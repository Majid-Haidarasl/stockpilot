import type { ThemeOptions } from "@mui/material/styles";

/** Vazirmatn for Persian UI; system UI sans as Latin fallback. */
export const FONT_FAMILY = '"Vazirmatn", "Segoe UI", Tahoma, sans-serif';

export const typography: ThemeOptions["typography"] = {
  fontFamily: FONT_FAMILY,
  h1: { fontWeight: 700, fontSize: "2rem", lineHeight: 1.25 },
  h2: { fontWeight: 700, fontSize: "1.75rem", lineHeight: 1.3 },
  h3: { fontWeight: 700, fontSize: "1.5rem", lineHeight: 1.35 },
  h4: { fontWeight: 700, fontSize: "1.25rem", lineHeight: 1.4 },
  h5: { fontWeight: 700, fontSize: "1.125rem", lineHeight: 1.4 },
  h6: { fontWeight: 600, fontSize: "1rem", lineHeight: 1.45 },
  subtitle1: { fontWeight: 600, fontSize: "0.95rem", lineHeight: 1.5 },
  subtitle2: { fontWeight: 600, fontSize: "0.875rem", lineHeight: 1.5 },
  body1: { fontWeight: 400, fontSize: "0.95rem", lineHeight: 1.6 },
  body2: { fontWeight: 400, fontSize: "0.875rem", lineHeight: 1.55 },
  button: { fontWeight: 600, fontSize: "0.875rem", textTransform: "none" },
  caption: { fontWeight: 400, fontSize: "0.75rem", lineHeight: 1.4 },
  overline: { fontWeight: 600, fontSize: "0.7rem", letterSpacing: "0.04em" },
};
