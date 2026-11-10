import createCache from "@emotion/cache";
import { CacheProvider } from "@emotion/react";
import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import type { ReactNode } from "react";
import { prefixer } from "stylis";
import rtlPlugin from "stylis-plugin-rtl";

const rtlCache = createCache({
  key: "muirtl",
  stylisPlugins: [prefixer, rtlPlugin],
});

const theme = createTheme({
  direction: "rtl",
  typography: {
    fontFamily: '"Vazirmatn", "Tahoma", sans-serif',
  },
  palette: {
    mode: "light",
    primary: { main: "#0f4c5c" },
    secondary: { main: "#e36414" },
    background: { default: "#f4f7f8", paper: "#ffffff" },
  },
});

export function AppThemeProvider({ children }: { children: ReactNode }) {
  return (
    <CacheProvider value={rtlCache}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </CacheProvider>
  );
}
