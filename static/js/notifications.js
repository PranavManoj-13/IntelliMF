(function () {
  document.querySelectorAll('.toast').forEach(toast => {
    const close = toast.querySelector('.toast-close');
    let timer;
    const dismiss = () => { clearTimeout(timer); toast.remove(); };
    const schedule = () => {
      clearTimeout(timer);
      if (!toast.classList.contains('toast-error')) timer = setTimeout(dismiss, 6000);
    };
    close.addEventListener('click', dismiss);
    toast.addEventListener('mouseenter', () => clearTimeout(timer));
    toast.addEventListener('mouseleave', schedule);
    toast.addEventListener('focusin', () => clearTimeout(timer));
    toast.addEventListener('focusout', schedule);
    schedule();
  });
})();
