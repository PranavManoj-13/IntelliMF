import React, { useEffect, useRef } from "react";
const loss = (x, y) => 0.35 * (x * x - 1) ** 2 + 0.7 * (y - 0.32 * Math.sin(2 * x)) ** 2 + 0.08 * x;
function trajectory(x, y) {
  const points = [];
  for (let i = 0; i < 160; i++) {
    points.push({ x, y });
    const residual = y - 0.32 * Math.sin(2 * x);
    const dx = 1.4 * x * (x * x - 1) - 0.896 * residual * Math.cos(2 * x) + 0.08;
    x -= 0.045 * dx;
    y -= 0.045 * 1.4 * residual;
  }
  const distances = [0];
  for (let i = 1; i < points.length; i++) distances.push(distances[i - 1] + Math.hypot(points[i].x - points[i - 1].x, points[i].y - points[i - 1].y));
  let segment = 1;
  return Array.from({ length: 100 }, (_, i) => {
    const distance = distances.at(-1) * i / 99;
    while (segment < points.length - 1 && distances[segment] < distance) segment++;
    const ratio = (distance - distances[segment - 1]) / (distances[segment] - distances[segment - 1] || 1);
    return { x: points[segment - 1].x + (points[segment].x - points[segment - 1].x) * ratio, y: points[segment - 1].y + (points[segment].y - points[segment - 1].y) * ratio };
  });
}
function DescentBackground() {
  const canvasRef = useRef(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    const backdrop = document.createElement("canvas");
    const background = backdrop.getContext("2d");
    if (!ctx || !background) return;
    const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
    const paths = [trajectory(-1.85, 1.45), trajectory(1.8, -1.5), trajectory(0.3, 1.6)];
    const levels = [-0.04, 0.02, 0.09, 0.18, 0.3, 0.46, 0.68, 0.96, 1.3, 1.72, 2.25, 2.9, 3.7];
    let width = 0, height = 0, frame, lastFrame = 0;
    const project = ({ x, y }) => ({ x: width * 0.5 + x * width * 0.26 + y * width * 0.03, y: height * 0.55 + y * height * 0.29 - x * height * 0.035 });
    function drawContours() {
      background.clearRect(0, 0, width, height);
      const glow = background.createRadialGradient(width * 0.6, height * 0.55, 0, width * 0.6, height * 0.55, width * 0.7);
      glow.addColorStop(0, "#24374b80");
      glow.addColorStop(1, "#17233200");
      background.fillStyle = glow;
      background.fillRect(0, 0, width, height);
      const columns = 125, rows = 85;
      const grid = Array.from({ length: rows + 1 }, (_, row) => Array.from({ length: columns + 1 }, (_2, col) => {
        const x = col / columns * 4.4 - 2.2, y = row / rows * 3.6 - 1.8;
        return { x, y, value: loss(x, y) };
      }));
      for (const [index, level] of levels.entries()) {
        background.beginPath();
        for (let row = 0; row < rows; row++) for (let col = 0; col < columns; col++) {
          const corners = [grid[row][col], grid[row][col + 1], grid[row + 1][col + 1], grid[row + 1][col]];
          const crossings = [];
          for (let edge = 0; edge < 4; edge++) {
            const a = corners[edge], b = corners[(edge + 1) % 4];
            if (a.value < level === b.value < level) continue;
            const ratio = (level - a.value) / (b.value - a.value);
            crossings.push(project({ x: a.x + (b.x - a.x) * ratio, y: a.y + (b.y - a.y) * ratio }));
          }
          if (crossings.length === 4 && corners.reduce((sum, point) => sum + point.value, 0) / 4 < level) crossings.push(crossings.shift());
          for (let i = 0; i + 1 < crossings.length; i += 2) {
            background.moveTo(crossings[i].x, crossings[i].y);
            background.lineTo(crossings[i + 1].x, crossings[i + 1].y);
          }
        }
        background.strokeStyle = index % 3 === 0 ? "#90c1c54a" : "#849fc32f";
        background.lineWidth = index % 3 === 0 ? 1.2 : 0.8;
        background.stroke();
      }
    }
    function draw(time = 0) {
      ctx.clearRect(0, 0, width, height);
      ctx.drawImage(backdrop, 0, 0, width, height);
      paths.forEach((path, index) => {
        const progress = reducedMotion.matches ? 0.65 : (time / 16e3 + index * 0.27) % 1;
        const position = progress * (path.length - 1), step = Math.floor(position);
        ctx.beginPath();
        path.forEach((point2, i) => {
          const p = project(point2);
          if (i === 0) ctx.moveTo(p.x, p.y);
          else ctx.lineTo(p.x, p.y);
        });
        ctx.strokeStyle = "#acd6d52f";
        ctx.lineWidth = 1.2;
        ctx.stroke();
        ctx.beginPath();
        for (let i = Math.max(0, step - 12); i <= step; i++) {
          const p = project(path[i]);
          if (i === Math.max(0, step - 12)) ctx.moveTo(p.x, p.y);
          else ctx.lineTo(p.x, p.y);
        }
        ctx.strokeStyle = "#b9e2d5a8";
        ctx.lineWidth = 1.8;
        ctx.stroke();
        const next = path[Math.min(step + 1, path.length - 1)], ratio = position - step;
        const point = project({ x: path[step].x + (next.x - path[step].x) * ratio, y: path[step].y + (next.y - path[step].y) * ratio });
        const halo = ctx.createRadialGradient(point.x, point.y, 0, point.x, point.y, 17);
        halo.addColorStop(0, "#c2f4e160");
        halo.addColorStop(1, "#c2f4e100");
        ctx.fillStyle = halo;
        ctx.beginPath();
        ctx.arc(point.x, point.y, 17, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#c7e7de";
        ctx.beginPath();
        ctx.arc(point.x, point.y, 2.7, 0, Math.PI * 2);
        ctx.fill();
      });
    }
    function resize() {
      const bounds = canvas.getBoundingClientRect();
      width = bounds.width;
      height = bounds.height;
      const dpr = Math.min(devicePixelRatio || 1, 2);
      canvas.width = backdrop.width = width * dpr;
      canvas.height = backdrop.height = height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      background.setTransform(dpr, 0, 0, dpr, 0, 0);
      drawContours();
      draw();
    }
    function animate(time) {
      if (time - lastFrame > 40) {
        draw(time);
        lastFrame = time;
      }
      frame = requestAnimationFrame(animate);
    }
    function updateMotion() {
      cancelAnimationFrame(frame);
      if (reducedMotion.matches) draw();
      else frame = requestAnimationFrame(animate);
    }
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();
    updateMotion();
    reducedMotion.addEventListener("change", updateMotion);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      reducedMotion.removeEventListener("change", updateMotion);
    };
  }, []);
  return <canvas ref={canvasRef} />;
}
export {
  DescentBackground as default
};
