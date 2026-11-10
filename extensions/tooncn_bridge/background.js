import {captureToonCN} from './capture.mjs';
import {fetchReaderImage} from './image.mjs';
const HOST='vn.imagetranslator.tooncn';
let port=null,enabled=false,session=null,busy=false,reconnects=0,ownedTab=null;
let state='WAITING_APP';
let activeTab=null;const acknowledgements=new Map();
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const publicURL=value=>{
  try{const u=new URL(value);return u.origin==='https://tooncn.net'&&!/(?:login|logout|wp-admin|wp-login|account|password|authorization|credential|session|token)/i.test(u.pathname)?u.origin+u.pathname:null;}catch{return null;}
};
function connect(){
  if(port)return;
  try{
    port=chrome.runtime.connectNative(HOST);
    port.onMessage.addListener(message=>{
      reconnects=0;
      if(message.type==='connection'){
        enabled=message.enabled===true;session=enabled?message.session:null;state=enabled?'CONNECTED':'OFF';
        if(!enabled&&activeTab!==null)void chrome.scripting.executeScript({target:{tabId:activeTab},func:()=>globalThis.__itvnToonCNAbort?.abort()}).catch(()=>{});
      }else if(message.type==='image_ack'){
        const key=message.id+':'+message.sequence,done=acknowledgements.get(key);
        if(done){acknowledgements.delete(key);done();}
      }else if(message.type==='request')void request(message);
    });
    port.onDisconnect.addListener(()=>{
      void chrome.runtime.lastError;
      port=null;enabled=false;session=null;state='NATIVE_HOST_UNAVAILABLE';
      if(++reconnects<=3)setTimeout(connect,5000*reconnects);
    });
    port.postMessage({kind:'hello',version:2,extension_version:chrome.runtime.getManifest().version});
  }catch{port=null;state='NATIVE_HOST_UNAVAILABLE';}
}
async function chooseTab(url,openMissing){
  const tabs=await chrome.tabs.query({url:['https://tooncn.net/*']});
  const found=tabs.find(tab=>publicURL(tab.url)===url);
  if(found)return found.id;
  if(!openMissing)throw Error('TAB_NOT_OPEN');
  if(ownedTab!==null){
    try{
      const old=await chrome.tabs.get(ownedTab);
      if(publicURL(old.url)){
        await chrome.tabs.update(ownedTab,{url,active:false});return ownedTab;
      }
    }catch{/* Never touch a user tab that navigated away from ToonCN. */}
    ownedTab=null;
  }
  const created=await chrome.tabs.create({url,active:false});ownedTab=created.id;return created.id;
}
async function request(command){
  if(!enabled||command.session!==session||busy||!['capture','image'].includes(command.op)||publicURL(command.url)!==command.url)return;
  busy=true;const owner=session;state='READING_REQUESTED_PAGE';
  let result;
  try{
    const tabId=await chooseTab(command.url,command.open_missing===true);
    activeTab=tabId;
    const deadline=Date.now()+90000;let previous=null,stable=0;
    while(Date.now()<deadline){
      if(!enabled||owner!==session)throw Error('CONNECTION_OFF');
      const tab=await chrome.tabs.get(tabId);
      if(tab.status!=='complete'){await pause(1000);continue;}
      if(publicURL(tab.url)!==command.url)throw Error('UNEXPECTED_NAVIGATION');
      if(command.op==='image'){
        const rows=await chrome.scripting.executeScript({target:{tabId},func:fetchReaderImage,args:[command.url,command.image_src]});
        const image=rows.length===1?rows[0].result:null;
        if(!image?.ok)throw Error(image?.code||'INVALID_RESPONSE');
        if(!enabled||owner!==session)throw Error('CONNECTION_OFF');
        const send=async(message,sequence)=>{
          const key=command.id+':'+sequence;
          await new Promise((resolve,reject)=>{
            const timer=setTimeout(()=>{acknowledgements.delete(key);reject(Error('BROWSER_TIMEOUT'));},10000);
            acknowledgements.set(key,()=>{clearTimeout(timer);resolve();});
            port.postMessage({id:command.id,session:owner,...message});
          });
        };
        await send({kind:'image_start',mime:image.mime,bytes:image.bytes},-1);
        let sequence=0;
        for(let i=0;i<image.base64.length;i+=240000){
          if(!enabled||owner!==session)throw Error('CONNECTION_OFF');
          await send({kind:'image_chunk',sequence,data:image.base64.slice(i,i+240000)},sequence);sequence++;
        }
        port.postMessage({id:command.id,session:owner,kind:'image_end',chunks:sequence});
        result={transferred:true};break;
      }
      const rows=await chrome.scripting.executeScript({target:{tabId},func:captureToonCN});
      const captured=rows.length===1?rows[0].result:null;
      if(!captured?.ok){
        if(captured?.code==='PAGE_NOT_READY'){await pause(1000);continue;}
        throw Error(captured?.code||'INVALID_RESPONSE');
      }
      const fingerprint=JSON.stringify(captured.data);
      stable=fingerprint===previous?stable+1:0;previous=fingerprint;
      if(stable>=1){result={ok:true,data:captured.data};break;}
      await pause(750);
    }
    if(!result)throw Error('BROWSER_TIMEOUT');
  }catch(error){
    const codes=['TOONCN_TAB_REQUIRED','PAGE_NOT_READY','CHALLENGE_PENDING','ACCESS_DENIED','DOM_LIMIT',
      'TAB_NOT_OPEN','UNEXPECTED_NAVIGATION','BROWSER_TIMEOUT','CONNECTION_OFF','INVALID_RESPONSE',
      'IMAGE_UNAVAILABLE','IMAGE_LIMIT','IMAGE_SOURCE_CHANGED','RATE_LIMITED','NETWORK_ERROR'];
    result={ok:false,code:codes.includes(error.message)?error.message:'BRIDGE_FAILED'};
  }finally{
    if(port&&enabled&&owner===session&&!result?.transferred)port.postMessage({id:command.id,session:owner,...result});
    busy=false;activeTab=null;state=enabled?'CONNECTED':'OFF';
  }
}
chrome.runtime.onMessage.addListener((message,sender,reply)=>{
  if(sender.id!==chrome.runtime.id||sender.url!==chrome.runtime.getURL('popup.html'))return;
  if(message.kind==='status'){connect();reply({state,enabled});}
});
// Local IPC stays ready. While OFF no tab query or DOM read occurs.
chrome.runtime.onStartup.addListener(connect);
chrome.runtime.onInstalled.addListener(connect);
connect();
