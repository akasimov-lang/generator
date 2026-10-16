/** Update the project's standard pair, preserving alternates for other locales. */
export function buildStandardAlternates(markup: string, languageValue?: string | null, geoValue?: string | null, fakePath?: string, random = Math.random): string {
  const language = (languageValue || "").trim().toLowerCase().split(/[-_]/)[0];
  const geo = (geoValue || "").trim().toUpperCase().split(/[-_]/).pop() || "";
  if (!/^[a-z]{2,3}$/.test(language) || !/^[A-Z]{2}$/.test(geo)) throw new Error("Укажите язык и ГЕО проекта перед добавлением альтернейтов.");
  if (!fakePath || !/^\/[^\s<>"'?#]+\/$/.test(fakePath) || fakePath.startsWith("//")) throw new Error("Сначала выберите и сохраните фейковую внутреннюю страницу.");
  const locale = `${language}-${geo}`;
  const localeOnRoot = random() < 0.5;
  const pair = [[locale, localeOnRoot ? "/" : fakePath], [language, localeOnRoot ? fakePath : "/"]]
    .map(([lang, path]) => `<link rel="alternate" hreflang="${lang}" href="https://{{settings.canon}}${path}" />`).join("\n");
  const other = markup.replace(/<link\b[^>]*>/gi, tag => {
    const lang = tag.match(/\bhreflang\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/i);
    return [language, locale.toLowerCase()].includes((lang?.[1] ?? lang?.[2] ?? lang?.[3] ?? "").toLowerCase()) ? "" : tag;
  }).trim();
  return [other, pair].filter(Boolean).join("\n");
}
