// Decorative NAV-style paths and recurring SIP contributions; not live fund data.
(function () {
  const canvas = document.getElementById('investment-background');
  if (!canvas) return;
  const context = canvas.getContext('2d');
  if (!context) return;
  const backdrop = document.createElement('canvas');
  const background = backdrop.getContext('2d');
  if (!background) return;
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  let width = 0, height = 0, frame = 0, lastFrame = 0;
  let series = [];

  function makeSeries(offset, slope, phase) {
    return Array.from({ length: 101 }, (_, index) => {
      const t = index / 100;
      const fluctuation = Math.sin(t * 27 + phase) * .023 + Math.sin(t * 71 + phase) * .012 + Math.sin(t * 139) * .005;
      return { x: width * t, y: height * (offset - slope * t + fluctuation) };
    });
  }
  function trace(ctx, points) {
    ctx.beginPath();
    points.forEach((point, index) => {
      if (index === 0) ctx.moveTo(point.x, point.y);
      else ctx.lineTo(point.x, point.y);
    });
  }
  function drawBackdrop() {
    background.clearRect(0, 0, width, height);
    const glow = background.createRadialGradient(width * .8, height * .6, 0, width * .8, height * .6, width * .7);
    glow.addColorStop(0, '#25434c66');
    glow.addColorStop(1, '#17233200');
    background.fillStyle = glow;
    background.fillRect(0, 0, width, height);

    // A quiet chart grid, kept beneath the hero's central readability mask.
    background.strokeStyle = '#91acc514';
    background.lineWidth = 1;
    const spacing = width < 600 ? 48 : 80;
    background.beginPath();
    for (let x = 0; x <= width; x += spacing) {
      background.moveTo(x, height * .17);
      background.lineTo(x, height * .89);
    }
    for (let y = height * .17; y < height * .9; y += spacing) {
      background.moveTo(0, y);
      background.lineTo(width, y);
    }
    background.stroke();

    // Equal contribution bars suggest the regular cadence of a SIP.
    for (let index = 1; index < 17; index++) {
      const x = width * index / 17;
      const point = series[0][Math.round(index / 17 * 100)];
      const top = Math.max(height * .32, point.y + height * .07);
      const fill = background.createLinearGradient(0, top, 0, height * .9);
      fill.addColorStop(0, '#8fbbca14');
      fill.addColorStop(1, '#8fbbca00');
      background.fillStyle = fill;
      background.fillRect(x - 5, top, 10, height * .9 - top);
    }
    series.forEach((points, index) => {
      trace(background, points);
      if (index === 0) {
        const fill = background.createLinearGradient(0, height * .35, 0, height * .92);
        fill.addColorStop(0, '#a4d6d20d');
        fill.addColorStop(1, '#a4d6d200');
        background.lineTo(width, height * .92);
        background.lineTo(0, height * .92);
        background.closePath();
        background.fillStyle = fill;
        background.fill();
        trace(background, points);
      }
      background.strokeStyle = ['#a4d6d254', '#88a9d52b', '#a5b4cc1f'][index];
      background.lineWidth = index === 0 ? 1.7 : 1;
      background.stroke();
    });
    // Mark recurring purchases along the main path.
    for (let index = 1; index < 12; index++) {
      const point = series[0][Math.round(index / 12 * 100)];
      background.beginPath();
      background.arc(point.x, point.y, 3, 0, Math.PI * 2);
      background.fillStyle = '#a4d6d269';
      background.fill();
      background.beginPath();
      background.arc(point.x, point.y, 8, 0, Math.PI * 2);
      background.strokeStyle = '#a4d6d21f';
      background.stroke();
    }
  }
  function draw(time = 0) {
    context.clearRect(0, 0, width, height);
    context.drawImage(backdrop, 0, 0, width, height);
    const progress = reducedMotion.matches ? .82 : (time / 36000) % 1;
    const position = progress * 100;
    const index = Math.min(99, Math.floor(position));
    const fraction = position - index;
    const start = series[0][index], end = series[0][index + 1];
    const x = start.x + (end.x - start.x) * fraction;
    const y = start.y + (end.y - start.y) * fraction;
    const halo = context.createRadialGradient(x, y, 0, x, y, 22);
    halo.addColorStop(0, '#a4d6d24d');
    halo.addColorStop(1, '#a4d6d200');
    context.fillStyle = halo;
    context.fillRect(x - 22, y - 22, 44, 44);
    context.beginPath();
    context.arc(x, y, 3, 0, Math.PI * 2);
    context.fillStyle = '#c5e5df';
    context.fill();
  }
  function resize() {
    const bounds = canvas.getBoundingClientRect();
    width = bounds.width;
    height = bounds.height;
    const dpr = Math.min(devicePixelRatio || 1, 2);
    canvas.width = backdrop.width = Math.round(width * dpr);
    canvas.height = backdrop.height = Math.round(height * dpr);
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
    background.setTransform(dpr, 0, 0, dpr, 0, 0);
    series = [makeSeries(.81, .45, 0), makeSeries(.86, .32, 1.9), makeSeries(.74, .23, 3.8)];
    drawBackdrop();
    draw();
  }
  function animate(time) {
    if (document.hidden) return;
    if (time - lastFrame > 40) { draw(time); lastFrame = time; }
    frame = requestAnimationFrame(animate);
  }
  function updateMotion() {
    cancelAnimationFrame(frame);
    if (reducedMotion.matches || document.hidden) draw();
    else frame = requestAnimationFrame(animate);
  }
  const observer = new ResizeObserver(resize);
  function start() {
    observer.observe(canvas);
    reducedMotion.addEventListener('change', updateMotion);
    document.addEventListener('visibilitychange', updateMotion);
    resize();
    updateMotion();
  }
  window.addEventListener('pagehide', () => {
    cancelAnimationFrame(frame);
    observer.disconnect();
    reducedMotion.removeEventListener('change', updateMotion);
    document.removeEventListener('visibilitychange', updateMotion);
  });
  window.addEventListener('pageshow', (event) => { if (event.persisted) start(); });
  start();
})();
