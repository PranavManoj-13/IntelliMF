(function () {
  const storageKey = "intellimf-theme";

  function applyTheme(theme) {
    document.body.dataset.theme = theme;
    const toggle = document.getElementById("theme-toggle");
    if (toggle) {
      toggle.setAttribute("aria-label", `Switch to ${theme === "dark" ? "light" : "dark"} mode`);
      toggle.dataset.theme = theme;
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const saved = localStorage.getItem(storageKey);
    const preferredDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    const initialTheme = saved || (preferredDark ? "dark" : "light");
    applyTheme(initialTheme);

    const toggle = document.getElementById("theme-toggle");
    if (!toggle) {
      return;
    }

    toggle.addEventListener("click", () => {
      const nextTheme = document.body.dataset.theme === "dark" ? "light" : "dark";
      localStorage.setItem(storageKey, nextTheme);
      applyTheme(nextTheme);
    });
  });
})();
