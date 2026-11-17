import assert from "node:assert/strict";
import { test } from "node:test";
import { projectPagesCount, addPagesColumn } from "../src/projectPageCounts.ts";

test("Pages includes the homepage even when no internal pages exist", () => {
  assert.equal(projectPagesCount({ internal_pages_count: 0 }), 1);
  assert.equal(projectPagesCount({ internal_pages_count: 42 }), 43);
});

test("missing or invalid cached page counts remain unknown", () => {
  assert.equal(projectPagesCount({}), null);
  assert.equal(projectPagesCount({ internal_pages_count: null }), null);
  assert.equal(projectPagesCount({ internal_pages_count: -1 }), null);
  assert.equal(projectPagesCount({ internal_pages_count: "10" }), null);
  assert.equal(projectPagesCount({ internal_pages_count: 1.5 }), null);
});

test("saved project column preferences gain Pages immediately after Showcase", () => {
  const saved = Object.freeze(["name", "fiberyName", "subdomainsCount", "main"]);
  assert.deepEqual(addPagesColumn(saved), ["name", "fiberyName", "subdomainsCount", "pagesCount", "main"]);
  assert.deepEqual(saved, ["name", "fiberyName", "subdomainsCount", "main"]);
});

test("a user-customized Pages position is retained without duplicates", () => {
  assert.deepEqual(addPagesColumn(["pagesCount", "name", "subdomainsCount"]), ["pagesCount", "name", "subdomainsCount"]);
});
