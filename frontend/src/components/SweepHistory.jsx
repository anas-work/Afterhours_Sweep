import React from 'react';

export const SweepHistory = ({ sweeps = [], onRefresh, onFlushHistory }) => {
  return (
    <div className="bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-2xl p-6 shadow-lg">
      <div className="flex flex-wrap justify-between items-center gap-3 mb-5">
        <div>
          <h3 className="text-base font-bold text-white tracking-tight">Sweep History</h3>
          <p className="text-xs text-slate-400">Past automated and manual surveillance runs ({sweeps.length})</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onRefresh}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-300 transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      <div className="space-y-2.5 max-h-[360px] overflow-y-auto pr-1">
        {sweeps.length === 0 ? (
          <div className="text-center py-10 text-slate-500 text-xs">
            No surveillance sweeps recorded yet.
          </div>
        ) : (
          sweeps.map((sw) => {
            const hasIntrusion = sw.alarm_triggered || (sw.detections && sw.detections.length > 0);
            return (
              <div
                key={sw.id}
                className="bg-slate-950/40 border border-slate-800/60 rounded-xl p-3 flex flex-wrap justify-between items-center gap-3 hover:border-slate-700/80 transition-all"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        hasIntrusion ? 'bg-rose-500' : 'bg-emerald-400'
                      }`}
                    />
                    <span className="font-mono text-xs font-semibold text-white">
                      {sw.id}
                    </span>
                    <span
                      className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
                        hasIntrusion
                          ? 'bg-rose-950/40 text-rose-400 border border-rose-800/40'
                          : 'bg-emerald-950/40 text-emerald-400 border border-emerald-800/40'
                      }`}
                    >
                      {hasIntrusion ? 'Intrusion Alert' : 'Clear'}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">
                    {new Date(sw.started_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })}
                  </div>
                </div>

                <div className="flex items-center gap-4 text-xs font-mono text-right">
                  <div>
                    <div className="text-slate-400 text-[10px] uppercase">Frames</div>
                    <div className="text-white font-medium">{sw.processed_frames || 0}</div>
                  </div>
                  <div>
                    <div className="text-slate-400 text-[10px] uppercase">Speed</div>
                    <div className="text-white font-medium">{sw.processing_fps ? `${sw.processing_fps.toFixed(1)} FPS` : '—'}</div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
