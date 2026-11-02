"""Remember depleted networks until a usable new root is added."""
from app import models
from app.domain_transfer_policy import domain_key

MESSAGE = 'В сетке нет доступных резервов. Добавьте новореги в сетку. Для переклея используется исключение: новый поддомен своего домена.'


def mark(db, site, state):
    key = 'network-stock-warning:' + site.id
    row = db.get(models.AutoReglueConfig, key)
    if not row:
        db.add(models.AutoReglueConfig(key=key, value={'domains': list(state['domains'])}))


def notice(db, site, state):
    row = db.get(models.AutoReglueConfig, 'network-stock-warning:' + site.id)
    if not row:
        return None
    from app.mass_main_targets import target_kind, require_target
    old = {domain_key(d) for d in row.value.get('domains', [])}
    for domain in state.get('domains', []):
        if domain_key(domain) in old or target_kind(site, state, domain) != 'newreg':
            continue
        try:
            require_target(db, site, state, {'new_main': domain, 'main_target_kind': 'newreg'})
            return None
        except ValueError:
            pass
    return MESSAGE
