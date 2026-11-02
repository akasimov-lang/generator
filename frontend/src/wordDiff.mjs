// LCS on complete words. Moved, new and replaced words are marked; original text is preserved.
export function wordDiff(before, after) {
 const old=String(before||'').match(/\S+/gu)||[];
 const tokens=String(after||'').match(/\s+|\S+/gu)||[];
 const words=tokens.filter(t=>/\S/u.test(t));
 if(old.length*words.length>250000)return tokens.map(text=>({text,changed:/\S/u.test(text)&&!old.includes(text)}));
 const dp=Array.from({length:old.length+1},()=>new Uint16Array(words.length+1));
 for(let i=old.length-1;i>=0;i--)for(let j=words.length-1;j>=0;j--)dp[i][j]=old[i]===words[j]?dp[i+1][j+1]+1:Math.max(dp[i+1][j],dp[i][j+1]);
 const same=new Set();let i=0,j=0;
 while(i<old.length&&j<words.length){if(old[i]===words[j]){same.add(j);i++;j++;}else if(dp[i+1][j]>=dp[i][j+1])i++;else j++;}
 let k=0;return tokens.map(text=>({text,changed:/\S/u.test(text)?!same.has(k++):false}));
}
