import assert from "node:assert/strict";
import test from "node:test";
import { matchesProjectSearch, projectSearchKeywords } from "../src/projectSearch.ts";

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
