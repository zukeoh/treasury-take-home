(() => {
  const root = document.documentElement;
  const button = document.querySelector("#theme-toggle");
  if (!button) return;

  const applyTheme = (theme) => {
    root.dataset.theme = theme;
    const nextTheme = theme === "dark" ? "light" : "dark";
    const label = `Switch To ${nextTheme === "dark" ? "Dark" : "Light"} Mode`;
    button.setAttribute("aria-label", label);
    button.title = label;
  };

  button.addEventListener("click", () => {
    const theme = root.dataset.theme === "dark" ? "light" : "dark";
    localStorage.setItem("ttb-color-theme", theme);
    applyTheme(theme);
  });

  window.addEventListener("storage", (event) => {
    if (event.key === "ttb-color-theme" && ["light", "dark"].includes(event.newValue)) {
      applyTheme(event.newValue);
    }
  });

  applyTheme(root.dataset.theme === "dark" ? "dark" : "light");
})();
