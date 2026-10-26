import React, { useState, useMemo } from 'react';

export const DetectionsGallery = ({ 
  detections = [], 
  onSelectDetection, 
  onRefresh,
  onFlushHistory 
}) => {
  const [viewMode, setViewMode] = useState('dock'); // 'dock' or 'timeline'
  const [selectedDockFilter, setSelectedDockFilter] = useState('ALL');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshToast, setRefreshToast] = useState('');

  // Group detections by Dock / Camera
  const dockGroups = useMemo(() => {
    const map = {};
    for (const det of detections) {
      const camId = det.camera_id || 'unknown';
      if (!map[camId]) {
        map[camId] = {
          dockId: camId,
          dockName: det.camera_name || camId,
          totalFrames: 0,
          peakConfidence: 0.0,
          peakSnapshotUrl: '',
          peakDetection: null,
          firstSec: det.video_offset_sec || 0,
          lastSec: det.video_offset_sec || 0,
          frames: []
        };
      }
      const grp = map[camId];
      grp.frames.push(det);
      grp.totalFrames += 1;
      grp.lastSec = Math.max(grp.lastSec, det.video_offset_sec || 0);
      grp.firstSec = Math.min(grp.firstSec, det.video_offset_sec || 0);

      if (det.max_confidence >= grp.peakConfidence) {
        grp.peakConfidence = det.max_confidence;
        grp.peakSnapshotUrl = det.capture_url;
        grp.peakDetection = det;
      }
    }

    // Sort frames chronologically within each dock
    Object.values(map).forEach((grp) => {
      grp.frames.sort((a, b) => (a.video_offset_sec || 0) - (b.video_offset_sec || 0));
      grp.durationSec = Math.max(1, Math.round(grp.lastSec - grp.firstSec + 1));
    });

    // Return docks sorted by frame count descending
    return Object.values(map).sort((a, b) => b.totalFrames - a.totalFrames);
  }, [detections]);

  // Docks available for filter
  const uniqueDocks = useMemo(() => {
    return dockGroups.map((g) => ({
      id: g.dockId,
      name: g.dockName,
      count: g.totalFrames
    }));
  }, [dockGroups]);

  // Filtered docks
  const filteredDockGroups = useMemo(() => {
    if (selectedDockFilter === 'ALL') return dockGroups;
    return dockGroups.filter((g) => g.dockId === selectedDockFilter);
  }, [dockGroups, selectedDockFilter]);

  // Filtered timeline detections
  const filteredTimelineDetections = useMemo(() => {
    if (selectedDockFilter === 'ALL') return detections;
    return detections.filter((d) => d.camera_id === selectedDockFilter);
  }, [detections, selectedDockFilter]);

  const handleRefreshClick = async () => {
    setIsRefreshing(true);
    setRefreshToast('Refreshing surveillance feed...');
    try {
      if (onRefresh) await onRefresh();
      setRefreshToast('✓ Feeds & captures refreshed!');
    } catch (e) {
      setRefreshToast('Error refreshing feed');
    } finally {
      setIsRefreshing(false);
      setTimeout(() => setRefreshToast(''), 3000);
    }
  };

  return (
    <div className="bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-2xl p-6 shadow-xl relative">
      {/* Top Header Row */}
      <div className="flex flex-wrap justify-between items-center gap-4 mb-6 pb-4 border-b border-slate-800/80">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="text-base font-bold text-white tracking-tight">
              Detected Intrusions
            </h2>
            <span className="bg-red-950/40 border border-red-500/30 text-red-400 font-mono text-xs px-2.5 py-0.5 rounded-full font-medium">
              {detections.length} frames • {dockGroups.length} docks
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Review activity organized by dock location or chronological timeline
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2.5">
          {refreshToast && (
            <span className="text-xs font-mono text-cyan-400 bg-cyan-950/60 border border-cyan-500/40 px-3 py-1 rounded-lg animate-pulse">
              {refreshToast}
            </span>
          )}

          {/* View Mode Toggle */}
          <div className="bg-slate-950/80 p-1 rounded-xl border border-slate-800 flex items-center">
            <button
              onClick={() => setViewMode('dock')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
                viewMode === 'dock'
                  ? 'bg-gradient-to-r from-cyan-600 to-blue-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <span>🏢</span>
              <span>By Dock</span>
            </button>
            <button
              onClick={() => setViewMode('timeline')}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
                viewMode === 'timeline'
                  ? 'bg-gradient-to-r from-cyan-600 to-blue-600 text-white shadow-md'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <span>⏱️</span>
              <span>All Frames</span>
            </button>
          </div>

          {/* Refresh Feed Button */}
          <button
            onClick={handleRefreshClick}
            disabled={isRefreshing}
            className="px-3.5 py-2 rounded-xl bg-slate-800/80 hover:bg-slate-700/80 active:scale-95 text-xs font-bold text-slate-200 border border-slate-700 transition-all flex items-center gap-1.5 shadow-sm"
          >
            <span className={isRefreshing ? 'animate-spin inline-block' : ''}>🔄</span>
            <span>Refresh Feed</span>
          </button>

          {/* Flush History Button */}
          {onFlushHistory && (
            <button
              onClick={onFlushHistory}
              title="Clear all detection history"
              className="px-3 py-2 rounded-xl bg-rose-950/40 hover:bg-rose-900/60 active:scale-95 text-xs font-bold text-rose-300 border border-rose-500/40 transition-all flex items-center gap-1.5 shadow-sm"
            >
              <span>🗑️</span>
              <span>Flush</span>
            </button>
          )}
        </div>
      </div>

      {/* Dock Filter Selector Pill Bar */}
      {uniqueDocks.length > 0 && (
        <div className="flex items-center gap-2 overflow-x-auto pb-3 mb-5 scrollbar-thin">
          <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider whitespace-nowrap mr-1">
            Filter Dock:
          </span>
          <button
            onClick={() => setSelectedDockFilter('ALL')}
            className={`px-3 py-1 rounded-lg text-xs font-bold whitespace-nowrap transition-all ${
              selectedDockFilter === 'ALL'
                ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                : 'bg-slate-950/70 border border-slate-800 text-slate-300 hover:border-slate-700'
            }`}
          >
            All Docks ({detections.length})
          </button>
          {uniqueDocks.map((dock) => (
            <button
              key={dock.id}
              onClick={() => setSelectedDockFilter(dock.id)}
              className={`px-3 py-1 rounded-lg text-xs font-bold whitespace-nowrap transition-all flex items-center gap-1.5 ${
                selectedDockFilter === dock.id
                  ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                  : 'bg-slate-950/70 border border-slate-800 text-slate-300 hover:border-slate-700'
              }`}
            >
              <span>📍 {dock.name}</span>
              <span className="font-mono text-[10px] bg-black/40 px-1.5 py-0.2 rounded-full">
                {dock.count}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Empty State */}
      {detections.length === 0 ? (
        <div className="py-20 text-center border-2 border-dashed border-slate-800/80 rounded-2xl bg-slate-950/40">
          <div className="text-5xl mb-3 animate-pulse">🛡️</div>
          <div className="text-base font-extrabold text-white">No Afterhours Intrusions Recorded</div>
          <div className="text-xs text-slate-400 mt-1 max-w-md mx-auto">
            All camera feeds and warehouse docks are clear. Feeds are monitored via automated scheduled sweeps or manual recording.
          </div>
        </div>
      ) : viewMode === 'dock' ? (
        /* DOCK ORGANIZED VIEW */
        <div className="space-y-6">
          {filteredDockGroups.map((dock) => (
            <div
              key={dock.dockId}
              className="bg-slate-950/70 border border-slate-800 hover:border-cyan-500/50 rounded-2xl p-5 shadow-lg transition-all"
            >
              {/* Dock Header */}
              <div className="flex flex-wrap justify-between items-center gap-3 pb-4 border-b border-slate-800/80">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-red-950/60 border border-red-500/60 flex items-center justify-center text-sm shadow-[0_0_10px_rgba(239,68,68,0.3)]">
                    🚨
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-extrabold text-white text-base">{dock.dockName}</h3>
                      <span className="text-xs font-mono text-cyan-400 bg-cyan-950/80 border border-cyan-800 px-2 py-0.5 rounded">
                        {dock.dockId}
                      </span>
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">
                      Location: <span className="text-slate-300 font-medium">{dock.frames[0]?.camera_name || 'Main Dock Facility'}</span>
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3 font-mono text-xs">
                  <span className="bg-red-950/70 border border-red-500/40 text-red-300 px-2.5 py-1 rounded-lg">
                    {dock.totalFrames} Intrusion Frames ({dock.durationSec}s duration)
                  </span>
                  <span className="bg-cyan-950/70 border border-cyan-500/40 text-cyan-300 px-2.5 py-1 rounded-lg">
                    Peak Conf: {(dock.peakConfidence * 100).toFixed(1)}%
                  </span>
                </div>
              </div>

              {/* Dock Content: Peak Keyframe + 1-FPS Frame Reel */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 mt-4">
                {/* Left: Peak Keyframe (Best snapshot for this dock) */}
                <div className="lg:col-span-4 flex flex-col justify-between bg-black/60 rounded-xl p-3 border border-slate-800/80">
                  <div className="text-[11px] font-mono text-cyan-400 uppercase tracking-wider mb-2 flex justify-between items-center">
                    <span>★ Keyframe / Peak View</span>
                    <span>Conf: {(dock.peakConfidence * 100).toFixed(1)}%</span>
                  </div>

                  <div
                    onClick={() => onSelectDetection(dock.peakDetection)}
                    className="relative aspect-video rounded-lg overflow-hidden cursor-pointer group bg-black shadow-md border border-slate-700/60"
                  >
                    <img
                      src={dock.peakSnapshotUrl}
                      alt={`Peak detection on ${dock.dockName}`}
                      className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                    />
                    <div className="absolute top-2 right-2 bg-red-600 text-white font-mono text-[10px] font-bold px-2 py-0.5 rounded-full shadow">
                      PEAK DETECT
                    </div>
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center font-bold text-xs text-white">
                      Click to Inspect
                    </div>
                  </div>

                  <div className="mt-2 text-right">
                    <button
                      onClick={() => onSelectDetection(dock.peakDetection)}
                      className="text-xs font-bold text-cyan-400 hover:text-cyan-300 hover:underline"
                    >
                      Enlarge Keyframe Inspection →
                    </button>
                  </div>
                </div>

                {/* Right: 1-FPS Consecutive Frame Reel */}
                <div className="lg:col-span-8 flex flex-col justify-between">
                  <div className="text-[11px] font-mono text-slate-400 uppercase tracking-wider mb-2 flex justify-between items-center">
                    <span>1-FPS Timeline Reel ({dock.frames.length} Decimated Frames)</span>
                    <span className="text-[10px] text-slate-500">Scroll horizontally to inspect sequence</span>
                  </div>

                  <div className="flex gap-3 overflow-x-auto pb-3 pt-1 scrollbar-thin">
                    {dock.frames.map((frame, fIdx) => (
                      <div
                        key={frame.id || fIdx}
                        onClick={() => onSelectDetection(frame)}
                        className="flex-shrink-0 w-44 bg-slate-900 border border-slate-800 hover:border-red-500/80 rounded-xl overflow-hidden cursor-pointer group transition-all duration-200 hover:-translate-y-1 shadow"
                      >
                        <div className="relative aspect-video bg-black overflow-hidden">
                          <img
                            src={frame.capture_url}
                            alt={`Frame +${frame.video_offset_sec}s`}
                            className="w-full h-full object-cover transition-transform group-hover:scale-105"
                          />
                          <div className="absolute top-1.5 right-1.5 bg-black/70 backdrop-blur-sm text-yellow-300 font-mono text-[9px] px-1.5 py-0.5 rounded">
                            +{(frame.video_offset_sec || 0).toFixed(0)}s
                          </div>
                          <div className="absolute bottom-1.5 left-1.5 bg-red-600/90 text-white font-mono text-[9px] px-1.5 py-0.5 rounded font-bold">
                            {frame.person_count}P
                          </div>
                        </div>
                        <div className="p-2 flex justify-between items-center font-mono text-[10px] text-slate-400">
                          <span className="text-cyan-400 font-bold">
                            {(frame.max_confidence * 100).toFixed(0)}%
                          </span>
                          <span className="group-hover:text-white transition-colors">
                            Inspect →
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* FLAT TIMELINE GRID VIEW */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
          {filteredTimelineDetections.map((det) => (
            <div
              key={det.id}
              onClick={() => onSelectDetection(det)}
              className="bg-slate-950/70 border border-slate-800 hover:border-red-500/70 rounded-xl overflow-hidden transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_10px_25px_rgba(239,68,68,0.2)] cursor-pointer group flex flex-col"
            >
              <div className="relative aspect-video bg-black overflow-hidden">
                <img
                  src={det.capture_url}
                  alt={`Intrusion capture on ${det.camera_name}`}
                  className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                  onError={(e) => {
                    e.target.onerror = null;
                    e.target.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="200" fill="%23111"><text x="50%" y="50%" fill="%23999" text-anchor="middle">Loading Snapshot...</text></svg>';
                  }}
                />
                <div className="absolute top-2.5 right-2.5 bg-red-600/90 backdrop-blur-sm text-white font-mono font-bold text-xs px-2.5 py-1 rounded-full shadow-lg flex items-center gap-1">
                  <span>🚨</span>
                  <span>{det.person_count} PERSON{det.person_count > 1 ? 'S' : ''}</span>
                </div>
                <div className="absolute bottom-2 left-2 bg-slate-950/80 backdrop-blur-sm border border-slate-700/60 text-cyan-400 font-mono text-[10px] px-2 py-0.5 rounded">
                  {det.camera_id}
                </div>
              </div>

              <div className="p-3.5 flex flex-col gap-1.5 flex-1 justify-between">
                <div>
                  <div className="font-bold text-sm text-white truncate group-hover:text-cyan-400 transition-colors">
                    {det.camera_name}
                  </div>
                  <div className="flex justify-between items-center text-xs font-mono text-slate-400 mt-1">
                    <span>Offset: +{det.video_offset_sec}s</span>
                    <span className="text-cyan-400 font-bold">
                      {(det.max_confidence * 100).toFixed(1)}% conf
                    </span>
                  </div>
                </div>

                <div className="text-[10px] font-mono text-slate-500 border-t border-slate-800/80 pt-2 flex justify-between items-center">
                  <span>{det.timestamp ? det.timestamp.replace('T', ' ').slice(0, 19) : ''}</span>
                  <span className="text-cyan-400 text-xs font-bold group-hover:translate-x-0.5 transition-transform">
                    Inspect →
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
