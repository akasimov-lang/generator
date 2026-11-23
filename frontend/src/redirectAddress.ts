/** Keep the destination path and its case; trim only pasted URL prefixes. */
export function normalizeRedirectAddress(value: string): string {
  return value.trim().replace(/^\/+/, "").replace(/^https?:\/\//i, "").replace(/^\/+/, "");
}

/** Domain redirects accept a host only; page paths belong to page redirects. */
export function domainRedirectSource(value: string): string {
  const raw = normalizeRedirectAddress(value);
  if (!raw || /[\\\s\u0000-\u001f\u007f]/.test(raw)) throw new Error("Откуда: укажите корректный домен без пробелов.");
  let url: URL;
  try { url = new URL(`https://${raw}`); }
  catch { throw new Error("Откуда: укажите корректный домен."); }
  if (url.username || url.password || /[:@]/.test(raw.split(/[/?#]/)[0])) {
    throw new Error("Откуда: укажите домен без логина, пароля и порта.");
  }
  // Check the literal path too: URL normalizes paths such as /folder/.. to /.
  const suffix = raw.slice(raw.search(/[/?#]/) < 0 ? raw.length : raw.search(/[/?#]/));
  if (suffix && suffix !== "/") {
    throw new Error("Откуда: нужен домен без пути. Для адреса страницы используйте раздел «Постраничные редиректы» ниже.");
  }
  const host = url.hostname.toLowerCase().replace(/\.$/, "");
  if (host.length > 253 || !host.includes(".") || !host.split(".").every(label => /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))) {
    throw new Error("Откуда: укажите корректный домен.");
  }
  return host;
}
