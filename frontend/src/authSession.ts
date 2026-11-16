// Bound the whole authentication request, including reading its response body.
export const AUTH_TIMEOUT_MS = 25_000;

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
    timer = setTimeout(() => controller.abort(new Error(
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
