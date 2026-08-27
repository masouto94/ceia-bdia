export type Theme = "light" | "dark";

export const THEME_STORAGE_KEY = "student-project-theme";

const systemTheme = (): Theme =>
  window.matchMedia?.("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";

export const getInitialTheme = (): Theme => {
  const saved = localStorage.getItem(THEME_STORAGE_KEY);
  return saved === "light" || saved === "dark" ? saved : systemTheme();
};

export const applyTheme = (theme: Theme) => {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
};

export const initializeTheme = () => applyTheme(getInitialTheme());
