import { isApiProblemError } from "./api/problem";
import { mapApiError } from "./api/mapApiError";

export type PageStatus =
  | { kind: "loading" }
  | { kind: "empty" }
  | { kind: "error"; message: string }
  | { kind: "forbidden"; message: string }
  | { kind: "ready" };

export type QueryFailureStatus = Extract<PageStatus, { kind: "error" | "forbidden" }>;

export function statusFromQueryError(error: unknown): QueryFailureStatus {
  if (isApiProblemError(error) && error.problem.code === "FORBIDDEN") {
    return { kind: "forbidden", message: mapApiError(error) };
  }
  return { kind: "error", message: mapApiError(error) };
}
