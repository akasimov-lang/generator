import React from 'react';
import { createRoot } from 'react-dom/client';
import { AutoReglueView } from '../src/AutoRegluePanel';
window.saved = {enabled:false, execution_mode:'within_network', scheme_mode:'preserve', schedule_enabled:false, interval_days:0, max_projects:20, auxiliary_hreflangs:[]};
const before = '<link rel="alternate" hreflang="az" href="https://old.test/" />';
const run = {id:'run',status:'completed',phase:'completed',message:'Готово',plan:{project:'target.test',source_project:'source.test',new_main:'new.test',old_main:'old.test',alternateMarkup:'',alternates_before:{markup:before,enabled:true},alternates_after:{markup:'',enabled:false},added_at:'2026-10-17T12:00:00Z',elapsed_seconds:114,required_page_urls:[]}};
async function api(path, options={}) {
 if(path.endsWith('/brands'))return {brands:[]};
 if(path.endsWith('/settings')){window.saved=JSON.parse(options.body);return structuredClone(window.saved);}
 return {settings:structuredClone(window.saved),projects:[],runs:[run],tasks:[]};
}
createRoot(document.getElementById('root')).render(<AutoReglueView api={api}/>);
