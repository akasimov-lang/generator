// Bound the whole authentication request, including reading its response body.
export const AUTH_TIMEOUT_MS = 25_000;

export class AuthTimeoutError extends Error {}

export function isTemporaryAuthError(error: unknown): boolean {
  if (error instanceof AuthTimeoutError || error instanceof TypeError) return true;
  const status = (error as { statusCode?: number } | null)?.statusCode;
  return status !== undefined && [408, 429, 502, 503, 504].includes(status);
}

function waitForRetry(delayMs: number, signal: AbortSignal): Promise<void> {
  signal.throwIfAborted();
  return new Promise((resolve, reject) => {
    const cancel = () => {
      clearTimeout(timer);
      signal.removeEventListener("abort", cancel);
      reject(signal.reason);
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", cancel);
      resolve();
    }, delayMs);
    signal.addEventListener("abort", cancel, { once: true });
  });
}

// A deployment or temporary network outage must not require a new login.
// Never retry an expired token or grant access before the server verifies it.
export async function recoverAuthSession<T>(
  request: (signal: AbortSignal) => Promise<T>,
  signal: AbortSignal,
  onRetry: (error: unknown) => void,
  initialDelayMs = 1_500,
): Promise<T> {
  let delayMs = initialDelayMs;
  while (true) {
    signal.throwIfAborted();
    try {
      const result = await request(signal);
      signal.throwIfAborted();
      return result;
    } catch (error) {
      signal.throwIfAborted();
      if (!isTemporaryAuthError(error)) throw error;
      onRetry(error);
      await waitForRetry(delayMs, signal);
      delayMs = Math.min(delayMs * 2, 30_000);
    }
  }
}

export async function withAuthDeadline<T>(
  request: (signal: AbortSignal) => Promise<T>,
  parentSignal?: AbortSignal | null,
  timeoutMs = AUTH_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  const cancel = () => controller.abort(parentSignal?.reason);
  let timer: ReturnType<typeof setTimeout> | undefined;
  let onAbort: () => void = () => {};
  const interrupted = new Promise<never>((_, reject) => {
    onAbort = () => reject(controller.signal.reason ?? new DOMException("Aborted", "AbortError"));
    controller.signal.addEventListener("abort", onAbort, { once: true });
    if (parentSignal?.aborted) cancel();
    else parentSignal?.addEventListener("abort", cancel, { once: true });
    timer = setTimeout(() => controller.abort(new AuthTimeoutError(
      "Сервис авторизации не ответил вовремя. Повторите проверку через несколько секунд.",
    )), timeoutMs);
  });
  try {
    return await Promise.race([
      controller.signal.aborted ? interrupted : request(controller.signal), interrupted,
    ]);
  } finally {
    clearTimeout(timer);
    parentSignal?.removeEventListener("abort", cancel);
    controller.signal.removeEventListener("abort", onAbort);
  }
}
