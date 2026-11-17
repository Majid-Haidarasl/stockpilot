/** Persian labels for order-lifecycle notification types. */

const LABELS: Record<string, string> = {
  OrderReserved: "سفارش رزرو شد",
  OrderConfirmed: "سفارش تأیید شد",
  OrderCancelled: "سفارش لغو شد",
  OrderShipped: "سفارش ارسال شد",
  OrderExpired: "رزرو منقضی شد",
};

export function notificationTypeLabel(type: string): string {
  return LABELS[type] ?? type;
}
