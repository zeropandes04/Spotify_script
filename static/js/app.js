/* app.js — Spotify Transcript Tool frontend */

(function () {
  "use strict";

  // ── Element refs ────────────────────────────────────────────────────────
  const form         = document.getElementById("transcript-form");
  const submitBtn    = document.getElementById("submit-btn");
  const btnText      = submitBtn.querySelector(".btn-text");
  const btnSpinner   = submitBtn.querySelector(".btn-spinner");
  const resultCard   = document.getElementById("result-card");
  const errorCard    = document.getElementById("error-card");
  const errorMsg     = document.getElementById("error-message");
  const transcriptEl = document.getElementById("transcript-output");
  const copyBtn      = document.getElementById("copy-btn");
  const downloadBtn  = document.getElementById("download-btn");
  const formatOpts   = document.querySelectorAll(".format-opt");

  // Episode info
  const epImage  = document.getElementById("ep-image");
  const epShow   = document.getElementById("ep-show");
  const epTitle  = document.getElementById("ep-title");
  const epDate   = document.getElementById("ep-date");
  const epSource = document.getElementById("ep-source");
  const epWords  = document.getElementById("ep-words");
  const epSegs   = document.getElementById("ep-segs");

  // ── State ────────────────────────────────────────────────────────────────
  let lastResult = null;

  // ── Format selector ──────────────────────────────────────────────────────
  formatOpts.forEach(opt => {
    opt.addEventListener("click", () => {
      formatOpts.forEach(o => o.classList.remove("selected"));
      opt.classList.add("selected");
    });
  });

  function getSelectedFormat() {
    const checked = form.querySelector('input[name="format"]:checked');
    return checked ? checked.value : "txt";
  }

  // ── Form submit ──────────────────────────────────────────────────────────
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    await fetchTranscript();
  });

  async function fetchTranscript() {
    const url          = document.getElementById("url").value.trim();
    const clientId     = document.getElementById("client-id").value.trim();
    const clientSecret = document.getElementById("client-secret").value.trim();
    const fmt          = getSelectedFormat();

    // Basic client-side validation
    if (!url) { return showError("Please enter a Spotify episode URL."); }
    if (!clientId) { return showError("Please enter your Spotify Client ID."); }
    if (!clientSecret) { return showError("Please enter your Spotify Client Secret."); }

    setLoading(true);
    hideAll();

    try {
      const res = await fetch("/api/transcript", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, client_id: clientId, client_secret: clientSecret, format: fmt }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || `Server error ${res.status}`);
      }

      lastResult = data;
      showResult(data);
    } catch (err) {
      showError(err.message || "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  }

  // ── Render result ────────────────────────────────────────────────────────
  function showResult(data) {
    // Episode info
    if (data.image) {
      epImage.src = data.image;
      epImage.alt = data.title || "";
      epImage.hidden = false;
    } else {
      epImage.hidden = true;
    }
    epShow.textContent  = data.show  || "";
    epTitle.textContent = data.title || data.episode_id;
    epDate.textContent  = data.date  || "";
    epSource.textContent = sourceLabel(data.source);
    epWords.textContent  = data.words ? `${data.words.toLocaleString()} words` : "";
    epSegs.textContent   = data.segments ? `${data.segments} segments` : "";

    // Transcript
    transcriptEl.textContent = data.content;

    resultCard.hidden = false;
    resultCard.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function sourceLabel(src) {
    if (src === "spotify-native") return "Spotify native";
    if (src === "rss")            return "RSS feed";
    return src || "unknown";
  }

  // ── Copy ─────────────────────────────────────────────────────────────────
  copyBtn.addEventListener("click", async () => {
    if (!lastResult) return;
    try {
      await navigator.clipboard.writeText(lastResult.content);
      const orig = copyBtn.textContent;
      copyBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> Copied!`;
      setTimeout(() => {
        copyBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy`;
      }, 1800);
    } catch {
      // Fallback: select text
      const range = document.createRange();
      range.selectNodeContents(transcriptEl);
      window.getSelection().removeAllRanges();
      window.getSelection().addRange(range);
    }
  });

  // ── Download ─────────────────────────────────────────────────────────────
  downloadBtn.addEventListener("click", async () => {
    if (!lastResult) return;
    try {
      const res = await fetch("/api/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content:    lastResult.content,
          format:     lastResult.format,
          episode_id: lastResult.episode_id,
        }),
      });
      if (!res.ok) throw new Error("Download failed");
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href     = url;
      a.download = `${lastResult.episode_id}.${lastResult.format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      showError(`Download error: ${err.message}`);
    }
  });

  // ── Helpers ──────────────────────────────────────────────────────────────
  function setLoading(on) {
    submitBtn.disabled = on;
    btnText.hidden     = on;
    btnSpinner.hidden  = !on;
  }

  function hideAll() {
    resultCard.hidden = true;
    errorCard.hidden  = true;
    lastResult        = null;
  }

  function showError(msg) {
    errorMsg.textContent = msg;
    errorCard.hidden     = false;
    errorCard.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ── Persist credentials in sessionStorage (convenience, not localStorage) ─
  const clientIdInput     = document.getElementById("client-id");
  const clientSecretInput = document.getElementById("client-secret");

  const savedId     = sessionStorage.getItem("sp_client_id");
  const savedSecret = sessionStorage.getItem("sp_client_secret");
  if (savedId)     clientIdInput.value     = savedId;
  if (savedSecret) clientSecretInput.value = savedSecret;

  clientIdInput.addEventListener("input", () => {
    sessionStorage.setItem("sp_client_id", clientIdInput.value);
  });
  clientSecretInput.addEventListener("input", () => {
    sessionStorage.setItem("sp_client_secret", clientSecretInput.value);
  });

})();
