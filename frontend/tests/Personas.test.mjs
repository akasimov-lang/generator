import assert from "node:assert/strict";
import { after, test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const server = await createServer({ configFile: false, root: new URL("..", import.meta.url).pathname, server: { middlewareMode: true, hmr: false }, optimizeDeps: { noDiscovery: true, include: [] }, appType: "custom" });
after(() => server.close());
const { PersonaProjects } = await server.ssrLoadModule("/src/Personas.tsx");

test("author projects link to their PagePilot profiles and show a distinct Main", () => {
  const html = renderToStaticMarkup(React.createElement(PersonaProjects, { projects: [
    { id: "one", name: "project.test", main_domain: "main.test", fibery_name: "#254_Project" },
    { id: "two", name: "same.test", main_domain: "same.test", fibery_name: "" },
  ] }));
  assert.match(html, /href="\/project-overview\/project.test\/"/);
  assert.match(html, /title="#254_Project"/);
  assert.match(html, /<small>main.test<\/small>/);
  assert.match(html, /href="\/project-overview\/same.test\/"/);
  assert.doesNotMatch(html, /<small>same.test<\/small>/);
});

test("an author without assignments has an explicit empty project cell", () => {
  const html = renderToStaticMarkup(React.createElement(PersonaProjects, { projects: [] }));
  assert.match(html, /Нет проектов/);
  assert.doesNotMatch(html, /href=/);
});
