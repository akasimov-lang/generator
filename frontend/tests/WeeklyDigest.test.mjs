import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import * as vite from 'vite';

const require = createRequire(import.meta.url);
const source = readFileSync(new URL('../src/WeeklyDigest.tsx', import.meta.url), 'utf8');
const transformed = vite.transformWithOxc
  ? await vite.transformWithOxc(source, new URL('../src/WeeklyDigest.tsx', import.meta.url).pathname, {jsx: {runtime: 'classic'}})
  : await vite.transformWithEsbuild(source, 'WeeklyDigest.tsx', {loader: 'tsx', jsx: 'transform'});
const compiled = transformed.code.replace(/from ['"](react|lucide-react)['"]/g, (_, name) => `from ${JSON.stringify(pathToFileURL(require.resolve(name)).href)}`);
const {currentMoscowWeek, validWeek, DigestText, WeeklyDigestLinks} = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
const render = (component, props) => renderToStaticMarkup(React.createElement(component, props));

test('the new week starts at Monday midnight Moscow, even while UTC is still Sunday', () => {
  assert.equal(currentMoscowWeek(new Date('2026-11-08T20:59:59Z')), '2026-11-02');
  assert.equal(currentMoscowWeek(new Date('2026-11-08T21:00:00Z')), '2026-11-09');
});

test('the current report remains the same Monday across a year boundary', () => {
  assert.equal(currentMoscowWeek(new Date('2027-01-01T01:00:00Z')), '2026-12-28');
  assert.equal(currentMoscowWeek(new Date('2027-01-03T21:00:00Z')), '2027-01-04');
});

test('report URLs accept only existing Monday dates rather than normalized invalid dates', () => {
  assert.equal(validWeek('2026-11-02'), true);
  assert.equal(validWeek('2026-11-07'), false);
  assert.equal(validWeek('2026-02-30'), false);
  assert.equal(validWeek('2026-11-02/../private'), false);
});

test('the saved chat format remains readable as headings, numbered and bulleted results', () => {
  const html = render(DigestText, {text: '**Новости PagePilot**\n\nЗа неделю — **182 проекта**.\n\n- **128** смен Main.\n- [Подробный отчёт](/weekly-reports?id=report-one)\n\n**🇵🇱 Lemon**\n\n1. Замена внутренней страницы на уникальную.\n2. Canonical на `/`.\n\n**8 задач — требуют ручного разбора.**'});
  assert.match(html, /<h3>Новости PagePilot<\/h3>/);
  assert.match(html, /<strong>182 проекта<\/strong>/);
  assert.match(html, /<ul><li><strong>128<\/strong> смен Main\.<\/li>/);
  assert.match(html, /href="\/weekly-reports\?id=report-one"/);
  assert.match(html, /<ol><li>Замена внутренней страницы на уникальную\.<\/li>/);
  assert.match(html, /<code>\/<\/code>/);
  assert.match(html, /<h3>8 задач — требуют ручного разбора\.<\/h3>/);
});

test('report evidence cannot introduce executable HTML or unsafe links', () => {
  const html = render(DigestText, {text: '<img src=x onerror=alert(1)>\n\n[Bad](javascript:alert) [External](//evil.example) [Backslash](/\\evil.example) [Good](https://example.com/report)'});
  assert.doesNotMatch(html, /<img|href="javascript:|href="\/\/evil|href="\/\\/);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(html, /href="https:\/\/example.com\/report"/);
  assert.match(html, /rel="noopener noreferrer"/);
});

test('week archive opens the exact saved period and marks only the current period', () => {
  const html = render(WeeklyDigestLinks, {currentWeek: '2026-11-09', reports: [
    {id: 'new', week_start: '2026-11-09', title: '9–15 ноября', status: 'open', projects: 0},
    {id: 'previous', week_start: '2026-11-02', title: '2–8 ноября', status: 'closed', projects: 182},
  ]});
  assert.match(html, /href="\/weekly-reports\?week=2026-11-09" aria-current="date"/);
  assert.match(html, /href="\/weekly-reports\?week=2026-11-02"/);
  assert.equal((html.match(/aria-current="date"/g) || []).length, 1);
  assert.match(html, /Наполняется в течение недели/);
  assert.match(html, /Завершённая неделя/);
});
