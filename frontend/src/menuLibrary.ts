export type MenuLibraryItem = {
  name: string;
  russian_name?: string;
  external_id: string;
  path: string;
  parent_external_id?: string | null;
  template_id?: string;
};

const CONCEPTS = [
  ["casino-reviews", "/casino-reviews/", "Обзоры казино"],
  ["best-casinos", "/best-casinos/", "Лучшие казино"],
  ["casino-bonuses", "/casino-bonuses/", "Бонусы казино"],
  ["casino-games", "/casino-games/", "Игры казино"],
  ["payment-methods", "/payment-methods/", "Способы оплаты"],
  ["mobile-casinos", "/mobile-casinos/", "Мобильные казино"],
  ["casino-guides", "/casino-guides/", "Руководства"],
  ["responsible-gambling", "/responsible-gambling/", "Ответственная игра"]
] as const;

const LABELS: Record<string, string[]> = {
  ar: ["مراجعات الكازينوهات", "أفضل الكازينوهات", "مكافآت الكازينو", "ألعاب الكازينو", "طرق الدفع", "كازينوهات الهاتف", "أدلة الكازينو", "اللعب المسؤول"],
  az: ["Kazino rəyləri", "Ən yaxşı kazinolar", "Kazino bonusları", "Kazino oyunları", "Ödəniş üsulları", "Mobil kazinolar", "Kazino bələdçiləri", "Məsuliyyətli oyun"],
  bg: ["Ревюта на казина", "Най-добрите казина", "Казино бонуси", "Казино игри", "Методи на плащане", "Мобилни казина", "Казино ръководства", "Отговорна игра"],
  bn: ["ক্যাসিনো পর্যালোচনা", "সেরা ক্যাসিনো", "ক্যাসিনো বোনাস", "ক্যাসিনো গেম", "পেমেন্ট পদ্ধতি", "মোবাইল ক্যাসিনো", "ক্যাসিনো গাইড", "দায়িত্বশীল জুয়া"],
  ca: ["Ressenyes de casinos", "Millors casinos", "Bons de casino", "Jocs de casino", "Mètodes de pagament", "Casinos mòbils", "Guies de casino", "Joc responsable"],
  cs: ["Recenze kasin", "Nejlepší kasina", "Kasino bonusy", "Kasino hry", "Platební metody", "Mobilní kasina", "Průvodci kasinem", "Zodpovědné hraní"],
  da: ["Kasinoanmeldelser", "Bedste kasinoer", "Kasinobonusser", "Kasinospil", "Betalingsmetoder", "Mobile kasinoer", "Kasino guides", "Ansvarligt spil"],
  de: ["Casino-Bewertungen", "Beste Casinos", "Casino-Boni", "Casino-Spiele", "Zahlungsmethoden", "Mobile Casinos", "Casino-Ratgeber", "Verantwortungsvolles Spielen"],
  el: ["Κριτικές καζίνο", "Καλύτερα καζίνο", "Μπόνους καζίνο", "Παιχνίδια καζίνο", "Μέθοδοι πληρωμής", "Καζίνο για κινητά", "Οδηγοί καζίνο", "Υπεύθυνο παιχνίδι"],
  en: ["Casino Reviews", "Best Casinos", "Casino Bonuses", "Casino Games", "Payment Methods", "Mobile Casinos", "Casino Guides", "Responsible Gambling"],
  es: ["Reseñas de casinos", "Mejores casinos", "Bonos de casino", "Juegos de casino", "Métodos de pago", "Casinos móviles", "Guías de casino", "Juego responsable"],
  et: ["Kasiinoarvustused", "Parimad kasiinod", "Kasiinoboonused", "Kasiinomängud", "Makseviisid", "Mobiilikasiinod", "Kasiinojuhendid", "Vastutustundlik mängimine"],
  fi: ["Kasinoarvostelut", "Parhaat kasinot", "Kasinobonukset", "Kasinopelit", "Maksutavat", "Mobiilikasinot", "Kasino-oppaat", "Vastuullinen pelaaminen"],
  fr: ["Avis sur les casinos", "Meilleurs casinos", "Bonus de casino", "Jeux de casino", "Méthodes de paiement", "Casinos mobiles", "Guides de casino", "Jeu responsable"],
  ga: ["Léirmheasanna ceasaíneo", "Na ceasaíneonna is fearr", "Bónais ceasaíneo", "Cluichí ceasaíneo", "Modhanna íocaíochta", "Ceasaíneonna móibíleacha", "Treoracha ceasaíneo", "Cearrbhachas freagrach"],
  hr: ["Recenzije kasina", "Najbolja kasina", "Casino bonusi", "Casino igre", "Načini plaćanja", "Mobilna kasina", "Vodiči za kasino", "Odgovorno igranje"],
  hu: ["Kaszinó értékelések", "Legjobb kaszinók", "Kaszinó bónuszok", "Kaszinó játékok", "Fizetési módok", "Mobil kaszinók", "Kaszinó útmutatók", "Felelős szerencsejáték"],
  it: ["Recensioni casinò", "Migliori casinò", "Bonus casinò", "Giochi da casinò", "Metodi di pagamento", "Casinò mobile", "Guide ai casinò", "Gioco responsabile"],
  kk: ["Казино шолулары", "Үздік казинолар", "Казино бонустары", "Казино ойындары", "Төлем әдістері", "Мобильді казинолар", "Казино нұсқаулықтары", "Жауапты ойын"],
  lt: ["Kazino apžvalgos", "Geriausi kazino", "Kazino premijos", "Kazino žaidimai", "Mokėjimo būdai", "Mobilieji kazino", "Kazino vadovai", "Atsakingas lošimas"],
  lv: ["Kazino apskati", "Labākie kazino", "Kazino bonusi", "Kazino spēles", "Maksājumu metodes", "Mobilie kazino", "Kazino ceļveži", "Atbildīga spēle"],
  nl: ["Casino reviews", "Beste casino's", "Casinobonussen", "Casinospellen", "Betaalmethoden", "Mobiele casino's", "Casinogidsen", "Verantwoord gokken"],
  no: ["Kasinoanmeldelser", "Beste kasinoer", "Kasinobonuser", "Kasinospill", "Betalingsmetoder", "Mobilkasinoer", "Kasinoguider", "Ansvarlig spilling"],
  pl: ["Recenzje kasyn", "Najlepsze kasyna", "Bonusy kasynowe", "Gry kasynowe", "Metody płatności", "Kasyna mobilne", "Poradniki kasynowe", "Odpowiedzialna gra"],
  pt: ["Avaliações de casinos", "Melhores casinos", "Bónus de casino", "Jogos de casino", "Métodos de pagamento", "Casinos móveis", "Guias de casino", "Jogo responsável"],
  ro: ["Recenzii cazinouri", "Cele mai bune cazinouri", "Bonusuri cazino", "Jocuri de cazino", "Metode de plată", "Cazinouri mobile", "Ghiduri cazino", "Joc responsabil"],
  ru: CONCEPTS.map((concept) => concept[2]),
  sk: ["Recenzie kasín", "Najlepšie kasína", "Kasínové bonusy", "Kasínové hry", "Platobné metódy", "Mobilné kasína", "Sprievodcovia kasínom", "Zodpovedné hranie"],
  sl: ["Ocene igralnic", "Najboljše igralnice", "Igralniški bonusi", "Igralniške igre", "Načini plačila", "Mobilne igralnice", "Vodniki po igralnicah", "Odgovorno igranje"],
  sv: ["Casinorecensioner", "Bästa casinon", "Casinobonusar", "Casinospel", "Betalningsmetoder", "Mobilcasinon", "Casinoguider", "Ansvarsfullt spelande"],
  sw: ["Maoni ya kasino", "Kasino bora", "Bonasi za kasino", "Michezo ya kasino", "Njia za malipo", "Kasino za simu", "Miongozo ya kasino", "Uchezaji wa kuwajibika"],
  tr: ["Casino incelemeleri", "En iyi casinolar", "Casino bonusları", "Casino oyunları", "Ödeme yöntemleri", "Mobil casinolar", "Casino rehberleri", "Sorumlu oyun"],
  uz: ["Kazino sharhlari", "Eng yaxshi kazinolar", "Kazino bonuslari", "Kazino o‘yinlari", "To‘lov usullari", "Mobil kazinolar", "Kazino qo‘llanmalari", "Mas’uliyatli o‘yin"]
};

function normalizeLanguage(value: string | null): string {
  const language = (value || "en").trim().toLowerCase().split(/[-_]/)[0];
  return ({ au: "en", cz: "cs", dk: "da", gr: "el", kz: "kk", se: "sv" } as Record<string, string>)[language] || language;
}

export function getMenuLibrary(language: string | null): MenuLibraryItem[] {
  const labels = LABELS[normalizeLanguage(language)] || LABELS.en;
  return CONCEPTS.map(([external_id, path, russian_name], index) => ({ external_id, path, russian_name, name: labels[index] }));
}
