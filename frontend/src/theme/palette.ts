/** Color presets and semantic tokens. Swap primary via ACTIVE_PRIMARY_PRESET only. */

export type PrimaryPresetId = "teal" | "navy" | "blue";

/** Active brand preset — change this one constant to swap the whole primary palette. */
export const ACTIVE_PRIMARY_PRESET: PrimaryPresetId = "navy";

export type PrimaryPreset = {
  id: PrimaryPresetId;
  /** Light-mode brand primary (filled buttons, focus ring base). */
  lightPrimary: string;
  lightPrimaryContrast: string;
  /** Dark-mode interactive primary (must stay readable on dark surfaces). */
  darkPrimary: string;
  darkPrimaryContrast: string;
  accent: string;
  accentContrast: string;
};

export const PRIMARY_PRESETS: Record<PrimaryPresetId, PrimaryPreset> = {
  teal: {
    id: "teal",
    lightPrimary: "#0F766E",
    lightPrimaryContrast: "#FFFFFF",
    darkPrimary: "#2DD4BF",
    darkPrimaryContrast: "#042F2E",
    accent: "#0369A1",
    accentContrast: "#FFFFFF",
  },
  navy: {
    id: "navy",
    lightPrimary: "#0F172A",
    lightPrimaryContrast: "#FFFFFF",
    darkPrimary: "#38BDF8",
    darkPrimaryContrast: "#0F172A",
    accent: "#0369A1",
    accentContrast: "#FFFFFF",
  },
  blue: {
    id: "blue",
    lightPrimary: "#1E40AF",
    lightPrimaryContrast: "#FFFFFF",
    darkPrimary: "#60A5FA",
    darkPrimaryContrast: "#0F172A",
    accent: "#D97706",
    accentContrast: "#0F172A",
  },
};

export function activePreset(): PrimaryPreset {
  return PRIMARY_PRESETS[ACTIVE_PRIMARY_PRESET];
}

/** Semantic colors tuned for ≥4.5:1 text contrast on matching surfaces. */
export const SEMANTIC = {
  success: { light: "#15803D", dark: "#4ADE80" },
  warning: { light: "#B45309", dark: "#FBBF24" },
  error: { light: "#DC2626", dark: "#F87171" },
  info: { light: "#0369A1", dark: "#38BDF8" },
} as const;

export type OrderStatusCode =
  | "DRAFT"
  | "RESERVED"
  | "CONFIRMED"
  | "SHIPPED"
  | "CANCELLED"
  | "EXPIRED";

export type OrderStatusTone = {
  /** Chip background */
  bg: string;
  /** Chip text + icon (≥4.5:1 on bg) */
  fg: string;
};

export const ORDER_STATUS_TONES: Record<
  OrderStatusCode,
  { light: OrderStatusTone; dark: OrderStatusTone }
> = {
  DRAFT: {
    light: { bg: "#E2E8F0", fg: "#1E293B" },
    dark: { bg: "#334155", fg: "#E2E8F0" },
  },
  RESERVED: {
    light: { bg: "#FEF3C7", fg: "#92400E" },
    dark: { bg: "#78350F", fg: "#FDE68A" },
  },
  CONFIRMED: {
    light: { bg: "#DBEAFE", fg: "#1E3A8A" },
    dark: { bg: "#1E3A8A", fg: "#BFDBFE" },
  },
  SHIPPED: {
    light: { bg: "#DCFCE7", fg: "#166534" },
    dark: { bg: "#14532D", fg: "#BBF7D0" },
  },
  CANCELLED: {
    light: { bg: "#FEE2E2", fg: "#991B1B" },
    dark: { bg: "#7F1D1D", fg: "#FECACA" },
  },
  EXPIRED: {
    light: { bg: "#F1F5F9", fg: "#475569" },
    dark: { bg: "#475569", fg: "#E2E8F0" },
  },
};

/** Out-of-stock chip tones (≥4.5:1). */
export const OUT_OF_STOCK_TONES: { light: OrderStatusTone; dark: OrderStatusTone } = {
  light: { bg: "#FEE2E2", fg: "#991B1B" },
  dark: { bg: "#7F1D1D", fg: "#FECACA" },
};

export function orderStatusTone(
  status: string,
  mode: "light" | "dark",
): OrderStatusTone {
  const key = status as OrderStatusCode;
  const entry = ORDER_STATUS_TONES[key];
  if (!entry) {
    return mode === "light"
      ? { bg: "#E2E8F0", fg: "#1E293B" }
      : { bg: "#334155", fg: "#F8FAFC" };
  }
  return entry[mode];
}

/**
 * Soft Slate Sky dark surfaces — soft deep navy bg, lighter elevated cards,
 * sky accent primary (see navy.darkPrimary). Not pure black.
 */
export const SURFACES = {
  light: {
    default: "#F8FAFC",
    paper: "#FFFFFF",
    textPrimary: "#020617",
    textSecondary: "#475569",
    divider: "#E2E8F0",
    /** Slightly distinct chrome (sidebar / app bar). */
    chrome: "#FFFFFF",
    borderSubtle: "rgba(15, 23, 42, 0.08)",
    navActiveTint: "rgba(15, 23, 42, 0.06)",
  },
  dark: {
    default: "#0B1220",
    paper: "#1E293B",
    textPrimary: "#E2E8F0",
    textSecondary: "#94A3B8",
    divider: "rgba(148, 163, 184, 0.15)",
    chrome: "#111827",
    borderSubtle: "rgba(148, 163, 184, 0.15)",
    navActiveTint: "rgba(56, 189, 248, 0.12)",
  },
} as const;
