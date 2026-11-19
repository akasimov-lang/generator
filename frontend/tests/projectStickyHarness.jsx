import React from 'react';
import {createRoot} from 'react-dom/client';
import {ProjectStickyNote} from '../src/ProjectStickyNote';
import {useProjectNoteIndex} from '../src/projectNoteIndex';
import {notesFirst} from '../src/projectNoteOrder';
window.notes={};window.puts=[];window.fail=false;window.delay=0;
async function api(path,options={}) {
 if(path==='/project-notes')return {site_ids:Object.keys(window.notes).filter(id=>window.notes[id].text.trim())};
 const id=path.split('/')[2];
 if(options.method==='PUT') {
  const payload=JSON.parse(options.body);window.puts.push({id,...payload});
  if(window.delay)await new Promise(r=>setTimeout(r,window.delay));
  if(window.fail)throw new Error('Нет связи. Черновик сохранён.');
  const old=window.notes[id]||{text:'',revision:''};
  if(old.text!==payload.text&&old.revision!==payload.revision){const error=new Error('Заметка изменена в другой вкладке');error.statusCode=409;throw error;}
  window.notes[id]={text:payload.text,revision:String(Date.now())};
 }
 return window.notes[id]||{text:'',revision:''};
}
function Harness(){
 const [id,setId]=React.useState('a');const index=useProjectNoteIndex(api);
 return <><button onClick={()=>setId(id==='a'?'b':'a')}>Сменить проект</button><ProjectStickyNote key={id} siteId={id} project={id+'.test'} username='tester' api={api}/><ul id='order'>{['a','b','c'].sort((a,b)=>notesFirst(a,b,index.ids)).map(id=><li key={id}>{id}</li>)}</ul></>;
}
createRoot(document.getElementById('root')).render(<Harness/>);
