export function needsTextRetry(row:{title_h1_error?:string;paragraphs_error?:string}):boolean {
 return !!(row.title_h1_error||row.paragraphs_error);
}

export function pilotTextError(error:string,field:"title_h1"|"paragraphs",mode?:string):string {
 const subject=field==="title_h1"?"Заголовки":"Абзацы";
 if(/400\s*(?:Bad Request)?/i.test(error)&&/gemini|generativelanguage/i.test(error))
  return `Gemini отклонил запрос. ${subject} нужно перегенерировать. Новый вариант не опубликован.`;
 if(/Проверка (?:сохранения смысла|соответствия странице|общего смысла)|"approved"\s*:\s*false/i.test(error))
  return field==="title_h1"&&mode==="minimal"
   ?"Заголовки нужно перегенерировать: точечная правка изменила исходный смысл. Новый вариант не опубликован."
   :`${subject} нужно перегенерировать: новый текст не прошёл проверку соответствия странице. Новые смыслы по теме разрешены. Новый вариант не опубликован.`;
 if(/429|Too Many Requests/i.test(error))return "Gemini временно ограничил запросы. Повторите генерацию позже. Новый вариант не опубликован.";
 if(/timeout|timed out|50[0234]|Service Unavailable/i.test(error))return "Gemini не ответил вовремя. Повторите генерацию. Новый вариант не опубликован.";
 if(/https?:\/\/|Traceback|HTTPStatusError|Client error|Server error/.test(error))
  return `${subject} пока не подготовлены: ошибка сервиса генерации. Повторите генерацию этого проекта.`;
 return error;
}
