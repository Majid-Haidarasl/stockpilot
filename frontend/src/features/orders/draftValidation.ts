/** Persian validation for draft order forms (no money → number coercion). */

export type DraftLineInput = {
  productId: string;
  quantity: string;
};

export type DraftFormInput = {
  customerId: string;
  lines: DraftLineInput[];
};

export type DraftFormErrors = {
  customerId?: string;
  lines?: string;
  lineErrors?: Array<{ productId?: string; quantity?: string }>;
};

const MAX_LINES = 20;
const MAX_QTY = 100_000;

export function validateDraftForm(input: DraftFormInput): DraftFormErrors {
  const errors: DraftFormErrors = {};
  if (!input.customerId.trim()) {
    errors.customerId = "انتخاب مشتری الزامی است.";
  }
  if (input.lines.length === 0) {
    errors.lines = "حداقل یک سطر کالا لازم است.";
    return errors;
  }
  if (input.lines.length > MAX_LINES) {
    errors.lines = `حداکثر ${MAX_LINES} سطر کالا مجاز است.`;
  }

  const seen = new Set<string>();
  const lineErrors: Array<{ productId?: string; quantity?: string }> = [];
  let hasLineError = false;

  for (const line of input.lines) {
    const row: { productId?: string; quantity?: string } = {};
    if (!line.productId.trim()) {
      row.productId = "کالا را انتخاب کنید.";
      hasLineError = true;
    } else if (seen.has(line.productId)) {
      row.productId = "هر کالا فقط یک‌بار می‌تواند در سفارش باشد.";
      hasLineError = true;
    } else {
      seen.add(line.productId);
    }

    const qty = line.quantity.trim();
    if (!/^\d+$/.test(qty) || Number(qty) < 1) {
      row.quantity = "تعداد باید عدد صحیح مثبت باشد.";
      hasLineError = true;
    } else if (Number(qty) > MAX_QTY) {
      row.quantity = `تعداد هر سطر حداکثر ${MAX_QTY.toLocaleString("fa-IR")} است.`;
      hasLineError = true;
    }
    lineErrors.push(row);
  }

  if (hasLineError) {
    errors.lineErrors = lineErrors;
  }
  return errors;
}

export function hasDraftErrors(errors: DraftFormErrors): boolean {
  return Boolean(errors.customerId || errors.lines || errors.lineErrors?.some((r) => r.productId || r.quantity));
}
