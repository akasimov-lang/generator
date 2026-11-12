import assert from 'node:assert/strict';
import {after, test} from 'node:test';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';

const server = await createServer({configFile: false, root: new URL('..', import.meta.url).pathname,
  server: {middlewareMode: true, hmr: false}, optimizeDeps: {noDiscovery: true, include: []}, appType: 'custom'});
after(() => server.close());
const {ProjectGscField} = await server.ssrLoadModule('/src/ProjectGscField.tsx');
const notifications = await server.ssrLoadModule('/src/projectNotificationEvents.ts');

test('GSC is an accessible text input without buttons or external links', () => {
  const html = renderToStaticMarkup(React.createElement(ProjectGscField, {siteId: 'first', api: async () => ({value: ''})}));
  assert.match(html, /<label[^>]*>GSC<\/label>/);
  assert.match(html, /type="text"/); assert.match(html, /autoComplete="off"/);
  assert.match(html, /aria-describedby=/); assert.match(html, /role="status"/);
  assert.doesNotMatch(html, /<button|<a\s|<form/);
});

test('private GSC changes and failures do not trigger site refreshes or shared notifications', () => {
  const previous = globalThis.window, events = [];
  globalThis.window = {dispatchEvent: event => events.push(event)};
  try {
    const site = '11111111-1111-1111-1111-111111111111';
    notifications.projectApiResult(`/sites/${site}/gsc`, 'PUT');
    notifications.projectApiResult(`/sites/${site}/gsc`, 'PUT', Error('private draft'));
    notifications.projectApiResult(`/sites/${site}/gsc`, 'GET', Error('offline'));
    assert.equal(events.length, 0);
    assert.deepEqual(notifications.localProjectNotices(site), []);
    notifications.projectApiResult(`/sites/${site}/network`, 'PUT');
    assert.equal(events.length, 1); assert.equal(events[0].type, notifications.PROJECT_CHANGED_EVENT);
  } finally { globalThis.window = previous; }
});
