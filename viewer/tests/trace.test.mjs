import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {createHash} from "node:crypto";
import {fileURLToPath} from "node:url";
import {validatePreview,parseOriginalCsv,auditFullAgainstPreview,reversalBracket,energyLedger,flowLabel,
  PREVIEW_GIT_BLOB_SHA1,SOURCE_CSV_SHA256,FIELDS} from "../trace.mjs";
const file=fileURLToPath(new URL("../data/bridge-preview.json",import.meta.url));
const bytes=readFileSync(file);
const blob=Buffer.concat([Buffer.from("blob "+bytes.length+"\0"),bytes]);
const raw=JSON.parse(bytes.toString("utf8"));
const rec=()=>validatePreview(structuredClone(raw));
test("preview is exactly the source-pinned Git blob",()=>{
  assert.equal(createHash("sha1").update(blob).digest("hex"),PREVIEW_GIT_BLOB_SHA1);
  assert.equal(raw.originalCsvSha256,SOURCE_CSV_SHA256);
  assert.equal(raw.nativeQualified,false);
});
test("23 saved native samples, correct bridge reversal bracket, no invented timestamp",()=>{
  const data=rec();assert.equal(data.length,23);assert.equal(data[0].time,0);
  assert.equal(data.at(-1).time,20000);
  assert.equal(data[0]["bridge.Q_flow"],-6);
  assert.equal(data.at(-1)["bridge.Q_flow"],2.0286508853152214);
  assert.deepEqual(reversalBracket(data),{from:1720,to:1730,index:3});
  assert.equal(flowLabel(data[2]["bridge.Q_flow"]),"Right → left");
  assert.equal(flowLabel(data[3]["bridge.Q_flow"]),"Left → right");
});
test("energy readout preserves joules separately from reservoir watts",()=>{
  const e=energyLedger(rec().at(-1));
  assert.equal(e.leftJ,15155.825150610235);
  assert.equal(e.rightJ,-21693.43515726092);
  assert.equal(e.totalJ,e.leftJ+e.rightJ);
  assert.equal(e.hotW,9.933899640855579);
  assert.equal(e.coldW,-9.945704215565364);
});
test("false qualification, missing fields, nonfinite values, interpolation and duplicate times refuse",()=>{
  const variants=[
    p=>{p.nativeQualified=true;},
    p=>{p.columns[3]="unknown";},
    p=>{p.data.pop();},
    p=>{p.data[2][0]=1725;},
    p=>{p.data[3][0]=1720;},
    p=>{p.data[0][4]=null;},
    p=>{p.data[2][3]=8;},
  ];
  for(const change of variants){const p=structuredClone(raw);change(p);assert.throws(()=>validatePreview(p));}
});
test("CSV parser refuses missing original samples, incomplete columns and terminal tampering",()=>{
  assert.throws(()=>parseOriginalCsv("time,left.T\n0,300\n"));
  const hdr=FIELDS.join(",");
  const synthetic=Array.from({length:2001},(_,i)=>FIELDS.map((f,j)=>j===0?String(i*10):"1").join(","));
  const last=synthetic.at(-1);
  const ok=[hdr,...synthetic,last].join("\n")+"\n";
  const rows=parseOriginalCsv(ok);
  assert.equal(rows.length,2001);
  assert.equal(rows[172].time,1720);
  assert.throws(()=>parseOriginalCsv([hdr,...synthetic,last.replace(/,1$/,",2")].join("\n")));
  assert.throws(()=>parseOriginalCsv([hdr,...synthetic.slice(0,-1),last].join("\n")));
  const shifted=[...synthetic];shifted[100]="1000.001"+synthetic[100].slice(4);
  assert.throws(()=>parseOriginalCsv([hdr,...shifted,last].join("\n")));
});
test("preview-vs-full byte-decoded values must agree at every selected time",()=>{
  const preview=rec();
  const rows=Array.from({length:2001},(_,i)=>Object.fromEntries(FIELDS.map(f=>[f,f==="time"?i*10:0])));
  for(const p of preview)rows[p.time/10]=structuredClone(p);
  assert.equal(auditFullAgainstPreview(rows,preview),true);
  rows[173]["bridge.Q_flow"]+=1e-10;
  assert.throws(()=>auditFullAgainstPreview(rows,preview));
});
test("static viewer has no solver or native-runner use",()=>{
  const html=readFileSync(fileURLToPath(new URL("../index.html",import.meta.url)),"utf8");
  const core=readFileSync(fileURLToPath(new URL("../trace.mjs",import.meta.url)),"utf8");
  for(const suspect of ["buildModel(", "simulate(", "omc --version", "eval(", "new Function("]){
    assert.equal((html+core).includes(suspect),false,suspect);
  }
  assert.match(html,/Logical graph only/);
  assert.match(html,/not independent measurements/);
});
