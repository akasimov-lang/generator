import React from 'react';
import {Save} from 'lucide-react';
import type {SaveState} from './SaveIndicator';

export type RedirectSaveFeedback={state:SaveState;detail:string};
export function RedirectSectionSaveStatus({state,detail}:RedirectSaveFeedback) {
  const text=state==='saving'?'Сохраняем…':state==='error'?'Ошибка сохранения':state==='saved'?'Сохранено':'Есть изменения';
  return <span className={`redirectSectionSaveStatus ${state}`} role="status" aria-live="polite" title={detail} aria-label={`${text}. ${detail}`}><Save size={14} strokeWidth={1.8} aria-hidden="true"/><span>{text}</span></span>;
}
