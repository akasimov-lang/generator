export type Point={x:number;y:number};
export type NodeBox=Point & {width:number;height:number;circle?:boolean};
export const center=(box:NodeBox):Point=>({x:box.x+box.width/2,y:box.y+box.height/2});
export function boundary(box:NodeBox,towards:Point):Point {
  const c=center(box),dx=towards.x-c.x,dy=towards.y-c.y;
  if(!dx&&!dy)return c;
  const scale=box.circle?box.width/2/Math.hypot(dx,dy):Math.min(dx?box.width/2/Math.abs(dx):Infinity,dy?box.height/2/Math.abs(dy):Infinity);
  return {x:c.x+dx*scale,y:c.y+dy*scale};
}
export function edgePoints(from:NodeBox,to:NodeBox){return {start:boundary(from,center(to)),end:boundary(to,center(from))};}
export function movedPointer(start:Point,next:Point){return Math.hypot(next.x-start.x,next.y-start.y)>5;}
export function shelfWidthLimits(total:number) {
  const min=Math.min(180,Math.max(100,total/2));
  return {min,max:Math.max(min,Math.min(640,total-240))};
}
export function clampShelfWidth(value:number,total:number){const {min,max}=shelfWidthLimits(total);return Math.round(Math.max(min,Math.min(max,Number.isFinite(value)?value:300)));}
export function clampBoardZoom(value:number){return Math.round(Math.max(.4,Math.min(2,Number.isFinite(value)?value:1))*100)/100;}
export function boardPoint(client:Point,origin:Point,zoom:number):Point{return {x:(client.x-origin.x)/zoom,y:(client.y-origin.y)/zoom};}
