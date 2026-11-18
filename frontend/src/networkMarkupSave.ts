/** Re-read and merge edited fields only after an explicit pre-write conflict. */
export async function saveMarkupWithRetry<T>(attempt: () => Promise<T>, onWait: () => void,
  wait: (ms:number)=>Promise<void> = ms => new Promise(resolve => setTimeout(resolve, ms))): Promise<T> {
  for(let retries=0;;retries++) {
    try { return await attempt(); }
    catch(error) {
      const safe = error instanceof Error && (error as Error & {statusCode?:number}).statusCode === 409
        && ["Настройки сетки изменились", "С сеткой уже выполняется операция", "Ожидает освобождения сетки"].some(message => error.message.includes(message));
      if(!safe) throw error;
      if(retries>=5) throw Object.assign(new Error("Сетка всё ещё занята или меняется. Правки сохранены в форме. Нажмите Enter для повторного сохранения."), {statusCode: 409});
      onWait();
      await wait((retries+1)*1000);
    }
  }
}
