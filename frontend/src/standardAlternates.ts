/** Replace the full markup with the project's language/GEO/canonical scheme. */
export function buildBaseAlternates(languageValue?: string | null, geoValue?: string | null, fakePath?: string, currentMarkup = ""): string {
  const geo = (geoValue || "").trim().toUpperCase().split(/[-_]/).pop() || "";
  const language = (languageValue || "").trim().toLowerCase().split(/[-_]/)[0];
  if (!/^[a-z]{2,3}$/.test(language) || !/^[A-Z]{2}$/.test(geo)) throw new Error("Укажите язык и ГЕО проекта перед добавлением альтернейтов.");
  if (!fakePath || !/^\/[A-Za-z0-9_-]+(?:\/[A-Za-z0-9_-]+)*\/$/.test(fakePath)) throw new Error("Сначала выберите и сохраните фейковую внутреннюю страницу.");
  const locale = `${language}-${geo}`;
  // Derive the next placement from the markup so it survives saving and reloads.
  const localeHasFake = (currentMarkup.match(/<link\b[^>]*>/gi) || []).some(tag => {
    const attr = (name: string) => tag.match(new RegExp(`\\b${name}\\s*=\\s*(?:"([^"]*)"|'([^']*)'|([^\\s>]+))`, "i"))?.slice(1).find(value => value !== undefined) || "";
    const href = attr("href");
    return attr("rel").toLowerCase() === "alternate" && attr("hreflang").toLowerCase() === locale.toLowerCase()
      && href.split(/[?#]/)[0].endsWith(fakePath);
  });
  return [[language, localeHasFake ? fakePath : "/"], [locale, localeHasFake ? "/" : fakePath], ["x-default", "/"]]
    .map(([lang, path]) => `<link rel="alternate" href="https://{{settings.canon}}${path}" hreflang="${lang}" />`).join("\n");
}

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
