document.addEventListener("submit", (event) => {
  const message = event.target.getAttribute("data-confirm");
  if (message && !window.confirm(message)) {
    event.preventDefault();
  }
});

function setupMarkdownPreview() {
  const textarea = document.querySelector("[data-markdown-source]");
  const preview = document.querySelector("[data-markdown-preview]");
  const csrfInput = document.querySelector('input[name="csrf_token"]');
  if (!textarea || !preview || !csrfInput) return;

  let timer = null;

  const render = () => {
    fetch("/vorschau", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ csrf_token: csrfInput.value, inhalt: textarea.value }),
    })
      .then((resp) => resp.text())
      .then((html) => {
        // Same sanitized renderer the public site uses (bleach-cleaned server-side).
        preview.innerHTML = html;
      })
      .catch(() => {});
  };

  textarea.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(render, 400);
  });

  render();
}

document.addEventListener("DOMContentLoaded", setupMarkdownPreview);
