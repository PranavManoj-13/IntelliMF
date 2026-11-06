import React from "react";
function NetworkBackground() {
  const nodes = [
    [980, 150],
    [1120, 95],
    [1270, 175],
    [1410, 115],
    [1025, 300],
    [1175, 265],
    [1340, 340],
    [1480, 275],
    [950, 455],
    [1110, 435],
    [1260, 510],
    [1440, 470]
  ];
  const edges = [[0, 1], [0, 4], [0, 5], [1, 2], [1, 5], [2, 3], [2, 5], [2, 6], [3, 7], [4, 5], [4, 8], [4, 9], [5, 6], [5, 9], [6, 7], [6, 9], [6, 10], [6, 11], [7, 11], [8, 9], [9, 10], [10, 11]];
  return <div className="site-background" aria-hidden="true">
    <svg viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMin slice" focusable="false">
      <defs>
        <pattern id="feature-grid" width="34" height="34" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".85" fill="currentColor" /></pattern>
        <linearGradient id="contour-fade" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#748fc4" stopOpacity=".35" /><stop offset="1" stopColor="#748fc4" stopOpacity="0" /></linearGradient>
      </defs>
      <rect width="1600" height="1000" fill="url(#feature-grid)" className="background-grid" />
      <g className="background-contours" fill="none" stroke="url(#contour-fade)" strokeWidth="1">
        {Array.from({ length: 8 }, (_, i) => <path key={i} d={`M${-150 + i * 22} 760 C${180 + i * 30} ${270 + i * 25}, ${700 + i * 20} ${1160 - i * 30}, ${1700 + i * 20} ${510 + i * 21}`} />)}
      </g>
      <g className="background-network">
        {edges.map(([a, b], i) => <path key={i} d={`M${nodes[a][0]} ${nodes[a][1]}L${nodes[b][0]} ${nodes[b][1]}`} fill="none" stroke="currentColor" strokeWidth="1" />)}
        {nodes.map(([x, y], i) => <circle key={i} cx={x} cy={y} r={i % 3 === 0 ? 4.5 : 3} fill="currentColor" className={i % 3 === 0 ? "network-pulse" : ""} style={{ animationDelay: `${i * 0.5}s` }} />)}
      </g>
      <g className="background-regression" fill="currentColor">
        <path d="M40 900 390 725" stroke="currentColor" strokeWidth="1" strokeDasharray="5 8" />
        {Array.from({ length: 20 }, (_, i) => <circle key={i} cx={50 + i * 17} cy={900 - i * 8 + Math.sin(i * 2.3) * 28} r={2 + i % 2} />)}
      </g>
    </svg>
  </div>;
}
export {
  NetworkBackground as default
};
