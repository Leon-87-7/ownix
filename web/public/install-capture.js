// Chromium fires `beforeinstallprompt` once per page load, often before React
// hydrates. Loaded synchronously in the root layout's <head> so it registers
// during parse; stashes the event for components/shell/install-prompt.tsx.
//
// preventDefault() suppresses Chrome's own install offer, so only do it on
// dashboard routes, where the install card replaces that offer. The path is
// checked when the event fires, so client-side navigation to a public route
// (/, /privacy, /intake/share, ...) leaves Chrome's offer alone. Keep this list
// in sync with app/(dashboard) — install-prompt.test.tsx fails if it drifts.
(function () {
  var DASHBOARD =
    /^\/(?:(?:feed|brain|controls|doc-parser|jobs|newsletter-digest|prompts|spaces)(?:\/|$)|intake\/?$)/;
  window.addEventListener("beforeinstallprompt", function (e) {
    if (!DASHBOARD.test(window.location.pathname)) return;
    e.preventDefault();
    window.__ownixInstallPrompt = e;
  });
})();
