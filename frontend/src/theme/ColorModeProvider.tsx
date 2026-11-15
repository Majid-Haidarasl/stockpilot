import createCache from "@emotion/cache";
import { CacheProvider } from "@emotion/react";
import { CssBaseline, ThemeProvider } from "@mui/material";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { prefixer } from "stylis";
import rtlPlugin from "stylis-plugin-rtl";
import { createAppTheme } from "./createAppTheme";
import "./fonts";

const COLOR_MODE_KEY = "stockpilot.colorMode";

export type ColorMode = "light" | "dark";

type ColorModeContextValue = {
  mode: ColorMode;
  toggleColorMode: () => void;
  setColorMode: (mode: ColorMode) => void;
};

const ColorModeContext = createContext<ColorModeContextValue | null>(null);

const rtlCache = createCache({
  key: "muirtl",
  stylisPlugins: [prefixer, rtlPlugin],
});

function readStoredMode(): ColorMode | null {
  try {
    const raw = localStorage.getItem(COLOR_MODE_KEY);
    if (raw === "light" || raw === "dark") return raw;
  } catch {
    /* ignore */
  }
  return null;
}

function systemPrefersDark(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function resolveInitialMode(): ColorMode {
  return readStoredMode() ?? (systemPrefersDark() ? "dark" : "light");
}

export function AppThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ColorMode>(() => resolveInitialMode());

  useEffect(() => {
    try {
      localStorage.setItem(COLOR_MODE_KEY, mode);
    } catch {
      /* ignore */
    }
  }, [mode]);

  const setColorMode = useCallback((next: ColorMode) => {
    setModeState(next);
  }, []);

  const toggleColorMode = useCallback(() => {
    setModeState((prev) => (prev === "light" ? "dark" : "light"));
  }, []);

  const theme = useMemo(() => createAppTheme(mode), [mode]);

  const ctx = useMemo(
    () => ({ mode, toggleColorMode, setColorMode }),
    [mode, toggleColorMode, setColorMode],
  );

  return (
    <ColorModeContext.Provider value={ctx}>
      <CacheProvider value={rtlCache}>
        <ThemeProvider theme={theme}>
          <CssBaseline />
          {children}
        </ThemeProvider>
      </CacheProvider>
    </ColorModeContext.Provider>
  );
}

export function useColorMode(): ColorModeContextValue {
  const ctx = useContext(ColorModeContext);
  if (!ctx) {
    throw new Error("useColorMode must be used within AppThemeProvider");
  }
  return ctx;
}

export { COLOR_MODE_KEY };
