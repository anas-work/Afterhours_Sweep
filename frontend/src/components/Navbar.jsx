import React from 'react';

export const Navbar = ({ 
  mode, 
  setMode, 
  audioMuted, 
  toggleMute, 
  testAlarm, 
  clockTime, 
  onFlushHistory 
}) => {
  return (
    <header className="bg-slate-900/90 backdrop-blur-md border-b border-slate-800/80 px-6 py-3.5 sticky top-0 z-50 flex flex-wrap justify-between items-center gap-4">
      {/* Brand Section */}
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
        </div>
        <div>
          <h1 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
            Afterhours Surveillance
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
              ABLBL
            </span>
          </h1>
          <p className="text-xs text-slate-400">
            Dock & Perimeter Monitoring
          </p>
        </div>
      </div>

      {/* Mode Switcher & Controls */}
      <div className="flex items-center gap-3">
        {/* Mode Toggle */}
        <div className="bg-slate-950/70 p-1 rounded-lg border border-slate-800 flex items-center">
          <button
            onClick={() => setMode('AUTO')}
            className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
              mode === 'AUTO' 
                ? 'bg-cyan-600 text-white shadow-sm' 
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Auto Mode
          </button>
          <button
            onClick={() => setMode('MANUAL')}
            className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
              mode === 'MANUAL' 
                ? 'bg-purple-600 text-white shadow-sm' 
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Manual Mode
          </button>
        </div>

        {/* Live IST Clock */}
        <div className="bg-slate-950/50 border border-slate-800/80 px-3 py-1 rounded-lg font-mono text-xs text-slate-200">
          {clockTime || '00:00:00'} <span className="text-[10px] text-slate-500">IST</span>
        </div>

        {/* Audio Mute Button */}
        <button
          onClick={toggleMute}
          className="px-2.5 py-1 rounded-lg border border-slate-800 bg-slate-950/50 hover:bg-slate-800 text-xs text-slate-300 transition-colors"
          title={audioMuted ? 'Unmute siren' : 'Mute siren'}
        >
          {audioMuted ? '🔇 Muted' : '🔊 Sound On'}
        </button>

        {/* Test Siren */}
        <button
          onClick={testAlarm}
          className="px-2.5 py-1 rounded-lg border border-red-500/30 bg-red-950/20 hover:bg-red-900/40 text-xs font-medium text-red-400 transition-colors"
        >
          Test Alarm
        </button>

        {/* Flush History */}
        <button
          onClick={onFlushHistory}
          title="Clear all past sweeps and detection history"
          className="px-2.5 py-1 rounded-lg border border-slate-800 bg-slate-950/50 hover:bg-rose-950/40 hover:border-rose-800/60 hover:text-rose-300 text-xs text-slate-400 transition-colors"
        >
          Clear History
        </button>
      </div>
    </header>
  );
};
