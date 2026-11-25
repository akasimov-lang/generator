"""AMP roles are excluded from domain redirect editing, independently of names."""
from app.network_state import domain_name


def amp_keys(state, types=None):
    return {domain_name(d).removeprefix('www.') for d in [*state.get('amp_domains', []), state.get('amp'), state.get('prev_amp'),
            *[d for d, kind in (types or {}).items() if kind == 'amp']] if domain_name(d)}


def require_non_amp(state, types, source, target):
    excluded = amp_keys(state, types)
    from app.domain_redirects import redirect_address
    names = [domain_name(redirect_address(value)).removeprefix('www.') for value in (source, target)]
    if any(name == root or name.endswith('.' + root) for name in names for root in excluded):
        raise ValueError('AMP-домены не участвуют в доменных редиректах. Выберите домен основной сетки.')
