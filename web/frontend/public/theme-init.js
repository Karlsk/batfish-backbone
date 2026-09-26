// Runs before the app and stylesheet load; keep preference semantics in sync with ThemeProvider.
(function () {
  var preference = "system";
  try {
    var saved = localStorage.getItem("batfish-theme-preference");
    if (saved === "light" || saved === "dark") preference = saved;
  } catch (_) {
    /* Storage is optional for appearance. */
  }
  var mode =
    preference === "system"
      ? window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      : preference;
  var root = document.documentElement;
  root.dataset.theme = mode;
  root.style.colorScheme = mode;
  root.style.backgroundColor = mode === "dark" ? "#0a111e" : "#eff3f9";
})();
