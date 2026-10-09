const status = document.getElementById('status');
async function activeTab() { return (await chrome.tabs.query({ active: true, currentWindow: true }))[0]?.id; }
(async () => { const job = await chrome.runtime.sendMessage({ type: 'JOB', tabId: await activeTab() }); if (job.status) status.textContent = job.status; })();
document.getElementById('capture').addEventListener('click', async () => {
  status.textContent = 'Получаем и сохраняем…';
  try { const result = await chrome.runtime.sendMessage({ type: 'CAPTURE', tabId: await activeTab() }); status.textContent = result.saved ? 'HTML сохранён в задаче PagePilot.' : result.error; }
  catch { status.textContent = 'Откройте вкладку Rich Results Test, запущенную из PagePilot.'; }
});
