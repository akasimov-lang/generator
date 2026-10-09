(() => {
  const jobs = new Map();
  const validId = value => typeof value === 'string' && /^[\w-]{1,80}$/.test(value);
  window.addEventListener('message', async event => {
    if (event.source !== window || event.origin !== location.origin || event.data?.type !== 'PAGEPILOT_COLLECT_GOOGLE_HTML') return;
    const { templateId, sourceId, revision, url } = event.data;
    if (!validId(templateId) || !validId(sourceId) || !Number.isInteger(revision)) return;
    try {
      const target = new URL(url);
      if (!['https:', 'http:'].includes(target.protocol) || target.username || target.password) throw Error('Некорректный адрес');
      jobs.set(sourceId, { templateId, sourceId, revision, url });
      const result = await chrome.runtime.sendMessage({ type: 'START', templateId, sourceId, revision, url });
      if (result?.error) throw Error(result.error);
    } catch (error) { window.postMessage({ type: 'PAGEPILOT_EXTENSION_ERROR', templateId, error: error.message }, location.origin); }
  });
  chrome.runtime.onMessage.addListener((message, sender, reply) => {
    if (sender.id !== chrome.runtime.id || message.type !== 'SAVE_HTML') return;
    const job = jobs.get(message.sourceId);
    if (!job || job.templateId !== message.templateId) { reply({ error: 'Вернитесь в PagePilot и запустите получение снова: вкладка была обновлена.' }); return; }
    if (typeof message.html !== 'string' || new TextEncoder().encode(message.html).length > 2000000) { reply({ error: 'HTML превышает 2 МБ' }); return; }
    (async () => {
      try {
        const token = localStorage.getItem('admin_token');
        if (!token) throw Error('Войдите в PagePilot и повторите получение');
        const response = await fetch(`/api/site-templates/${job.templateId}/sources/${job.sourceId}`, {
          method: 'PUT', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ html: message.html, url: job.url, revision: job.revision })
        });
        const body = await response.json();
        if (!response.ok) throw Error(typeof body.detail === 'string' ? body.detail : `PagePilot: HTTP ${response.status}`);
        if (body.capture?.status !== 'google_ready') throw Error(body.capture?.error || 'Код сохранён, но не прошёл проверку HTML');
        jobs.delete(job.sourceId);
        window.postMessage({ type: 'PAGEPILOT_SOURCE_SAVED', templateId: job.templateId }, location.origin);
        reply({ saved: true });
      } catch (error) { reply({ error: error.message }); }
    })();
    return true;
  });
})();
