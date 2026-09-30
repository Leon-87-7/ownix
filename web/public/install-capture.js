// Chromium fires `beforeinstallprompt` once per page load, often before React
// hydrates. Loaded only by the dashboard layout (the one place the install
// card mounts, since preventDefault() suppresses Chrome's own offer) — it
// stashes the event for components/shell/install-prompt.tsx to pick up.
window.addEventListener("beforeinstallprompt", function (e) {
  e.preventDefault();
  window.__ownixInstallPrompt = e;
});
