import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Navbar } from './components/Navbar.jsx';
import { AlarmBanner } from './components/AlarmBanner.jsx';
import { CommandCenter } from './components/CommandCenter.jsx';
import { DetectionsGallery } from './components/DetectionsGallery.jsx';
import { CameraManager } from './components/CameraManager.jsx';
import { SweepHistory } from './components/SweepHistory.jsx';
import { InspectionModal } from './components/InspectionModal.jsx';

export const App = () => {
  // State
  const [mode, setMode] = useState('AUTO'); // 'AUTO' or 'MANUAL'
  const [currentState, setCurrentState] = useState('IDLE');
  const [statusDescription, setStatusDescription] = useState('System armed and waiting for trigger.');
  const [clockTime, setClockTime] = useState('--:--:--');
  const [scheduledTime, setScheduledTime] = useState('22:00:00');
  const [sweepDuration, setSweepDuration] = useState(180);
  const [countdownStr, setCountdownStr] = useState('--:--:--');
  const [recordingTimer, setRecordingTimer] = useState('00:00');
  const [recordingElapsedSec, setRecordingElapsedSec] = useState(0);

  // Progress & Telemetry
  const [progressPercent, setProgressPercent] = useState(0);
  const [processedFrames, setProcessedFrames] = useState(0);
  const [totalFrames, setTotalFrames] = useState(0);
  const [currentFps, setCurrentFps] = useState(0);
  const [processingTime, setProcessingTime] = useState(0);
  const [telemetry, setTelemetry] = useState(null);

  // Alarms & Data
  const [isAlarmActive, setIsAlarmActive] = useState(false);
  const [alarmCameraInfo, setAlarmCameraInfo] = useState('');
  const [audioMuted, setAudioMuted] = useState(false);
  const [detections, setDetections] = useState([]);
  const [cameras, setCameras] = useState([]);
  const [sweeps, setSweeps] = useState([]);
  const [selectedDetection, setSelectedDetection] = useState(null);

  // Web Audio Siren Synth
  const audioCtxRef = useRef(null);
  const sirenOscRef = useRef(null);
  const sirenIntervalRef = useRef(null);
  const isPlayingSirenRef = useRef(false);

  const initAudio = () => {
    if (!audioCtxRef.current) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      audioCtxRef.current = new AudioContext();
    }
    if (audioCtxRef.current.state === 'suspended') {
      audioCtxRef.current.resume();
    }
  };

  const playSiren = useCallback(() => {
    if (audioMuted) return;
    initAudio();
    if (isPlayingSirenRef.current) return;

    isPlayingSirenRef.current = true;
    const ctx = audioCtxRef.current;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0.35, ctx.currentTime);
    gain.connect(ctx.destination);

    const osc = ctx.createOscillator();
    osc.type = 'sawtooth';
    osc.connect(gain);
    osc.frequency.setValueAtTime(650, ctx.currentTime);
    osc.start();
    sirenOscRef.current = osc;

    let high = false;
    sirenIntervalRef.current = setInterval(() => {
      if (!isPlayingSirenRef.current || !ctx) return;
      high = !high;
      const target = high ? 980 : 580;
      osc.frequency.linearRampToValueAtTime(target, ctx.currentTime + 0.35);
    }, 400);
  }, [audioMuted]);

  const stopSiren = useCallback(() => {
    isPlayingSirenRef.current = false;
    if (sirenIntervalRef.current) {
      clearInterval(sirenIntervalRef.current);
      sirenIntervalRef.current = null;
    }
    if (sirenOscRef.current) {
      try {
        sirenOscRef.current.stop();
        sirenOscRef.current.disconnect();
      } catch (e) {}
      sirenOscRef.current = null;
    }
  }, []);

  // Fetch functions
  const fetchStatus = useCallback(async () => {
    try {
      const resp = await fetch('/api/status');
      if (resp.ok) {
        const data = await resp.json();
        setMode(data.mode || 'AUTO');
        setCurrentState(data.current_state);
        setScheduledTime(data.scheduled_time);
        setSweepDuration(data.sweep_duration_seconds);
        setTelemetry(data.telemetry);
        setProcessingTime(data.processing_time_sec);
        setCurrentFps(data.processing_fps);
        setProcessedFrames(data.processed_frames);
        setTotalFrames(data.total_frames);

        const cd = data.seconds_until_next_sweep;
        const ch = Math.floor(cd / 3600);
        const cm = Math.floor((cd % 3600) / 60);
        const cs = cd % 60;
        setCountdownStr(`${String(ch).padStart(2, '0')}:${String(cm).padStart(2, '0')}:${String(cs).padStart(2, '0')}`);

        if (data.is_alarm_active) {
          setIsAlarmActive(true);
          setAlarmCameraInfo(data.alarm_camera_info);
          playSiren();
        } else {
          setIsAlarmActive(false);
          stopSiren();
        }
      }
    } catch (e) {
      console.error('Failed to fetch status', e);
    }
  }, [playSiren, stopSiren]);

  const fetchDetections = async () => {
    try {
      const resp = await fetch('/api/detections?limit=50');
      if (resp.ok) {
        const data = await resp.json();
        setDetections(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchCameras = async () => {
    try {
      const resp = await fetch('/api/cameras');
      if (resp.ok) {
        const data = await resp.json();
        setCameras(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchSweeps = async () => {
    try {
      const resp = await fetch('/api/sweeps?limit=15');
      if (resp.ok) {
        const data = await resp.json();
        setSweeps(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Clock interval
  useEffect(() => {
    const clockInterval = setInterval(() => {
      const now = new Date();
      setClockTime(now.toLocaleTimeString('en-US', { timeZone: 'Asia/Kolkata', hour12: false }));
    }, 1000);
    return () => clearInterval(clockInterval);
  }, []);

  // Timer ticker while recording
  useEffect(() => {
    let t = null;
    if (currentState === 'RECORDING') {
      t = setInterval(() => {
        setRecordingElapsedSec((prev) => {
          const next = prev + 1;
          const m = Math.floor(next / 60);
          const s = next % 60;
          setRecordingTimer(`${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`);
          return next;
        });
      }, 1000);
    } else {
      setRecordingElapsedSec(0);
      setRecordingTimer('00:00');
    }
    return () => {
      if (t) clearInterval(t);
    };
  }, [currentState]);

  // WebSocket
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/events`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const { event: evType, data } = JSON.parse(event.data);

        if (evType === 'STATUS_UPDATE') {
          fetchStatus();
        } else if (evType === 'SWEEP_STARTED') {
          setCurrentState('RECORDING');
          setStatusDescription(`Recording surveillance footage across ${data.cameras_count || 11} camera docks...`);
          setProgressPercent(10);
        } else if (evType === 'PROCESSING_STARTED') {
          setCurrentState('PROCESSING');
          setStatusDescription('Recording complete. Processing footages at 1-FPS with GPU 0 YOLO26n batch inference...');
        } else if (evType === 'PROCESSING_PROGRESS') {
          setProgressPercent(data.progress_percent || 0);
          setProcessedFrames(data.processed_frames);
          setTotalFrames(data.total_frames);
          setCurrentFps(data.fps);
          if (data.telemetry) setTelemetry(data.telemetry);
        } else if (evType === 'ALARM_TRIGGERED') {
          setIsAlarmActive(true);
          setAlarmCameraInfo(data.camera_name);
          playSiren();
          fetchDetections();
        } else if (evType === 'ALARM_SILENCED') {
          setIsAlarmActive(false);
          stopSiren();
        } else if (evType === 'SWEEP_COMPLETED') {
          setProgressPercent(100);
          setCurrentState(data.alarm_triggered ? 'ALARM_ACTIVE' : 'COMPLETED');
          setStatusDescription(
            `Sweep complete: ${data.processed_frames} frames processed at ${data.processing_fps} FPS. Detected ${data.detections_count} intruders.`
          );
          fetchSweeps();
          fetchDetections();
        }
      } catch (err) {
        console.error('WS parse error', err);
      }
    };

    const statusPolling = setInterval(fetchStatus, 3000);

    fetchStatus();
    fetchDetections();
    fetchCameras();
    fetchSweeps();

    return () => {
      ws.close();
      clearInterval(statusPolling);
    };
  }, [fetchStatus, playSiren, stopSiren]);

  // User Actions
  const handleModeChange = async (newMode) => {
    try {
      const resp = await fetch('/api/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: newMode })
      });
      if (resp.ok) {
        setMode(newMode);
        fetchStatus();
      }
    } catch (e) {
      alert('Error updating mode: ' + e.message);
    }
  };

  const handleStartManual = async () => {
    try {
      const resp = await fetch('/api/sweep/start_manual', { method: 'POST' });
      const data = await resp.json();
      if (!resp.ok) alert(data.detail);
      else fetchStatus();
    } catch (e) {
      alert('Failed to start manual capture: ' + e.message);
    }
  };

  const handleStopManual = async () => {
    try {
      const resp = await fetch('/api/sweep/stop_manual', { method: 'POST' });
      const data = await resp.json();
      if (!resp.ok) alert(data.detail);
      else fetchStatus();
    } catch (e) {
      alert('Failed to stop manual capture: ' + e.message);
    }
  };

  const handleTriggerAutoSweep = async () => {
    try {
      const resp = await fetch('/api/sweep/trigger', { method: 'POST' });
      const data = await resp.json();
      if (!resp.ok) alert(data.detail);
      else fetchStatus();
    } catch (e) {
      alert('Failed to trigger sweep: ' + e.message);
    }
  };

  const handleSilenceAlarm = async () => {
    try {
      await fetch('/api/sweep/silence_alarm', { method: 'POST' });
      setIsAlarmActive(false);
      stopSiren();
    } catch (e) {
      console.error(e);
    }
  };

  const handleFlushHistory = async () => {
    if (!window.confirm("Are you sure you want to flush all surveillance history, recorded clips, and person detection captures?")) {
      return;
    }
    try {
      const resp = await fetch('/api/flush', { method: 'POST' });
      if (resp.ok) {
        setDetections([]);
        setSweeps([]);
        setIsAlarmActive(false);
        setSelectedDetection(null);
        stopSiren();
        await Promise.all([fetchStatus(), fetchDetections(), fetchCameras(), fetchSweeps()]);
        alert('✓ All surveillance history and captures have been flushed.');
      } else {
        alert('Failed to flush history.');
      }
    } catch (e) {
      alert('Flush error: ' + e.message);
    }
  };

  const handleSeedCCTV = async () => {
    try {
      const resp = await fetch('/api/cameras/seed_cctv', { method: 'POST' });
      if (resp.ok) {
        fetchCameras();
        alert('Successfully copied test CCTV videos and initialized camera feeds!');
      }
    } catch (e) {
      alert('Failed to seed CCTV feeds: ' + e.message);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans flex flex-col selection:bg-cyan-500 selection:text-black">
      {/* Audio Siren Banner */}
      <AlarmBanner
        isActive={isAlarmActive}
        cameraInfo={alarmCameraInfo}
        onSilence={handleSilenceAlarm}
      />

      {/* Top Navbar */}
      <Navbar
        mode={mode}
        setMode={handleModeChange}
        audioMuted={audioMuted}
        toggleMute={() => {
          setAudioMuted(!audioMuted);
          if (!audioMuted) stopSiren();
        }}
        testAlarm={() => {
          initAudio();
          playSiren();
          setIsAlarmActive(true);
          setAlarmCameraInfo('TEST ALARM DRILL');
          setTimeout(() => {
            if (isAlarmActive) {
              setIsAlarmActive(false);
              stopSiren();
            }
          }, 4000);
        }}
        clockTime={clockTime}
        onFlushHistory={handleFlushHistory}
      />

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full space-y-8 flex-1">
        {/* Command Center with Auto/Manual & Live Timer */}
        <CommandCenter
          mode={mode}
          currentState={currentState}
          statusDescription={statusDescription}
          progressPercent={progressPercent}
          processedFrames={processedFrames}
          totalFrames={totalFrames}
          currentFps={currentFps}
          recordingTimer={recordingTimer}
          scheduledTime={scheduledTime}
          countdownStr={countdownStr}
          onStartManual={handleStartManual}
          onStopManual={handleStopManual}
          onTriggerAutoSweep={handleTriggerAutoSweep}
          sweepDuration={sweepDuration}
          processingTime={processingTime}
        />

        {/* Detections Gallery with Person Captures */}
        <DetectionsGallery
          detections={detections}
          onSelectDetection={(d) => setSelectedDetection(d)}
          onRefresh={fetchDetections}
          onFlushHistory={handleFlushHistory}
        />

        {/* Camera Feeds & Sweep History */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <CameraManager
            cameras={cameras}
            onRefreshCameras={fetchCameras}
            onSeedCCTV={handleSeedCCTV}
          />

          <SweepHistory
            sweeps={sweeps}
            onRefresh={fetchSweeps}
            onFlushHistory={handleFlushHistory}
          />
        </div>
      </main>

      {/* Fullscreen Inspection Modal */}
      <InspectionModal
        detection={selectedDetection}
        onClose={() => setSelectedDetection(null)}
      />
    </div>
  );
};
