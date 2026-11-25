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
