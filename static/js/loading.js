(function () {
  function showLoader() {
    const loader = document.getElementById("page-loader");
    if (loader) {
      loader.classList.add("is-visible");
      loader.setAttribute("aria-hidden", "false");
    }
  }

  function hideLoader() {
    const loader = document.getElementById("page-loader");
    if (loader) {
      loader.classList.remove("is-visible");
      loader.setAttribute("aria-hidden", "true");
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    hideLoader();

    document.querySelectorAll("a[href]").forEach((link) => {
      link.addEventListener("click", (event) => {
        const href = link.getAttribute("href");
        if (!href || href.startsWith("#") || link.target === "_blank" || event.metaKey || event.ctrlKey) {
          return;
        }
        showLoader();
      });
    });

    document.querySelectorAll("form").forEach((form) => {
      form.addEventListener("submit", () => {
        showLoader();
      });
    });

    window.addEventListener("pageshow", () => {
      hideLoader();
    });
  });
})();
