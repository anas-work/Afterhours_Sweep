import React from 'react';

export const CommandCenter = ({
  mode,
  currentState,
  statusDescription,
  progressPercent,
  processedFrames,
  totalFrames,
  currentFps,
  recordingTimer,
  scheduledTime,
  countdownStr,
  onStartManual,
  onStopManual,
  onTriggerAutoSweep,
  processingTime,
  sweepDuration = 180
}) => {
  const isRecording = currentState === 'RECORDING';
  const isProcessing = currentState === 'PROCESSING';

  const getStatusBadge = () => {
    switch (currentState) {
      case 'RECORDING':
        return (
          <span className="inline-flex items-center gap-1.5 bg-blue-500/10 text-blue-400 border border-blue-500/30 px-3 py-1 rounded-full text-xs font-medium">
            <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
            Recording Cameras
          </span>
        );
      case 'PROCESSING':
        return (
          <span className="inline-flex items-center gap-1.5 bg-amber-500/10 text-amber-400 border border-amber-500/30 px-3 py-1 rounded-full text-xs font-medium">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            Analyzing Footages
          </span>
        );
      case 'ALARM_ACTIVE':
        return (
          <span className="inline-flex items-center gap-1.5 bg-red-500/15 text-red-400 border border-red-500/40 px-3 py-1 rounded-full text-xs font-semibold animate-bounce">
            <span className="w-2 h-2 rounded-full bg-red-500" />
            Intrusion Detected
          </span>
        );
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center gap-1.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 px-3 py-1 rounded-full text-xs font-medium">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            Sweep Complete
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 bg-slate-800 text-slate-300 border border-slate-700/60 px-3 py-1 rounded-full text-xs font-medium">
            <span className="w-2 h-2 rounded-full bg-slate-400" />
            Ready
          </span>
        );
    }
  };

  return (
    <div className="bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-2xl p-6 shadow-lg relative overflow-hidden transition-all">
      {/* Header Row */}
      <div className="flex flex-wrap justify-between items-center gap-4 pb-4 border-b border-slate-800/80">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
            Surveillance Controls
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight">
            {mode === 'MANUAL' ? 'Manual Capture Mode' : 'Automated Schedule Mode'}
          </h2>
        </div>
        <div className="flex items-center gap-2">
          {getStatusBadge()}
        </div>
      </div>

      {/* Main Controls Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 my-6">
        {/* Action Buttons */}
        <div className="lg:col-span-2 flex flex-col justify-center gap-4 bg-slate-950/40 p-5 rounded-xl border border-slate-800/60">
          {mode === 'MANUAL' ? (
            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={onStartManual}
                disabled={isRecording || isProcessing}
                className={`flex-1 py-3 px-5 rounded-xl font-semibold text-sm transition-all flex items-center justify-center gap-2 ${
                  isRecording || isProcessing
                    ? 'bg-slate-800/50 text-slate-500 cursor-not-allowed border border-slate-800'
                    : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-900/20 active:scale-[0.99]'
                }`}
              >
                <span>▶</span>
                <span>Start Surveillance</span>
              </button>

              <button
                onClick={onStopManual}
                disabled={!isRecording}
                className={`flex-1 py-3 px-5 rounded-xl font-semibold text-sm transition-all flex items-center justify-center gap-2 ${
                  !isRecording
                    ? 'bg-slate-800/50 text-slate-500 cursor-not-allowed border border-slate-800'
                    : 'bg-rose-600 hover:bg-rose-500 text-white shadow-md shadow-rose-900/20 active:scale-[0.99]'
                }`}
              >
                <span>⏹</span>
                <span>Stop & Analyze</span>
              </button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={onTriggerAutoSweep}
                disabled={isRecording || isProcessing}
                className={`flex-1 py-3 px-5 rounded-xl font-semibold text-sm transition-all flex items-center justify-center gap-2 ${
                  isRecording || isProcessing
                    ? 'bg-slate-800/50 text-slate-500 cursor-not-allowed border border-slate-800'
                    : 'bg-cyan-600 hover:bg-cyan-500 text-white shadow-md shadow-cyan-900/20 active:scale-[0.99]'
                }`}
              >
                <span>⚡</span>
                <span>Run Sweep Now</span>
              </button>
            </div>
          )}

          {/* Clean Description */}
          <div className="text-xs text-slate-400 flex items-center gap-2">
            <span className="text-slate-500">ℹ</span>
            <span>{statusDescription || 'System is armed and monitoring all registered dock feeds.'}</span>
          </div>
        </div>

        {/* Status / Countdown Box */}
        <div className="bg-slate-950/40 p-5 rounded-xl border border-slate-800/60 flex flex-col justify-center items-center text-center">
          {isRecording ? (
            <div>
              <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">Recording Remaining</div>
              <div className="text-3xl font-mono font-bold text-blue-400">
                {recordingTimer}s
              </div>
              <div className="text-xs text-slate-500 mt-1">Collecting 1-FPS feeds</div>
            </div>
          ) : mode === 'AUTO' ? (
            <div>
              <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">Next Scheduled Sweep</div>
              <div className="text-2xl font-mono font-bold text-white tracking-tight">
                {scheduledTime || '23:30:00'}
              </div>
              <div className="text-xs font-mono text-cyan-400 mt-1">
                in {countdownStr || '00:00:00'}
              </div>
            </div>
          ) : (
            <div>
              <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">Mode</div>
              <div className="text-xl font-bold text-white">Manual Standby</div>
              <div className="text-xs text-slate-500 mt-1">Press Start to capture</div>
            </div>
          )}
        </div>
      </div>

      {/* Progress Bar (when active) */}
      {(isRecording || isProcessing || progressPercent > 0) && (
        <div className="mb-4">
          <div className="flex justify-between items-center text-xs text-slate-400 mb-1.5">
            <span>{isRecording ? 'Capturing camera video...' : isProcessing ? 'Analyzing frames...' : 'Sweep Progress'}</span>
            <span className="font-mono text-white">{Math.round(progressPercent)}%</span>
          </div>
          <div className="w-full h-2 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
            <div
              className="h-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all duration-300 rounded-full"
              style={{ width: `${Math.min(100, Math.max(0, progressPercent))}%` }}
            />
          </div>
        </div>
      )}

      {/* Minimalist Performance Summary Strip (No GPU/CPU meters) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-slate-800/60">
        <div className="bg-slate-950/30 p-2.5 rounded-lg border border-slate-800/40">
          <div className="text-[11px] text-slate-400 uppercase tracking-wider">Processing Speed</div>
          <div className="text-base font-semibold text-white font-mono mt-0.5">
            {currentFps ? `${currentFps.toFixed(1)} FPS` : '—'}
          </div>
        </div>

        <div className="bg-slate-950/30 p-2.5 rounded-lg border border-slate-800/40">
          <div className="text-[11px] text-slate-400 uppercase tracking-wider">Processing Time</div>
          <div className="text-base font-semibold text-white font-mono mt-0.5">
            {processingTime ? `${processingTime.toFixed(2)}s` : '—'}
          </div>
        </div>

        <div className="bg-slate-950/30 p-2.5 rounded-lg border border-slate-800/40">
          <div className="text-[11px] text-slate-400 uppercase tracking-wider">Frames Analyzed</div>
          <div className="text-base font-semibold text-white font-mono mt-0.5">
            {processedFrames} / {totalFrames || '—'}
          </div>
        </div>

        <div className="bg-slate-950/30 p-2.5 rounded-lg border border-slate-800/40">
          <div className="text-[11px] text-slate-400 uppercase tracking-wider">Sweep Window</div>
          <div className="text-base font-semibold text-white font-mono mt-0.5">
            {sweepDuration ? (
              sweepDuration % 60 === 0
                ? `${sweepDuration}s (${Math.floor(sweepDuration / 60)} min)`
                : sweepDuration >= 60
                ? `${sweepDuration}s (${Math.floor(sweepDuration / 60)}m ${sweepDuration % 60}s)`
                : `${sweepDuration}s`
            ) : '—'}
          </div>
        </div>
      </div>
    </div>
  );
};
