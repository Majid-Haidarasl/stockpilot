import { StatusChip } from "../../shared/ui/StatusChip";
import { orderStatusLabel } from "./statusLabels";

/** Status cue with text + icon (colour alone is never the only signal). */
export function OrderStatusBadge({ status }: { status: string }) {
  return <StatusChip status={status} label={orderStatusLabel(status)} />;
}
