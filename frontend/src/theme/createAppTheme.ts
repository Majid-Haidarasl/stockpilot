import { createTheme } from "@mui/material/styles";
import { createComponentOverrides } from "./components";
import { activePreset, SEMANTIC, SURFACES } from "./palette";
import { RADIUS, SPACING_UNIT } from "./shape";
import { typography } from "./typography";

export function createAppTheme(mode: "light" | "dark") {
  const preset = activePreset();
  const surfaces = SURFACES[mode];
  const primaryMain = mode === "light" ? preset.lightPrimary : preset.darkPrimary;
  const primaryContrast =
    mode === "light" ? preset.lightPrimaryContrast : preset.darkPrimaryContrast;

  return createTheme({
    direction: "rtl",
    spacing: SPACING_UNIT,
    shape: { borderRadius: RADIUS.md },
    typography,
    palette: {
      mode,
      primary: {
        main: primaryMain,
        contrastText: primaryContrast,
      },
      secondary: {
        main: preset.accent,
        contrastText: preset.accentContrast,
      },
      success: { main: SEMANTIC.success[mode] },
      warning: { main: SEMANTIC.warning[mode] },
      error: { main: SEMANTIC.error[mode] },
      info: { main: SEMANTIC.info[mode] },
      background: {
        default: surfaces.default,
        paper: surfaces.paper,
      },
      text: {
        primary: surfaces.textPrimary,
        secondary: surfaces.textSecondary,
      },
      divider: surfaces.divider,
    },
    components: createComponentOverrides(mode),
  });
}
