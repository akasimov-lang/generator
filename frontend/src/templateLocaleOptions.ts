import { LANGUAGE_OPTIONS } from "./languageOptions";
const codes = [
  "AF", "AX", "AL", "DZ", "AS", "AD", "AO", "AI", "AQ", "AG", "AR", "AM", "AW", "AU", "AT", "AZ",
  "BS", "BH", "BD", "BB", "BY", "BE", "BZ", "BJ", "BM", "BT", "BO", "BQ", "BA", "BW", "BV", "BR",
  "IO", "BN", "BG", "BF", "BI", "CV", "KH", "CM", "CA", "KY", "CF", "TD", "CL", "CN", "CX", "CC",
  "CO", "KM", "CG", "CD", "CK", "CR", "CI", "HR", "CU", "CW", "CY", "CZ", "DK", "DJ", "DM", "DO",
  "EC", "EG", "SV", "GQ", "ER", "EE", "SZ", "ET", "FK", "FO", "FJ", "FI", "FR", "GF", "PF", "TF",
  "GA", "GM", "GE", "DE", "GH", "GI", "GR", "GL", "GD", "GP", "GU", "GT", "GG", "GN", "GW", "GY",
  "HT", "HM", "VA", "HN", "HK", "HU", "IS", "IN", "ID", "IR", "IQ", "IE", "IM", "IL", "IT", "JM",
  "JP", "JE", "JO", "KZ", "KE", "KI", "KP", "KR", "KW", "KG", "LA", "LV", "LB", "LS", "LR", "LY",
  "LI", "LT", "LU", "MO", "MG", "MW", "MY", "MV", "ML", "MT", "MH", "MQ", "MR", "MU", "YT", "MX",
  "FM", "MD", "MC", "MN", "ME", "MS", "MA", "MZ", "MM", "NA", "NR", "NP", "NL", "NC", "NZ", "NI",
  "NE", "NG", "NU", "NF", "MK", "MP", "NO", "OM", "PK", "PW", "PS", "PA", "PG", "PY", "PE", "PH",
  "PN", "PL", "PT", "PR", "QA", "RE", "RO", "RU", "RW", "BL", "SH", "KN", "LC", "MF", "PM", "VC",
  "WS", "SM", "ST", "SA", "SN", "RS", "SC", "SL", "SG", "SX", "SK", "SI", "SB", "SO", "ZA", "GS",
  "SS", "ES", "LK", "SD", "SR", "SJ", "SE", "CH", "SY", "TW", "TJ", "TZ", "TH", "TL", "TG", "TK",
  "TO", "TT", "TN", "TR", "TM", "TC", "TV", "UG", "UA", "AE", "GB", "US", "UM", "UY", "UZ", "VU",
  "VE", "VN", "VG", "VI", "WF", "EH", "YE", "ZM", "ZW"
];
const ru = new Intl.DisplayNames(["ru"], { type: "region" });
const en = new Intl.DisplayNames(["en"], { type: "region" });
const flag = (code: string) => String.fromCodePoint(...[...code].map(c => 127397 + c.charCodeAt(0)));
export const TEMPLATE_GEOS = codes.map(code => ({ value: code, label: `${code} — ${ru.of(code) || code}`, keywords: en.of(code) || code })).sort((a,b) => a.label.slice(5).localeCompare(b.label.slice(5), "ru")).map(o => ({ ...o, label: `${flag(o.value)} ${o.label}` }));
export const TEMPLATE_LANGUAGES = LANGUAGE_OPTIONS.map(o => ({ value: o.code, label: `${o.nativeName} (${o.code.toUpperCase()})`, keywords: o.name }));

export function languageForGeo(geo: string): string {
  if (!codes.includes(geo)) return "";
  const language = new Intl.Locale(`und-${geo}`).maximize().language;
  return language === "fil" ? "tl" : language;
}
const languageNames = new Intl.DisplayNames(["ru"], { type: "language" });
for (const code of new Set(codes.map(languageForGeo))) {
  if (TEMPLATE_LANGUAGES.some(o => o.value === code)) continue;
  const nativeName = new Intl.DisplayNames([code], { type: "language" }).of(code) || code;
  TEMPLATE_LANGUAGES.push({ value: code, label: `${nativeName} (${code.toUpperCase()})`, keywords: languageNames.of(code) || code });
}
export const TEMPLATE_BRANDS = ["1win", "1xBet", "888casino", "Bet365", "Betano", "Betfair", "Betsson", "Bwin", "Casumo", "22Bet", "Dafabet", "DraftKings", "FanDuel", "Fonbet", "LeoVegas", "Melbet", "Mostbet", "Parimatch", "Pin-Up", "Pinco", "Pinnacle", "PokerStars", "Stake", "Unibet", "Vavada", "William Hill"].sort((a, b) => a.localeCompare(b)).map(value => ({ value, label: value }));
