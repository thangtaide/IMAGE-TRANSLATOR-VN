// Fake Chrome protocol, NOT a live browser acceptance test.
import assert from 'node:assert/strict';
const sent=[],listeners=[],startup=[];let queries=0,reads=0;
const port={onMessage:{addListener:f=>listeners.push(f)},onDisconnect:{addListener:()=>{}},postMessage:m=>sent.push(m)};
globalThis.chrome={runtime:{connectNative:()=>port,onMessage:{addListener:()=>{}},onStartup:{addListener:f=>startup.push(f)},onInstalled:{addListener:f=>startup.push(f)},id:'fixture',getURL:x=>'chrome-extension://fixture/'+x,getManifest:()=>({version:'0.3.0'})},
 tabs:{query:async filter=>{assert.deepEqual(filter.url,['https://tooncn.net/*']);queries++;return [{id:1,url:'https://tooncn.net/webtoon/123/'}];},
       get:async()=>({url:'https://tooncn.net/webtoon/123/',status:'complete'})},
 scripting:{executeScript:async()=>{reads++;return [{result:{ok:true,data:{version:1,kind:'tooncn_dom',page_url:'https://tooncn.net/webtoon/123/',title:'Fake',nodes:[]}}}];}}};
await import('../extensions/tooncn_bridge/background.js');
assert.deepEqual(sent[0],{kind:'hello',version:2,extension_version:'0.3.0'});
assert.equal(startup.length,2);
const emit=m=>listeners.forEach(f=>f(m));
emit({type:'request',op:'capture',id:'r0',session:'s',url:'https://tooncn.net/webtoon/123/'});
await new Promise(r=>setTimeout(r,30));assert.equal(queries,0);assert.equal(reads,0);
emit({type:'connection',enabled:true,session:'s'});
emit({type:'request',op:'capture',id:'r1',session:'s',url:'https://other.example/'});
await new Promise(r=>setTimeout(r,30));assert.equal(queries,0);
emit({type:'request',op:'capture',id:'r2',session:'s',url:'https://tooncn.net/webtoon/123/'});
await new Promise(r=>setTimeout(r,900));assert.equal(queries,1);assert.equal(reads,2);assert(sent.some(m=>m.id==='r2'&&m.ok));
emit({type:'connection',enabled:false,session:null});
emit({type:'request',op:'capture',id:'r3',session:'s',url:'https://tooncn.net/webtoon/123/'});
await new Promise(r=>setTimeout(r,30));assert.equal(queries,1);
console.log('Fake Chrome on-demand/OFF/scope checks passed.');
