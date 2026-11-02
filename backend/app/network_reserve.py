"""Selected reserves stay in their network and take precedence over imports."""
from app.network_state import domain_name


def reserved_domains(state):
    return list(dict.fromkeys(filter(None, [domain_name(state.get('reserve')),
        *(domain_name(d) for d in state.get('reserved_domains', []))])))


def selected_reserve(state):
    main = domain_name(state.get('canon')).removeprefix('www.')
    return next((d for d in reserved_domains(state) if d.removeprefix('www.') != main), '')


def require_import_target(state):
    if selected_reserve(state):
        raise ValueError('TARGET_HAS_RESERVE: У принимающей сетки выбран резерв. Перенос в неё не требуется; переклей выполняется на выбранный резерв.')
