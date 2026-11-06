(function () {
  const header = document.getElementById('site-header');
  const toggle = document.getElementById('menu-toggle');
  const navigation = document.getElementById('primary-navigation');
  const reveal = document.getElementById('nav-reveal');
  if (!header || !toggle || !navigation || !reveal) return;
  let lastY = window.scrollY;
  let queued = false;
  function showHeader() {
    header.classList.remove('is-hidden');
    reveal.classList.remove('is-available');
    reveal.tabIndex = -1;
  }
  function closeMenu() {
    header.classList.remove('menu-open');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-label', 'Open navigation');
  }
  toggle.addEventListener('click', () => {
    const open = toggle.getAttribute('aria-expanded') !== 'true';
    header.classList.toggle('menu-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    showHeader();
  });
  navigation.addEventListener('click', (event) => {
    if (event.target.closest('a')) closeMenu();
  });
  document.addEventListener('click', (event) => {
    if (!header.contains(event.target)) closeMenu();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && header.classList.contains('menu-open')) {
      closeMenu();
      toggle.focus();
    }
  });
  header.addEventListener('focusin', showHeader);
  reveal.addEventListener('pointerenter', showHeader);
  reveal.addEventListener('click', () => { showHeader(); header.querySelector('a').focus(); });
  window.addEventListener('scroll', () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      const y = window.scrollY;
      if (y < 120 || y < lastY - 3 || header.contains(document.activeElement) || header.classList.contains('menu-open')) showHeader();
      else if (y > lastY + 3) {
        header.classList.add('is-hidden');
        reveal.classList.add('is-available');
        reveal.tabIndex = 0;
      }
      lastY = y;
      queued = false;
    });
  }, { passive: true });
  window.matchMedia('(min-width: 801px)').addEventListener('change', closeMenu);
})();
