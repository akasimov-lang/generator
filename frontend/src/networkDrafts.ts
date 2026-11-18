export type MarkupDraft = { markup: string; enabled: boolean; originalMarkup: string; originalEnabled: boolean };
export type CanonicalDraft = { standard: string; fake: string; originalStandard: string; originalFake: string };
function field<T>(value: T, original: T, remote: T, sent?: T): [T, T] {
  // An unchanged submitted value is acknowledged, including untouched fields
  // rebased just before the request. Further typing remains a local edit.
  if (sent !== undefined) return [value === sent ? remote : value, remote];
  // PagePilot owns edited fields; remote changes refresh untouched fields and the save baseline.
  return value === original || value === remote ? [remote, remote] : [value, remote];
}
export function mergeMarkupDraft(old: MarkupDraft | null, markup: string, enabled: boolean, sent?: MarkupDraft): MarkupDraft {
  if (!old) return { markup, enabled, originalMarkup: markup, originalEnabled: enabled };
  const [value, originalMarkup] = field(old.markup, old.originalMarkup, markup, sent?.markup);
  const [checked, originalEnabled] = field(old.enabled, old.originalEnabled, enabled, sent?.enabled);
  return { markup: value, enabled: checked, originalMarkup, originalEnabled };
}
export function mergeCanonicalDraft(old: CanonicalDraft | null, standard: string, fake: string, sent?: CanonicalDraft): CanonicalDraft {
  if (!old) return { standard, fake, originalStandard: standard, originalFake: fake };
  const [value, originalStandard] = field(old.standard, old.originalStandard, standard, sent?.standard);
  const [internal, originalFake] = field(old.fake, old.originalFake, fake, sent?.fake);
  return { standard: value, fake: internal, originalStandard, originalFake };
}
