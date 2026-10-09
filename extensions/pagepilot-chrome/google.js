(async () => {
  const job = await chrome.runtime.sendMessage({ type: 'JOB' });
  if (!job.url || job.saved) return;
  const visible = node => node.getClientRects().length > 0;
  const button = pattern => [...document.querySelectorAll('button,[role="button"],[role="tab"]')].find(node => visible(node) && pattern.test(node.textContent.trim()));
  let started = false;
  for (let attempt = 0; attempt < 90; attempt++) {
    await new Promise(resolve => setTimeout(resolve, 2000));
    const text = document.body.innerText;
    if (/Войдите в аккаунт и повторите|Sign in.*try again|подтвердите.*не робот|unusual traffic/i.test(text)) {
      await chrome.runtime.sendMessage({ type: 'STATUS', status: 'Google требует вход или проверку. Завершите её самостоятельно, затем нажмите «Забрать HTML» в расширении.' });
      return;
    }
    const input = document.querySelector('input[type="url"]');
    const start = button(/^(Проверить страницу|Test URL)$/i);
    if (input && start && !started) {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, job.url);
      input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true }));
      start.click(); started = true;
    }
    const view = button(/^(Просмотреть проверенную страницу|View tested page)$/i);
    if (view) view.click();
    const html = button(/^HTML$/i);
    if (html) html.click();
    if (view || html || document.querySelector('.CodeMirror, .cm-editor')) {
      const result = await chrome.runtime.sendMessage({ type: 'CAPTURE' });
      if (result.saved) return;
    }
  }
  await chrome.runtime.sendMessage({ type: 'STATUS', status: 'Проверка не завершилась автоматически. Откройте HTML и нажмите «Забрать HTML» или вставьте код вручную в PagePilot.' });
})();
