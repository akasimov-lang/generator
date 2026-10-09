const trusted = url => {
  try { return ['https://ai-seo-content-panel.site', 'https://www.ai-seo-content-panel.site', 'http://localhost:5173', 'http://localhost:8080'].includes(new URL(url).origin); } catch { return false; }
};
const jobKey = id => `job:${id}`;
async function getJob(tabId) { return (await chrome.storage.session.get(jobKey(tabId)))[jobKey(tabId)]; }
async function update(tabId, job) { await chrome.storage.session.set({ [jobKey(tabId)]: job }); }
async function capture(tabId) {
  const job = await getJob(tabId);
  if (!job) throw Error('Откройте проверку кнопкой «Получить через Chrome» в PagePilot.');
  if (job.saved) return { saved: true };
  const results = await chrome.scripting.executeScript({ target: { tabId }, world: 'MAIN', func: () => {
    const values = [];
    document.querySelectorAll('.CodeMirror').forEach(node => { const v = node.CodeMirror?.getValue(); if (v) values.push(v); });
    for (const model of window.monaco?.editor?.getModels?.() || []) values.push(model.getValue());
    document.querySelectorAll('textarea, pre, .cm-content, [role="textbox"]').forEach(node => values.push(node.value || node.innerText || ''));
    // Never return Google's outerHTML or reconstruct a virtualised editor from visible lines.
    return values.filter(value => /<html\b/i.test(value) && /<\/html\s*>/i.test(value)).sort((a, b) => b.length - a.length)[0] || '';
  }});
  const html = results[0]?.result;
  if (!html) throw Error('Откройте «Просмотреть проверенную страницу → HTML». Если редактор не доступен расширению, скопируйте весь код и вставьте в PagePilot.');
  const response = await chrome.tabs.sendMessage(job.pagepilotTab, { type: 'SAVE_HTML', templateId: job.templateId, sourceId: job.sourceId, html });
  if (!response?.saved) throw Error(response?.error || 'PagePilot не подтвердил сохранение');
  await update(tabId, { ...job, saved: true, status: 'HTML сохранён в PagePilot' });
  return { saved: true };
}
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  (async () => {
    if (message.type === 'START') {
      if (!sender.tab || !trusted(sender.url)) throw Error('Запуск доступен только из PagePilot');
      const url = new URL(message.url);
      if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) throw Error('Некорректный адрес');
      const tab = await chrome.tabs.create({ url: 'about:blank' });
      await update(tab.id, { pagepilotTab: sender.tab.id, templateId: message.templateId, sourceId: message.sourceId, status: 'Ожидаем проверку Google', url: url.href });
      await chrome.tabs.update(tab.id, { url: 'https://search.google.com/test/rich-results?hl=ru&url=' + encodeURIComponent(url.href) });
      return { started: true };
    }
    const popup = !sender.tab && sender.url === chrome.runtime.getURL('popup.html');
    const tabId = sender.tab?.id ?? (popup ? message.tabId : undefined);
    if (!tabId) throw Error('Нет активной проверки');
    if (sender.tab && !sender.url?.startsWith('https://search.google.com/test/rich-results')) throw Error('Недопустимая вкладка');
    if (message.type === 'JOB') return await getJob(tabId) || {};
    if (message.type === 'CAPTURE') return await capture(tabId);
    if (message.type === 'STATUS') {
      const job = await getJob(tabId);
      if (job && !job.saved) await update(tabId, { ...job, status: String(message.status).slice(0, 500) });
      return {};
    }
  })().then(reply).catch(error => reply({ error: error.message }));
  return true;
});
chrome.tabs.onRemoved.addListener(tabId => { void chrome.storage.session.remove(jobKey(tabId)); });
