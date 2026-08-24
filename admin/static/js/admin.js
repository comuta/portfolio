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

function setupMediaUpload() {
  const form = document.querySelector("[data-upload-form]");
  if (!form) return;

  const fileInput = form.querySelector('input[type="file"]');
  const status = document.querySelector("[data-upload-status]");
  const textarea = document.querySelector("[data-markdown-source]");
  const titelbildInput = document.querySelector('input[name="titelbild"]');

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!fileInput.files.length) return;

    const body = new FormData();
    body.append("csrf_token", form.querySelector('input[name="csrf_token"]').value);
    body.append("datei", fileInput.files[0]);

    status.textContent = "Lädt hoch …";
    fetch(form.action, { method: "POST", body })
      .then((resp) => resp.json().then((data) => ({ ok: resp.ok, data })))
      .then(({ ok, data }) => {
        if (!ok) {
          status.textContent = "Fehler: " + (data.error || "Upload fehlgeschlagen.");
          return;
        }
        status.textContent = "";
        const pfad = data.pfad;

        const insertBtn = document.createElement("button");
        insertBtn.type = "button";
        insertBtn.className = "button";
        insertBtn.textContent = pfad + " → in Text einfügen";
        insertBtn.addEventListener("click", () => {
          if (!textarea) return;
          textarea.value += `\n\n![Bildbeschreibung](${pfad})\n`;
          textarea.dispatchEvent(new Event("input"));
        });

        const titelbildBtn = document.createElement("button");
        titelbildBtn.type = "button";
        titelbildBtn.className = "button";
        titelbildBtn.textContent = "Als Titelbild setzen";
        titelbildBtn.addEventListener("click", () => {
          if (titelbildInput) titelbildInput.value = pfad;
        });

        status.append(insertBtn, document.createTextNode(" "), titelbildBtn);
        fileInput.value = "";
      })
      .catch(() => {
        status.textContent = "Fehler beim Hochladen.";
      });
  });
}

document.addEventListener("DOMContentLoaded", setupMediaUpload);
