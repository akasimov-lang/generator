/** Re-read and merge edited fields only after an explicit pre-write conflict. */
export async function saveMarkupWithRetry<T>(attempt: () => Promise<T>, onWait: () => void,
  wait: (ms:number)=>Promise<void> = ms => new Promise(resolve => setTimeout(resolve, ms))): Promise<T> {
  for(let retries=0;;retries++) {
    try { return await attempt(); }
    catch(error) {
      const safe = error instanceof Error && (error as Error & {statusCode?:number}).statusCode === 409
        && (error.message.includes("Настройки сетки изменились") || error.message.includes("С сеткой уже выполняется операция"));
      if(!safe || retries>=5) throw error;
      onWait();
      await wait((retries+1)*1000);
    }
  }
}
