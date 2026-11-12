/** Scenario 11 — clear Persian denial when inventory write is not allowed. */
export const INVENTORY_WRITE_DENIED_MESSAGE =
  "اجازه تغییر موجودی را ندارید. فقط مدیر و کاربر انبار می‌توانند رسید یا تعدیل ثبت کنند.";

export function canWriteInventory(role: string): boolean {
  return role === "admin" || role === "warehouse";
}
