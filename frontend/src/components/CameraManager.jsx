import React, { useState } from 'react';

export const CameraManager = ({ cameras = [], onRefreshCameras, onSeedCCTV }) => {
  const [newCamId, setNewCamId] = useState('');
  const [newCamName, setNewCamName] = useState('');
  const [newCamUrl, setNewCamUrl] = useState('');
  const [newCamLoc, setNewCamLoc] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);

  const handleAddCamera = async (e) => {
    e.preventDefault();
    if (!newCamId || !newCamName || !newCamUrl) {
      alert('Please fill out Camera ID, Name, and Stream URL');
      return;
    }

    try {
      const resp = await fetch('/api/cameras', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: newCamId,
          name: newCamName,
          rtsp_url: newCamUrl,
          location: newCamLoc || 'Main Facility'
        })
      });
      if (resp.ok) {
        setNewCamId('');
        setNewCamName('');
        setNewCamUrl('');
        setNewCamLoc('');
        setShowAddForm(false);
        onRefreshCameras();
      }
    } catch (err) {
      alert('Failed to add camera: ' + err.message);
    }
  };

  const handleDeleteCamera = async (id) => {
    if (!confirm(`Remove camera ${id}?`)) return;
    try {
      await fetch(`/api/cameras/${id}`, { method: 'DELETE' });
      onRefreshCameras();
    } catch (e) {
      alert('Failed to delete camera: ' + e.message);
    }
  };

  return (
    <div className="bg-slate-900/60 backdrop-blur-md border border-slate-800 rounded-2xl p-6 shadow-lg">
      <div className="flex flex-wrap justify-between items-center gap-3 mb-5">
        <div>
          <h3 className="text-base font-bold text-white tracking-tight">Monitored Cameras</h3>
          <p className="text-xs text-slate-400">Connected dock and perimeter video streams ({cameras.length})</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-white transition-colors flex items-center gap-1.5"
          >
            <span>{showAddForm ? '✕ Cancel' : '+ Add Camera'}</span>
          </button>

          <button
            onClick={onSeedCCTV}
            title="Reload all warehouse dock test feeds"
            className="px-3 py-1.5 rounded-lg border border-cyan-500/30 bg-cyan-950/20 hover:bg-cyan-900/40 text-xs font-medium text-cyan-400 transition-colors"
          >
            Reload Docks
          </button>
        </div>
      </div>

      {/* Add Camera Form */}
      {showAddForm && (
        <form onSubmit={handleAddCamera} className="bg-slate-950/60 p-4 rounded-xl border border-slate-800/80 mb-4 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] text-slate-400 uppercase tracking-wider block mb-1">Camera ID</label>
              <input
                type="text"
                placeholder="e.g. cctv_dock_09"
                value={newCamId}
                onChange={(e) => setNewCamId(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div>
              <label className="text-[11px] text-slate-400 uppercase tracking-wider block mb-1">Name</label>
              <input
                type="text"
                placeholder="e.g. Dock Gate 9"
                value={newCamName}
                onChange={(e) => setNewCamName(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div>
              <label className="text-[11px] text-slate-400 uppercase tracking-wider block mb-1">Stream URL</label>
              <input
                type="text"
                placeholder="rtsp://127.0.0.1:8554/dock9 or test_videos/..."
                value={newCamUrl}
                onChange={(e) => setNewCamUrl(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div>
              <label className="text-[11px] text-slate-400 uppercase tracking-wider block mb-1">Location / Dock</label>
              <input
                type="text"
                placeholder="e.g. Dock 9"
                value={newCamLoc}
                onChange={(e) => setNewCamLoc(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="submit"
              className="px-4 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-xs font-medium transition-colors"
            >
              Save Camera
            </button>
          </div>
        </form>
      )}

      {/* Camera Grid / List */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 max-h-[360px] overflow-y-auto pr-1">
        {cameras.map((c) => (
          <div
            key={c.id}
            className="bg-slate-950/40 border border-slate-800/60 rounded-xl p-3 flex justify-between items-center group hover:border-slate-700/80 transition-all"
          >
            <div className="min-w-0 flex-1 pr-2">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0" />
                <span className="font-semibold text-xs text-white truncate">{c.name}</span>
              </div>
              <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-1 truncate">
                <span className="bg-slate-800/80 px-1.5 py-0.5 rounded text-[10px] text-slate-300 font-medium">
                  {c.location || 'Facility'}
                </span>
                <span className="truncate font-mono text-[10px] text-slate-500">{c.rtsp_url}</span>
              </div>
            </div>

            <button
              onClick={() => handleDeleteCamera(c.id)}
              className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-rose-400 p-1 rounded transition-all text-xs"
              title="Delete camera"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};
