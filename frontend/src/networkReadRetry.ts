const lockMessage = "С сеткой уже выполняется операция";

function pause(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new DOMException("Aborted", "AbortError")); return; }
    const abort = () => { clearTimeout(timer); signal.removeEventListener("abort", abort); reject(new DOMException("Aborted", "AbortError")); };
    const timer = setTimeout(() => { signal.removeEventListener("abort", abort); resolve(); }, ms);
    signal.addEventListener("abort", abort, { once: true });
  });
}

/** Retry only network reads rejected by the temporary per-project lock. */
export async function readNetworkWithRetry<T>(read: () => Promise<T>, signal: AbortSignal,
  onWait: () => void, wait: (ms: number, signal: AbortSignal) => Promise<void> = pause): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    if (signal.aborted) throw new DOMException("Aborted", "AbortError");
    try { return await read(); }
    catch (error) {
      const temporaryLock = error instanceof Error && (error as Error & { statusCode?: number }).statusCode === 409 && error.message.includes(lockMessage);
      if (!temporaryLock || attempt >= 5 || signal.aborted) throw error;
      onWait();
      await wait((attempt + 1) * 2000, signal);
    }
  }
}
