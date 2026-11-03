document.addEventListener("submit", (event) => {
  const message = event.target.dataset.confirm;
  if (message && !window.confirm(message)) event.preventDefault();
});

(() => {
  const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const items = document.querySelectorAll(".reveal-on-scroll");
  if (!items.length || reduceMotion || !("IntersectionObserver" in window)) return;

  items.forEach((item) => item.classList.add("reveal-ready"));
  const observer = new IntersectionObserver((entries, currentObserver) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        currentObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });
  items.forEach((item) => observer.observe(item));
})();

document.addEventListener("click", async (event) => {
  const button = event.target instanceof Element
    ? event.target.closest("[data-copy-link]")
    : null;
  if (!button) return;
  const input = button.parentElement.querySelector("input");
  if (!input) return;

  try {
    await navigator.clipboard.writeText(input.value);
    button.textContent = "Copied";
  } catch {
    try {
      input.focus();
      input.select();
      const copied = document.execCommand("copy");
      button.textContent = copied ? "Copied" : "Copy failed";
    } catch {
      button.textContent = "Copy failed";
    }
  }
});
