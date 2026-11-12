/**
 * Idempotency helper: one key per user action.
 * - begin() / startNewAction() → mint a fresh Idempotency-Key
 * - retry() → reuse the same key for the same action
 * - A new user action always calls begin() again (never auto-reuse across actions)
 * No optimistic updates — callers wait for the server response.
 */

export type IdempotentActionState = {
  readonly actionId: string;
  readonly idempotencyKey: string;
  readonly expectedVersion: number | null;
};

export type IdempotentActionController = {
  /** Start a brand-new user action (always a new Idempotency-Key). */
  begin: (expectedVersion?: number | null) => IdempotentActionState;
  /** Retry the current action with the same Idempotency-Key. */
  retry: (expectedVersion?: number | null) => IdempotentActionState;
  /** Current action, if any. */
  current: () => IdempotentActionState | null;
  /** Clear after success or when abandoning the action. */
  clear: () => void;
  /** Headers + body helpers for the active action. */
  buildRequest: (body?: Record<string, unknown>) => {
    headers: Record<string, string>;
    body: Record<string, unknown>;
  };
};

function newKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `idem-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function createIdempotentAction(actionId: string): IdempotentActionController {
  let state: IdempotentActionState | null = null;

  return {
    begin(expectedVersion = null) {
      state = {
        actionId,
        idempotencyKey: newKey(),
        expectedVersion: expectedVersion ?? null,
      };
      return state;
    },
    retry(expectedVersion) {
      if (!state) {
        throw new Error(`No in-flight action to retry for ${actionId}`);
      }
      if (expectedVersion !== undefined) {
        state = { ...state, expectedVersion: expectedVersion ?? null };
      }
      return state;
    },
    current() {
      return state;
    },
    clear() {
      state = null;
    },
    buildRequest(body = {}) {
      if (!state) {
        throw new Error(`Call begin() before buildRequest() for ${actionId}`);
      }
      const payload = { ...body };
      if (state.expectedVersion !== null && payload.expected_version === undefined) {
        payload.expected_version = state.expectedVersion;
      }
      return {
        headers: { "Idempotency-Key": state.idempotencyKey },
        body: payload,
      };
    },
  };
}
