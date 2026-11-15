/** Spacing, radius, elevation, and motion tokens. */

export const SPACING_UNIT = 8;

export const RADIUS = {
  sm: 6,
  md: 10,
  lg: 14,
} as const;

export const SHADOWS = {
  light: [
    "none",
    "0 1px 2px rgba(15, 23, 42, 0.06)",
    "0 2px 8px rgba(15, 23, 42, 0.08)",
    "0 4px 16px rgba(15, 23, 42, 0.1)",
    "0 8px 24px rgba(15, 23, 42, 0.12)",
  ],
  dark: [
    "none",
    "0 1px 2px rgba(0, 0, 0, 0.25)",
    "0 2px 8px rgba(0, 0, 0, 0.3)",
    "0 4px 16px rgba(0, 0, 0, 0.35)",
    "0 8px 24px rgba(0, 0, 0, 0.4)",
  ],
} as const;

export const MOTION = {
  durationMs: 180,
  easing: "cubic-bezier(0.4, 0, 0.2, 1)",
} as const;

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function transition(
  properties: string[] = ["background-color", "color", "border-color", "box-shadow"],
): string {
  if (prefersReducedMotion()) return "none";
  return properties
    .map((p) => `${p} ${MOTION.durationMs}ms ${MOTION.easing}`)
    .join(", ");
}
