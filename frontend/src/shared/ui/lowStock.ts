/** True when sellable quantity is at or below the warning threshold. */
export function isLowStock(available: number, threshold: number): boolean {
  return available <= threshold;
}
