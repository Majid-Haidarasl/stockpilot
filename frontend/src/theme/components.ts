import type { Theme } from "@mui/material/styles";
import type { Components } from "@mui/material/styles";
import { SURFACES } from "./palette";
import { MOTION, RADIUS, SHADOWS, prefersReducedMotion, transition } from "./shape";

export function createComponentOverrides(mode: "light" | "dark"): Components<Theme> {
  const focusRing = "3px solid var(--sp-focus-ring)";
  const surfaces = SURFACES[mode];
  const softShadow = mode === "light" ? SHADOWS.light[2] : SHADOWS.dark[2];

  return {
    MuiCssBaseline: {
      styleOverrides: {
        ":root": {
          "--sp-focus-ring": mode === "light" ? "#0369A1" : "#38BDF8",
          "--sp-chrome": surfaces.chrome,
          "--sp-border-subtle": surfaces.borderSubtle,
          "--sp-nav-active-tint": surfaces.navActiveTint,
        },
        "*:focus-visible": {
          outline: focusRing,
          outlineOffset: "2px",
        },
        "@media (prefers-reduced-motion: reduce)": {
          "*, *::before, *::after": {
            animationDuration: "0.01ms !important",
            animationIterationCount: "1 !important",
            transitionDuration: "0.01ms !important",
            scrollBehavior: "auto !important",
          },
        },
        body: {
          transition: prefersReducedMotion()
            ? "none"
            : `background-color ${MOTION.durationMs}ms ${MOTION.easing}`,
        },
      },
    },
    MuiButtonBase: {
      defaultProps: {
        disableRipple: prefersReducedMotion(),
      },
      styleOverrides: {
        root: {
          "&.Mui-focusVisible": {
            outline: focusRing,
            outlineOffset: "2px",
          },
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: RADIUS.md,
          minHeight: 40,
          transition: transition(["background-color", "color", "border-color", "box-shadow"]),
        },
        contained: {
          boxShadow: "none",
          "&:hover": { boxShadow: "none" },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: RADIUS.lg,
          border: "1px solid",
          borderColor: "divider",
          boxShadow: "none",
        },
      },
    },
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          backgroundImage: "none",
          borderRadius: RADIUS.md,
        },
        outlined: {
          borderColor: "divider",
          boxShadow: softShadow,
        },
      },
    },
    MuiTextField: {
      defaultProps: {
        size: "small",
        variant: "outlined",
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: RADIUS.md,
          transition: transition(["border-color", "box-shadow"]),
        },
      },
    },
    MuiSelect: {
      defaultProps: { size: "small" },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: RADIUS.lg,
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: RADIUS.sm,
          fontWeight: 600,
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: RADIUS.md,
        },
      },
    },
    MuiTabs: {
      styleOverrides: {
        indicator: {
          height: 3,
          borderRadius: 3,
        },
      },
    },
    MuiTooltip: {
      defaultProps: {
        arrow: true,
        enterDelay: 400,
      },
    },
    MuiSnackbar: {
      defaultProps: {
        anchorOrigin: { vertical: "bottom", horizontal: "left" },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          "& .MuiTableCell-head": {
            fontWeight: 700,
          },
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          transition: transition(["background-color"]),
          "&:nth-of-type(even)": {
            backgroundColor: mode === "light" ? "rgba(15, 23, 42, 0.02)" : "rgba(148, 163, 184, 0.04)",
          },
          "&:hover": {
            backgroundColor: mode === "light" ? "rgba(15, 23, 42, 0.04)" : "rgba(148, 163, 184, 0.08)",
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderColor: "divider",
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          borderLeft: "1px solid",
          borderRight: "none",
          borderColor: "divider",
          backgroundImage: "none",
          backgroundColor: surfaces.chrome,
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
          backgroundColor: surfaces.chrome,
        },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: RADIUS.md,
          marginInline: 8,
          transition: transition(["background-color", "color"]),
          "&.Mui-selected": {
            backgroundColor: surfaces.navActiveTint,
            "&:hover": {
              backgroundColor: surfaces.navActiveTint,
            },
          },
        },
      },
    },
  };
}
