import { toPersianDigits } from "../money";
import { isApiProblemError, type ApiProblem, type StockShortfall } from "./problem";

export type MapApiErrorOptions = {
  /** Map SKU → product title when the API only returns SKU in shortfalls. */
  titleBySku?: Record<string, string>;
};

function asShortfalls(
  errors: Array<Record<string, unknown>> | undefined,
  titleBySku?: Record<string, string>,
): StockShortfall[] {
  if (!errors) return [];
  return errors.flatMap((row) => {
    if (typeof row.sku !== "string") return [];
    const requested = Number(row.requested);
    const available = Number(row.available);
    if (!Number.isFinite(requested) || !Number.isFinite(available)) return [];
    const product_name =
      typeof row.product_name === "string"
        ? row.product_name
        : titleBySku?.[row.sku];
    return [{ sku: row.sku, requested, available, product_name }];
  });
}

function formatStockMessage(shortfalls: StockShortfall[]): string {
  if (shortfalls.length === 0) {
    return "موجودی کافی نیست.";
  }
  return shortfalls
    .map((item) => {
      const name = item.product_name?.trim() || item.sku;
      return `موجودی «${name}» کافی نیست (قابل فروش: ${toPersianDigits(String(item.available))}).`;
    })
    .join(" ");
}

export function mapApiProblem(
  problem: ApiProblem,
  options: MapApiErrorOptions = {},
): string {
  switch (problem.code) {
    case "INSUFFICIENT_STOCK":
      return formatStockMessage(asShortfalls(problem.errors, options.titleBySku));
    case "VERSION_CONFLICT":
      return "نسخه داده تغییر کرده است. صفحه را تازه کنید و دوباره تلاش کنید.";
    case "FORBIDDEN":
      return "اجازه انجام این کار را ندارید.";
    case "NOT_FOUND":
      return "مورد درخواستی یافت نشد.";
    case "VALIDATION_ERROR":
      return problem.detail
        ? `اطلاعات واردشده نامعتبر است: ${problem.detail}`
        : "اطلاعات واردشده نامعتبر است.";
    case "RESERVATION_EXPIRED":
      return "مهلت رزرو به پایان رسیده است.";
    case "IDEMPOTENCY_KEY_REUSED":
      return "این درخواست با کلید تکراری و بدنه متفاوت ارسال شده است.";
    case "IDEMPOTENCY_IN_PROGRESS":
      return "درخواست قبلی هنوز در حال پردازش است. کمی بعد دوباره تلاش کنید.";
    case "NETWORK_ERROR":
      return "ارتباط با سرور برقرار نشد. اتصال اینترنت را بررسی کنید.";
    default:
      return problem.detail ?? problem.title ?? "خطای ناشناخته رخ داد.";
  }
}

export function mapApiError(error: unknown, options: MapApiErrorOptions = {}): string {
  if (isApiProblemError(error)) {
    return mapApiProblem(error.problem, options);
  }
  if (error instanceof TypeError) {
    return mapApiProblem({ status: 0, code: "NETWORK_ERROR" }, options);
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "خطای ناشناخته رخ داد.";
}
