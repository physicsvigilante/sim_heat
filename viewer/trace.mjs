// H2-01: pure, read-only interpretation of saved native observations.
// No physical laws, new solver, interpolation, or reconstructed missing exports.
export const FIELDS = Object.freeze([
  "time","left.T","right.T","bridge.Q_flow","left.dU","right.dU",
  "heated.Q_to_network","cooled.Q_to_network","supplyLeft.Q_flow",
  "supplyRight.Q_flow","rejectLeft.Q_flow","rejectRight.Q_flow"
]);
export const RUN = 43699424883;
export const SOURCE_CSV_SHA256 = "4b1a822680c03742e3031f5be653b48e7dd736613be355796862de483c0e39fe";
export const PREVIEW_GIT_BLOB_SHA1 = "a9cbc96bf00d24a1390c69bb254fa073f79b5a77";
export const PREVIEW_TIMES = Object.freeze([0,1000,1720,1730,...Array.from({length:19},(_,i)=>(i+2)*1000)]);

function reject(condition, reason) { if (!condition) throw new Error(reason); }
export function validatePreview(p) {
  reject(p?.schema==="sim_heat.viewer.preview/1" && p.sourceRun===RUN
    && p.nativeQualified===false && p.originalCsvSha256===SOURCE_CSV_SHA256,
    "Unrecognized or falsely qualified native evidence");
  reject(JSON.stringify(p.columns)===JSON.stringify(FIELDS), "Preview channel meanings changed");
  reject(Array.isArray(p.data) && p.data.length===PREVIEW_TIMES.length, "Missing preview samples");
  const records=p.data.map((row,i)=>{
    reject(Array.isArray(row)&&row.length===FIELDS.length, "Incomplete native row");
    reject(row.every(v=>typeof v==="number"&&Number.isFinite(v)), "Invalid native number");
    reject(row[0]===PREVIEW_TIMES[i], "Missing, duplicated or interpolated time");
    return Object.fromEntries(row.map((v,j)=>[FIELDS[j],v]));
  });
  const b=reversalBracket(records);
  reject(b?.from===1720 && b?.to===1730, "Saved flow reversal bracket missing");
  return records;
}
export function reversalBracket(records) {
  for(let i=1;i<records.length;i++) if(records[i-1]["bridge.Q_flow"]<0
    && records[i]["bridge.Q_flow"]>=0) return {from:records[i-1].time,to:records[i].time,index:i};
  return null;
}
export function energyLedger(record) {
  return {leftJ:record["left.dU"],rightJ:record["right.dU"],
    totalJ:record["left.dU"]+record["right.dU"],
    hotW:record["heated.Q_to_network"],coldW:record["cooled.Q_to_network"]};
}
export function flowLabel(q) { return q>0?"Left → right":q<0?"Right → left":"Zero at this saved sample"; }
export function parseOriginalCsv(text) {
  reject(typeof text==="string"&&text.length<3_000_000,"Native CSV absent or too large");
  const lines=text.trimEnd().split(/\r?\n/);
  reject(lines.length===2003,"Original CSV must contain 2002 data rows");
  const names=lines[0].split(",");
  reject(new Set(names).size===names.length&&FIELDS.every(f=>names.includes(f)),
    "Native header missing or repeated");
  const ix=FIELDS.map(f=>names.indexOf(f));
  const raw=lines.slice(1).map(line=>line.split(","));
  reject(raw.every(r=>r.length===names.length), "Malformed native row");
  reject(raw[2001].every((v,i)=>v===raw[2000][i]), "Non-identical final duplicate");
  raw.pop();
  const result=raw.map((values,i)=>{
    const o={};
    for(let j=0;j<FIELDS.length;j++){
      const token=values[ix[j]];
      reject(token!==""&&token.trim()===token, "Missing native export");
      const num=Number(token);reject(Number.isFinite(num),"Nonfinite native export");
      o[FIELDS[j]]=num;
    }
    reject(o.time===i*10,"Native time grid mismatch");
    return o;
  });
  reject(result.length===2001,"Incomplete original trace");
  return result;
}
export function auditFullAgainstPreview(all, preview){
  const byTime=new Map(all.map(row=>[row.time,row]));
  for(const point of preview){
    const origin=byTime.get(point.time);
    reject(origin, "Preview timestamp missing in original");
    for(const field of FIELDS)reject(Object.is(point[field],origin[field])
      || point[field]===origin[field], "Preview and original disagree: "+field);
  }
  return true;
}
export async function sha256(bytes) {
  reject(typeof crypto!=="undefined"&&crypto.subtle,"SHA-256 requires HTTPS or localhost");
  const result=await crypto.subtle.digest("SHA-256",bytes);
  return Array.from(new Uint8Array(result),b=>b.toString(16).padStart(2,"0")).join("");
}
export async function verifyGitBlob(bytes) {
  reject(typeof crypto!=="undefined"&&crypto.subtle,"Git blob check needs a secure context");
  const prefix=new TextEncoder().encode("blob "+bytes.byteLength+"\0");
  const payload=new Uint8Array(prefix.length+bytes.byteLength);
  payload.set(prefix);payload.set(new Uint8Array(bytes),prefix.length);
  const hash=await crypto.subtle.digest("SHA-1",payload);
  const actual=Array.from(new Uint8Array(hash),n=>n.toString(16).padStart(2,"0")).join("");
  reject(actual===PREVIEW_GIT_BLOB_SHA1,"Bundled preview does not match pinned Git source blob");
  return true;
}
