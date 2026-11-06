import React, { useEffect, useState } from "react";
const MIN_LOADING_MS = 1400;
function PageLoader({ onComplete }) {
  const [leaving, setLeaving] = useState(false);
  useEffect(() => {
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let disposed = false, finishTimer, minimumTimer, limitTimer;
    let loadHandler;
    const loaded = document.readyState === "complete" ? Promise.resolve() : new Promise((resolve) => {
      loadHandler = resolve;
      window.addEventListener("load", loadHandler, { once: true });
    });
    const fonts = document.fonts?.ready.catch(() => {
    }) || Promise.resolve();
    const minimum = new Promise((resolve) => {
      minimumTimer = setTimeout(resolve, reduced ? 0 : MIN_LOADING_MS);
    });
    const maximum = new Promise((resolve) => {
      limitTimer = setTimeout(resolve, 2400);
    });
    Promise.all([minimum, Promise.race([Promise.all([loaded, fonts]), maximum])]).then(() => {
      if (disposed) return;
      clearTimeout(limitTimer);
      setLeaving(true);
      finishTimer = setTimeout(onComplete, reduced ? 0 : 220);
    });
    return () => {
      disposed = true;
      clearTimeout(minimumTimer);
      clearTimeout(limitTimer);
      clearTimeout(finishTimer);
      if (loadHandler) window.removeEventListener("load", loadHandler);
    };
  }, [onComplete]);
  const layers = [
    { name: "input", x: 35, nodes: [65, 125] },
    { name: "hidden", x: 160, nodes: [25, 70, 115, 160] },
    { name: "output", x: 285, nodes: [65, 125] }
  ];
  return <div className={leaving ? "page-loader is-leaving" : "page-loader"} role="status" aria-label="Loading page">
    <div className="loader-content">
      <svg className="loader-network" viewBox="0 0 320 185" width="320" height="185" fill="none" aria-hidden="true">
        {layers.slice(0, -1).flatMap((layer, col) => layer.nodes.flatMap((y, i) => layers[col + 1].nodes.map((nextY, j) => {
    const d = `M${layer.x} ${y}L${layers[col + 1].x} ${nextY}`;
    return <g key={`${col}-${i}-${j}`}><path d={d} className="network-loader-edge" /><path d={d} className="network-loader-signal" style={{ animationDelay: `${col * 0.45 + i * 0.045 + j * 0.035}s` }} /></g>;
  })))}
        {layers.map((layer, col) => <g key={layer.name} data-neuron-layer={layer.name}>{layer.nodes.map((y, i) => <circle key={i} cx={layer.x} cy={y} r="10" className="network-loader-neuron" style={{ animationDelay: `${col * 0.45 + i * 0.06}s` }} />)}</g>)}
      </svg>
      <p>Loading…</p>
    </div>
  </div>;
}
export {
  PageLoader as default
};
