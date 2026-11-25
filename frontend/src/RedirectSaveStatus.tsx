import React from 'react';
import type {RedirectSaveState} from './redirectSaveProgress';
export function RedirectSaveProgress({state}:{state:RedirectSaveState}) {
 return <div className={`redirectSaveProgress${state.failed?' hasErrors':''}`} role="status" aria-live="polite"><strong>{state.label}</strong><progress aria-label={state.label} value={state.value} max={state.max||1}/><small>{state.detail}</small></div>;
}
