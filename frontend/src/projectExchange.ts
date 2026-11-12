/** Background reads from PagePilot do not indicate an exchange with Webdev. */
export function isProjectExchangeRequest(path: string, method = "GET") {
  const url = new URL(path, "https://pagepilot.invalid");
  if (/\/(notifications|gsc)(?:\/|$)/.test(url.pathname)) return false;
  return method.toUpperCase() !== "GET" || url.searchParams.get("refresh") === "true";
}

/** Fast only while work is pending. Hidden tabs don't poll either queue. */
export function queuePollDue(active: number, lastRead: number, now: number, hidden: boolean) {
  return !hidden && now - lastRead >= (active > 0 ? 3000 : 30000);
}
