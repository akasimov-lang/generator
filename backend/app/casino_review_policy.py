"""Permanent review requirements, independent of saved prompt versions."""
import secrets

LOGIN = {'en':'login','cs':'přihlášení','sk':'prihlásenie','pl':'logowanie',
         'de':'Login','fr':'connexion','it':'accesso','es':'iniciar sesión',
         'pt':'entrar','nl':'inloggen','sv':'logga in','fi':'kirjaudu sisään',
         'da':'log ind','no':'logg inn','lv':'pieslēgties','lt':'prisijungti',
         'et':'logi sisse','ro':'autentificare','hu':'bejelentkezés',
         'ru':'вход','uk':'вхід','tr':'giriş','az':'giriş','bg':'вход',
         'el':'σύνδεση','ja':'ログイン','ko':'로그인','zh':'登录'}

INSTRUCTION = """
=== CASINO REVIEW FACT TABLE ===
Every casino review must contain an informative table in the project language,
with 2 columns and at least 5 substantive data rows. Cover the casino/operator,
licence/regulator, founding or launch year (state which), mobile app/platforms,
approximate game and provider counts, no-deposit bonus availability, payment
methods, and customer support channels and contacts. Distinguish deposits from
withdrawals and an app from a mobile website. Use supplied facts; do not invent
numbers, contact details or licence claims to fill the table. Missing information
may be identified briefly as unavailable. Approximate counts must be labelled.
The CTA label is exactly the reviewed brand plus 'login', translated into the
project language. Return it as Button Text metadata; the app inserts and styles
the button between whole content blocks. Its position may vary across reviews;
a project-specific placement instruction takes precedence. Do not split a list,
table or paragraph and do not add duplicate CTA markup in the prose.
=== END CASINO REVIEW FACT TABLE ===
"""


def login_label(brand, language):
    word = LOGIN.get(str(language or '').lower().replace('_', '-').split('-')[0])
    return f'{brand} — {word}' if word else None


def review_index(blocks, context):
    if context.get('review_button_placement') == 'before_table':
        return next((i for i, b in enumerate(blocks) if b.get('type') == 'table'), None)
    # Sample once at creation; subsequent processing retains the existing button.
    choices = [i + 1 for i, b in enumerate(blocks) if b.get('type') in {'paragraph', 'table', 'list'}]
    return secrets.choice(choices) if choices else None


def style_button(blocks, button):
    """Fallback styles are scoped to this CTA; established theme rules can win."""
    token = button['id']
    if any(b.get('id') == token + '-open' for b in blocks):
        return
    i = blocks.index(button)
    opening = '<style>:where(.pp-casino-review-action){margin:24px 0;display:flex;flex-wrap:wrap}:where(.pp-casino-review-action) :where(button,a){display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:12px 24px;border:0;border-radius:8px;background:#17644f;color:#fff;font-family:inherit;font-size:16px;font-weight:700;line-height:1.4;text-decoration:none;cursor:pointer;max-width:100%;white-space:normal;overflow-wrap:anywhere}:where(.pp-casino-review-action) :where(button,a):focus-visible{outline:3px solid #e8a330;outline-offset:3px}</style><div class="pp-casino-review-action">'
    blocks.insert(i, {'id':token+'-open','type':'code','data':{'code':opening}})
    blocks.insert(i+2, {'id':token+'-close','type':'code','data':{'code':'</div>'}})


def validate_table(page):
    tables = [b.get('data', {}).get('content') for b in page['content']['blocks'] if b.get('type') == 'table']
    if not any(isinstance(rows,list) and len(rows)>=6 and all(isinstance(r,list) and 2<=len(r)<=5 for r in rows) for rows in tables):
        raise ValueError('В обзоре казино отсутствует информативная таблица: минимум 5 строк данных и 2–5 столбцов.')
