// Chromium fires `beforeinstallprompt` once per page load, often before React
// hydrates. Loaded only by the dashboard layout (the one place the install
// card mounts, since preventDefault() suppresses Chrome's own offer) — it
// stashes the event for components/shell/install-prompt.tsx to pick up.
(function () {
  var self = document.currentScript;
  window.addEventListener("beforeinstallprompt", function (e) {
    // After a client-side navigation out of the dashboard, React removes this
    // <script> element; stand down so Chrome's native offer comes back.
    if (self && !self.isConnected) return;
    e.preventDefault();
    window.__ownixInstallPrompt = e;
  });
})();
