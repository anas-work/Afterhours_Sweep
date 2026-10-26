import React from 'react';

export const AlarmBanner = ({ isActive, cameraInfo, onSilence }) => {
  if (!isActive) return null;

  return (
    <div className="w-full bg-gradient-to-r from-red-700 via-rose-600 to-red-700 text-white px-6 py-3.5 shadow-2xl border-b border-red-500/60 flex flex-wrap justify-between items-center gap-4 relative z-40">
      <div className="flex items-center gap-3">
        <span className="flex h-3 w-3 relative">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-75"></span>
          <span className="relative inline-flex rounded-full h-3 w-3 bg-white"></span>
        </span>
        <span className="text-xl">🚨</span>
        <div>
          <span className="font-extrabold tracking-wider text-sm md:text-base">
            SECURITY INTRUSION ALERT: PERSON DETECTED IN AFTERHOURS SURVEILLANCE SWEEP!
          </span>
          {cameraInfo && (
            <span className="ml-3 bg-black/60 border border-white/40 px-2.5 py-1 rounded font-mono text-xs font-bold text-yellow-300 shadow-inner">
              Breached Dock: {cameraInfo}
            </span>
          )}
        </div>
      </div>
      <div>
        <button
          onClick={onSilence}
          className="bg-black/70 hover:bg-black/90 text-white border border-white/60 hover:border-white px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all shadow-lg hover:scale-105 active:scale-95 flex items-center gap-1.5"
        >
          <span>🔕</span>
          <span>Silence Alarm</span>
        </button>
      </div>
    </div>
  );
};
