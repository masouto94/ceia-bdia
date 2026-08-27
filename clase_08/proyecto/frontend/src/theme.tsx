import { type ReactNode, createContext, useContext, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { Button } from "./components/ui/button";
import {
  applyTheme,
  getInitialTheme,
  THEME_STORAGE_KEY,
  type Theme,
} from "./theme-core";

const ThemeContext = createContext<{ theme: Theme; toggle: () => void } | null>(
  null,
);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(getInitialTheme);
  applyTheme(theme);
  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    localStorage.setItem(THEME_STORAGE_KEY, next);
    setTheme(next);
  };
  return (
    <ThemeContext.Provider value={{ theme, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function ThemeToggle() {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("Falta el proveedor de tema");
  const isDark = value.theme === "dark";
  return (
    <Button
      className="theme-toggle"
      variant="outline"
      type="button"
      aria-label={isDark ? "Activar tema claro" : "Activar tema oscuro"}
      aria-pressed={isDark}
      onClick={value.toggle}
    >
      {isDark ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
    </Button>
  );
}
