// Compare each hreflang with its previous line, so reordering links is not a text change.
function changedCharacters(before, after) {
  const a = [...before], b = [...after];
  if (a.length * b.length > 1_000_000) {
    let start = 0, end = 0;
    while (start < Math.min(a.length,b.length) && a[start] === b[start]) start++;
    while (end < Math.min(a.length,b.length)-start && a[a.length-1-end] === b[b.length-1-end]) end++;
    return b.map((_,i) => i >= start && i < b.length-end);
  }
  const matrix = Array.from({length:a.length+1}, () => new Uint32Array(b.length+1));
  for (let i=a.length-1;i>=0;i--) for (let j=b.length-1;j>=0;j--)
    matrix[i][j] = a[i]===b[j] ? matrix[i+1][j+1]+1 : Math.max(matrix[i+1][j],matrix[i][j+1]);
  const changed = b.map(() => true);
  let i=0,j=0;
  while(i<a.length && j<b.length) {
    if(a[i]===b[j]) { changed[j]=false;i++;j++; }
    else if(matrix[i+1][j]>=matrix[i][j+1]) i++;
    else j++;
  }
  return changed;
}
const lang = line => line.match(/\bhreflang\s*=\s*['"]([^'"]+)['"]/i)?.[1].toLowerCase();
export function alternateDiff(before='',after='') {
  const oldLines = before.split('\n'), used = new Set(), chunks=[];
  for (const [index,line] of after.split('\n').entries()) {
    const key=lang(line);
    let match=oldLines.findIndex((old,i)=>!used.has(i) && (key ? lang(old)===key : old===line));
    if(match<0 && !key && !used.has(index) && !lang(oldLines[index]||'')) match=index<oldLines.length?index:-1;
    const old=match>=0?oldLines[match]:'';
    if(match>=0) used.add(match);
    const changed=changedCharacters(old,line), chars=[...line];
    for(let i=0;i<chars.length;i++) {
      const last=chunks[chunks.length-1];
      if(last && last.changed===changed[i]) last.text+=chars[i];
      else chunks.push({text:chars[i],changed:changed[i]});
    }
    if(index<after.split('\n').length-1) chunks.push({text:'\n',changed:false});
  }
  return chunks;
}
