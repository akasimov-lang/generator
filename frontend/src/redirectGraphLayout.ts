type RedirectRow={url:string;value:string};
const host=(value:string)=>{try{return new URL(value.includes('://')?value.replace(/\s/g,''):'https://'+value.replace(/\s/g,'')).hostname.toLowerCase().replace(/^www\./,'');}catch{return '';}};
type Point={x:number;y:number};
export const routeKey=(from:string,to:string)=>`${host(from)}>${host(to)}`;
/** Follow outgoing redirects only: siblings sharing Main are not part of this path. */
export function redirectChain(domain:string,rows:RedirectRow[],canon:string) {
  const edges=new Map(rows.map(r=>[host(r.url),r]));
  const nodes=new Set<string>(),links=new Set<string>();
  let current=host(domain),cycle=false;
  const main=host(canon);
  while(current){
    if(nodes.has(current)){cycle=true;break;}
    nodes.add(current);
    if(current===main)break;
    const row=edges.get(current);if(!row)break;
    const target=host(row.value);if(!target)break;
    links.add(routeKey(row.url,row.value));current=target;
  }
  return {nodes,links,cycle,reachesMain:!!main&&nodes.has(main)};
}
/** Incoming subtree of the active domain, plus its outgoing path to Main. */
export function redirectBranch(domain:string,rows:RedirectRow[],canon:string) {
  const result=redirectChain(domain,rows,canon),start=host(domain),main=host(canon);
  const incoming=new Map<string,RedirectRow[]>();
  for(const row of rows){const from=host(row.url),to=host(row.value);if(!from||!to||from===main)continue;incoming.set(to,[...(incoming.get(to)||[]),row]);}
  const pending=start?[start]:[],visited=new Set<string>();
  while(pending.length){const current=pending.pop()!;if(visited.has(current))continue;visited.add(current);
    for(const row of incoming.get(current)||[]){const from=host(row.url);result.nodes.add(from);result.links.add(routeKey(row.url,row.value));pending.push(from);}
  }
  return result;
}
export function extendedBoardHeight(current:number,viewport:number,zoom:number) {
  return Math.min(100000,Math.ceil(current+Math.max(1,viewport)/zoom));
}
type Block={width:number;height:number;positions:Record<string,Point>};
/** Pack redirect trees by destination. Each subtree occupies its own rectangle. */
export function arrangeRedirectGraph(domains:string[],rows:RedirectRow[],canon:string,viewportWidth:number) {
  const main=host(canon),names=[...new Set(domains.map(host).filter(Boolean))].sort();
  const included=new Set(names),parent=new Map<string,string>();
  for(const r of rows){const from=host(r.url),to=host(r.value);if(from!==main&&from!==to&&included.has(from)&&included.has(to))parent.set(from,to);}
  const children=new Map<string,string[]>();
  for(const [from,to] of parent)children.set(to,[...(children.get(to)||[]),from]);
  for(const list of children.values())list.sort();
  const gap=28,levelGap=64,margin=32;
  const boardWidth=Math.max(640,viewportWidth-2*margin);
  const branchWidth=Math.max(300,Math.min(640,Math.floor(boardWidth/3)));
  const visited=new Set<string>();
  function pack(blocks:Block[],limit:number):Block {
    let x=0,y=0,rowHeight=0,width=0;const positions:Record<string,Point>={};
    for(const block of blocks){if(x&&x+block.width>limit){x=0;y+=rowHeight+gap;rowHeight=0;}
      for(const [domain,p] of Object.entries(block.positions))positions[domain]={x:p.x+x,y:p.y+y};
      width=Math.max(width,x+block.width);rowHeight=Math.max(rowHeight,block.height);x+=block.width+gap;
    }
    return {positions,width,height:y+rowHeight};
  }
  function tree(domain:string):Block {
    visited.add(domain);const isMain=domain===main,w=isMain?360:280,h=isMain?100:112;
    const blocks:Block[]=[];
    for(const child of children.get(domain)||[])if(!visited.has(child))blocks.push(tree(child));
    const packed=pack(blocks,isMain?boardWidth:branchWidth),width=Math.max(w,packed.width);
    const positions:Record<string,Point>={[domain]:{x:(width-w)/2,y:0}};
    for(const [child,p] of Object.entries(packed.positions))positions[child]={x:p.x+(width-packed.width)/2,y:p.y+h+levelGap};
    return {positions,width,height:h+(blocks.length?levelGap+packed.height:0)};
  }
  const roots=[...(included.has(main)?[main]:[]),...names.filter(n=>n!==main&&!parent.has(n))];
  const trees:Block[]=[];
  for(const root of [...roots,...names])if(!visited.has(root))trees.push(tree(root));
  // Main's component comes first. Detached paths and malformed cycles remain visible.
  const packed=pack(trees,boardWidth);
  return {positions:Object.fromEntries(Object.entries(packed.positions).map(([name,p])=>[name===main?`main:${name}`:name,{x:p.x+margin,y:p.y+margin}])),width:packed.width+2*margin,height:packed.height+2*margin};
}
