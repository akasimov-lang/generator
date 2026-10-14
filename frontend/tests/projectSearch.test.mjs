import assert from "node:assert/strict";
import test from "node:test";
import { normalizeDomainQuery, isExactNetworkDomainSearch, matchesProjectSearch, projectSearchKeywords } from "../src/projectSearch.ts";

const encoded = "xn--80ae9b7b.xn--p1ai";

test("finds a Punycode domain by full and partial Cyrillic input", () => {
  for (const query of ["авсэ.рф", "авсэ", "ВСЭ", ".рф", "  АВСЭ.РФ  "]) {
    assert.equal(matchesProjectSearch(`https://${encoded}/`, query), true, query);
  }
  assert.equal(matchesProjectSearch(encoded, "другой.рф"), false);
});

test("keeps full and partial Punycode searches and accepts Unicode stored domains", () => {
  assert.equal(matchesProjectSearch(encoded, encoded), true);
  assert.equal(matchesProjectSearch(encoded, "xn--80ae"), true);
  assert.equal(matchesProjectSearch("авсэ.рф", encoded), true);
});

test("searches network domain aliases, subdomains and other IDN zones", () => {
  const keywords = projectSearchKeywords(["Project", "example.com", `www.${encoded}`, "xn--80adxhks.xn--p1acf"]);
  for (const query of ["авсэ", "www.авсэ.рф", "москва.рус", "PROJECT", "example.com"]) {
    assert.equal(matchesProjectSearch(keywords, query), true, query);
  }
});

test("preserves ordinary text searches and tolerates malformed IDN labels", () => {
  assert.equal(matchesProjectSearch("Example.COM", "example"), true);
  assert.equal(matchesProjectSearch("Тестовый проект", "тестовый"), true);
  assert.equal(matchesProjectSearch("xn--a-! example.com", "example"), true);
  assert.equal(matchesProjectSearch("", ""), true);
});

test("recognizes an exact domain as a member of its current project network", () => {
  const domains = ["1xslots-online.com", "1xslots-casino-online.com", encoded];
  assert.equal(isExactNetworkDomainSearch(domains, "1xslots-casino-online.com"), true);
  assert.equal(isExactNetworkDomainSearch(domains, "https://1xslots-casino-online.com/path"), true);
  assert.equal(isExactNetworkDomainSearch(domains, "авсэ.рф"), true);
  assert.equal(isExactNetworkDomainSearch(domains, "casino-online.com"), false);
});

test("normalizes pasted URLs in both domain search fields without truncating project names", () => {
  for (const query of ["http://example.com", "https://example.com/", "htpps://example.com/", "example.com/", " HTTPS://EXAMPLE.COM/path?q=1#part ", "//example.com/"]) {
    assert.equal(normalizeDomainQuery(query), "example.com", query);
    assert.equal(isExactNetworkDomainSearch(["example.com"], query), true, query);
  }
  assert.equal(normalizeDomainQuery("#1313_Pin Up_AZ"), "#1313_pin up_az");
  assert.equal(normalizeDomainQuery("Example project"), "example project");
});
