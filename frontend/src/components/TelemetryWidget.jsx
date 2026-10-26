import React from 'react';

export const TelemetryWidget = ({ telemetry, processingTime, processingFps, processedFrames, totalFrames }) => {
  const gpuName = telemetry?.gpu_name || 'NVIDIA RTX A4000 (GPU 0)';
  const gpuUtil = telemetry?.gpu_utilization_pct ?? 0;
  const vramUsed = telemetry?.gpu_memory_used_mb ?? 0;
  const vramTotal = telemetry?.gpu_memory_total_mb ?? 16376;
  const cpuUtil = telemetry?.cpu_utilization_pct ?? 0;
  const ramUsed = telemetry?.ram_used_mb ?? 0;
  const ramTotal = telemetry?.ram_total_mb ?? 32000;

  return (
    <div className="bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-2xl p-6 shadow-xl">
      <div className="flex justify-between items-center mb-4">
        <div>
          <h3 className="text-sm font-bold uppercase tracking-wider text-cyan-400">
            LIVE HARDWARE & TESTING TELEMETRY
          </h3>
          <p className="text-xs text-slate-400">Real-time NVIDIA GPU 0 & throughput performance metrics</p>
        </div>
        <span className="px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-500/50 text-[11px] font-mono text-emerald-400">
          ACTIVE SENSORS
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Metric 1: Processing Speed FPS */}
        <div className="bg-slate-950/70 p-4 rounded-xl border border-slate-800/80 flex flex-col justify-between">
          <div className="text-[11px] font-mono uppercase text-slate-400">GPU 0 Ingestion FPS</div>
          <div className="text-2xl font-black font-mono text-emerald-400 my-1">
            {processingFps > 0 ? `${processingFps}` : '0.0'}
            <span className="text-xs font-normal text-slate-400 ml-1">FPS</span>
          </div>
          <div className="text-[10px] text-slate-400">Batched YOLO26n speed</div>
        </div>

        {/* Metric 2: Processing Duration */}
        <div className="bg-slate-950/70 p-4 rounded-xl border border-slate-800/80 flex flex-col justify-between">
          <div className="text-[11px] font-mono uppercase text-slate-400">Processing Time</div>
          <div className="text-2xl font-black font-mono text-cyan-400 my-1">
            {processingTime > 0 ? `${processingTime}` : '0.00'}
            <span className="text-xs font-normal text-slate-400 ml-1">s</span>
          </div>
          <div className="text-[10px] text-slate-400">
            {processedFrames > 0 ? `${processedFrames} frames analyzed` : 'Standby'}
          </div>
        </div>

        {/* Metric 3: GPU 0 VRAM & Core */}
        <div className="bg-slate-950/70 p-4 rounded-xl border border-slate-800/80 flex flex-col justify-between">
          <div className="text-[11px] font-mono uppercase text-slate-400">GPU 0 Load & VRAM</div>
          <div className="text-xl font-bold font-mono text-purple-400 my-1">
            {gpuUtil}% <span className="text-xs font-normal text-slate-400 font-mono">({Math.round(vramUsed)} MB)</span>
          </div>
          <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden mt-1">
            <div 
              className="bg-purple-500 h-full rounded-full transition-all"
              style={{ width: `${Math.min(100, Math.round((vramUsed / Math.max(1, vramTotal)) * 100))}%` }}
            />
          </div>
          <div className="text-[10px] text-slate-400 mt-1 truncate">{gpuName}</div>
        </div>

        {/* Metric 4: System RAM & Host CPU */}
        <div className="bg-slate-950/70 p-4 rounded-xl border border-slate-800/80 flex flex-col justify-between">
          <div className="text-[11px] font-mono uppercase text-slate-400">Host Memory & CPU</div>
          <div className="text-xl font-bold font-mono text-blue-400 my-1">
            {Math.round(ramUsed / 1024)}GB <span className="text-xs font-normal text-slate-400 font-mono">({cpuUtil}% CPU)</span>
          </div>
          <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden mt-1">
            <div 
              className="bg-blue-500 h-full rounded-full transition-all"
              style={{ width: `${Math.min(100, Math.round((ramUsed / Math.max(1, ramTotal)) * 100))}%` }}
            />
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Total RAM: {Math.round(ramTotal / 1024)} GB</div>
        </div>
      </div>
    </div>
  );
};
