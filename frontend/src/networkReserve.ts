type ReserveState = {
  canon: string;
  reserve: string;
  domains: string[];
  amp?: string;
  amp_domains?: string[];
  domain_types?: Record<string, string>;
};

// A fresh revision may include unrelated metadata changes. Never silently
// replace another user's reserve or save against a different Main.
export function validateReserveSave(previous: ReserveState, fresh: ReserveState, domain: string) {
  if (fresh.canon !== previous.canon || (fresh.reserve !== previous.reserve && fresh.reserve !== domain)) {
    throw new Error("Main или резерв изменился. Проверьте актуальные данные перед сохранением.");
  }
  if (!domain || domain === fresh.canon || !fresh.domains.includes(domain)
      || domain === fresh.amp || fresh.amp_domains?.includes(domain) || fresh.domain_types?.[domain] === "amp") {
    throw new Error("Выбранный домен больше недоступен для резерва. Выберите домен из актуальной сетки.");
  }
}
