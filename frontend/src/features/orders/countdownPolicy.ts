/** Pure helper: local countdown never decides confirm eligibility. */
export function confirmEnabledByCountdown(remainingMs: number): boolean {
  void remainingMs;
  return true;
}
