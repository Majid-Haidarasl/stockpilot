const LABELS: Record<string, string> = {
  DRAFT: "پیش‌نویس",
  RESERVED: "رزروشده",
  CONFIRMED: "تأییدشده",
  SHIPPED: "ارسال‌شده",
  CANCELLED: "لغوشده",
  EXPIRED: "منقضی‌شده",
};

export function orderStatusLabel(status: string): string {
  return LABELS[status] ?? status;
}
