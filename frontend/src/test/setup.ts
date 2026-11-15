import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

/**
 * Default to desktop viewport for MUI useMediaQuery (`breakpoints.down("sm")` → matches: false).
 * Tests that need mobile must override window.matchMedia.
 */
if (!window.matchMedia) {
  // jsdom may lack matchMedia entirely
}
Object.defineProperty(window, "matchMedia", {
  writable: true,
  configurable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});
