export function notesFirst(leftId: string, rightId: string, noted: ReadonlySet<string>) {
  return Number(noted.has(rightId)) - Number(noted.has(leftId));
}
