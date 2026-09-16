# Network UI regression test

Run Vite locally on port 5174 from `frontend`:

```sh
npm run dev -- --host 127.0.0.1 --port 5174
```

Run the browser check with Python and Playwright (included in backend requirements):

```sh
python frontend/tests/network_browser.py
```

The default browser is Playwright Chromium. Set `CHROME` to an installed Chrome
executable when needed. `VITE_TEST_URL` overrides `http://127.0.0.1:5174`.
The fixture uses an in-memory API; no external projects or accounts are accessed.
Screenshots are written to a temporary directory printed at completion.

Covers reserve/save/check/reglue order, saving alternates, blocking launch while
markup is unsaved, persistence across the two views, external-edit conflicts,
domain history and mobile rendering. The HTML fixture is not a production entry.
