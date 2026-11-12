/** RFC 9457 Problem Details as returned by StockPilot (`application/problem+json`). */

export type StockShortfall = {
  sku: string;
  requested: number;
  available: number;
  product_name?: string;
};

export type ApiProblem = {
  type?: string;
  title?: string;
  status: number;
  code: string;
  detail?: string;
  errors?: Array<Record<string, unknown>>;
};

export class ApiProblemError extends Error {
  readonly problem: ApiProblem;

  constructor(problem: ApiProblem) {
    super(problem.detail ?? problem.title ?? problem.code);
    this.name = "ApiProblemError";
    this.problem = problem;
  }
}

export function isApiProblemError(error: unknown): error is ApiProblemError {
  return error instanceof ApiProblemError;
}

export async function parseApiProblem(response: Response): Promise<ApiProblem> {
  let body: Record<string, unknown> = {};
  try {
    body = (await response.json()) as Record<string, unknown>;
  } catch {
    // non-JSON body
  }
  const code =
    typeof body.code === "string"
      ? body.code
      : response.status === 403
        ? "FORBIDDEN"
        : response.status === 404
          ? "NOT_FOUND"
          : response.status === 422
            ? "VALIDATION_ERROR"
            : "HTTP_ERROR";
  return {
    type: typeof body.type === "string" ? body.type : undefined,
    title: typeof body.title === "string" ? body.title : undefined,
    status: response.status,
    code,
    detail: typeof body.detail === "string" ? body.detail : undefined,
    errors: Array.isArray(body.errors) ? (body.errors as Array<Record<string, unknown>>) : undefined,
  };
}
