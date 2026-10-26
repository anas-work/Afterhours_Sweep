import React from 'react';

export const InspectionModal = ({ detection, onClose }) => {
  if (!detection) return null;

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 bg-black/85 backdrop-blur-md z-50 flex items-center justify-center p-4 md:p-8 animate-fadeIn"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-slate-900 border border-slate-700 rounded-2xl max-w-4xl w-full overflow-hidden shadow-2xl flex flex-col max-h-[90vh]"
      >
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex justify-between items-center bg-slate-950/60">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <span>🚨 Intrusion Evidence Inspection:</span>
              <span className="text-cyan-400">{detection.camera_name}</span>
            </h3>
            <div className="text-xs text-slate-400 font-mono">
              Sweep ID: {detection.sweep_id} • Offset: +{detection.video_offset_sec}s
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center justify-center font-bold text-sm transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Modal Body / Image View */}
        <div className="p-6 overflow-y-auto space-y-4">
          <div className="bg-black rounded-xl overflow-hidden flex justify-center items-center border border-slate-800">
            <img
              src={detection.capture_url}
              alt="High resolution annotated capture"
              className="max-h-[500px] w-auto max-w-full object-contain"
            />
          </div>

          {/* Metadata Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 bg-slate-950/60 p-4 rounded-xl border border-slate-800/80 font-mono text-xs">
            <div>
              <span className="text-slate-500 block">Camera ID</span>
              <strong className="text-white text-sm">{detection.camera_id}</strong>
            </div>
            <div>
              <span className="text-slate-500 block">Persons In Frame</span>
              <strong className="text-red-400 text-sm">{detection.person_count}</strong>
            </div>
            <div>
              <span className="text-slate-500 block">Confidence Score</span>
              <strong className="text-emerald-400 text-sm">{(detection.max_confidence * 100).toFixed(1)}%</strong>
            </div>
            <div>
              <span className="text-slate-500 block">Captured Timestamp</span>
              <strong className="text-slate-300 text-sm">
                {detection.timestamp ? detection.timestamp.replace('T', ' ').slice(0, 19) : 'N/A'}
              </strong>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
