document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".metadata-row input").forEach((input) => {
    input.addEventListener("change", () => {
      const row = input.closest(".metadata-row");
      if (row) {
        row.classList.add("metadata-row-dirty");
      }
    });
  });
});
