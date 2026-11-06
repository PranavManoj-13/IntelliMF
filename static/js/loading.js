(function () {
  const loader = document.getElementById('page-loader');
  if (!loader) return;
  function hideLoader() {
    loader.classList.remove('is-visible');
    loader.setAttribute('aria-hidden', 'true');
  }
  function showLoader() {
    loader.classList.add('is-visible');
    loader.setAttribute('aria-hidden', 'false');
  }
  // Delay the overlay briefly so anchor navigation and quick responses stay immediate.
  function queueLoader(event) {
    setTimeout(() => { if (!event.defaultPrevented) showLoader(); }, 180);
  }
  document.addEventListener('click', (event) => {
    const link = event.target.closest('a[href]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || link.target === '_blank' || link.hasAttribute('download')) return;
    const target = new URL(link.href, location.href);
    if (target.origin !== location.origin || !['http:', 'https:'].includes(target.protocol)) return;
    if (target.pathname === location.pathname && target.search === location.search) return;
    queueLoader(event);
  });
  document.addEventListener('submit', (event) => { if (event.target.method !== 'dialog') queueLoader(event); });
  window.addEventListener('pageshow', hideLoader);
})();
