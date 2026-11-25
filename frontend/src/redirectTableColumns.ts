export function redirectTableColumns<T>(rows:readonly T[]):T[][] {
  return Array.from({length:Math.ceil(rows.length/15)},(_,index)=>rows.slice(index*15,index*15+15));
}
