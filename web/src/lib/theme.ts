export type Theme = "dark" | "light";

const KEY = "fintwin-theme";

/** The person's stored choice. Dark is the default; storage may be unavailable, which is not an error. */
export function readTheme(): Theme {
  try {
    return localStorage.getItem(KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

/** The tokens in styles.css switch on the root element's data-theme. */
export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    // The choice still holds for this visit.
  }
}
