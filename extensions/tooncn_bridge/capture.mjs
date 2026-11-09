// Serialized into Chrome's isolated world only for an active app request.
// A generic, filtered DOM projection, NOT a guessed ToonCN chapter/image parser.
export function captureToonCN(){
  const fail=code=>({ok:false,code});
  if(location.origin!=='https://tooncn.net')return fail('TOONCN_TAB_REQUIRED');
  if(/(?:login|logout|wp-admin|wp-login|account|password|authorization|credential|session|token)/i.test(location.pathname))return fail('TOONCN_TAB_REQUIRED');
  if(document.readyState!=='complete'||!document.body)return fail('PAGE_NOT_READY');
  const title=document.title;
  const firstText=(document.body.innerText||'').slice(0,1500);
  if(/just a moment|checking your browser|verify you are human|verifying you are human/i.test(title+'\n'+firstText))return fail('CHALLENGE_PENDING');
  if(/sorry, you have been blocked|access denied|you do not have permission/i.test(firstText))return fail('ACCESS_DENIED');
  const clean=(s,max)=>String(s||'').replace(/[\x00-\x1f\x7f]/g,' ').replace(/\s+/g,' ').trim().slice(0,max);
  function publicURL(value,sameSite=false){
    if(!value)return null;
    try{
      const u=new URL(value,location.href);
      if(u.protocol!=='https:'||u.username||u.password||(u.port&&u.port!=='443'))return null;
      if(!/^[a-z0-9.-]+$/.test(u.hostname)||/^(?:\d+\.){3}\d+$/.test(u.hostname)||u.hostname==='localhost'||/\.(?:local|internal|localhost)$/.test(u.hostname))return null;
      if(sameSite&&u.hostname!=='tooncn.net')return null;
      if(/(?:login|logout|wp-admin|wp-login|account|password|authorization|credential|session|token)/i.test(u.pathname))return null;
      if(u.pathname.split('/').some(part=>part.length>160))return null;
      // Never export query/fragment values, including signed resource tokens.
      return (u.origin+u.pathname).length<=2048?u.origin+u.pathname:null;
    }catch{return null;}
  }
  // Observed content containers, omit sidebars/recommendations when available.
  const root=document.querySelector?.('#content .postbody article, #content .chapterbody')||document.body;
  const elements=root.querySelectorAll('*');
  if(elements.length>20000)return fail('DOM_LIMIT');
  const rows=[],ids=new Map();
  const excluded='script,style,noscript,template,iframe,form,input,textarea,select,button,header,nav,footer,[contenteditable],#comments,.comments-area';
  const tags=new Set(['main','article','section','div','aside','h1','h2','h3','p','span','strong','b','ul','ol','li','a','img','figure','figcaption','picture','source']);
  for(const el of elements){
    const tag=el.tagName.toLowerCase();
    if(!tags.has(tag)||el.closest(excluded))continue;
    const rect=el.getBoundingClientRect(),style=getComputedStyle(el);
    if(style.display==='none'||style.visibility==='hidden'||(!rect.width&&!rect.height))continue;
    let parent=el.parentElement;
    while(parent&&!ids.has(parent))parent=parent.parentElement;
    const attributes={};
    for(const name of ['id','class']){
      const value=clean(el.getAttribute(name),200);
      if(value&&!/(?:token|secret|credential|password|session|authorization)/i.test(value))attributes[name]=value;
    }
    if(tag==='a'){
      const value=publicURL(el.getAttribute('href'),true);if(value)attributes.href=value;
    }
    if(tag==='img'||tag==='source'){
      for(const [name,value] of [['src',el.getAttribute('src')],['current_src',el.currentSrc],['data_src',el.getAttribute('data-src')],['data_lazy_src',el.getAttribute('data-lazy-src')]]){
        const safe=publicURL(value);if(safe)attributes[name]=safe;
      }
      const srcset=el.getAttribute('srcset');
      if(srcset){
        const values=srcset.split(',').map(x=>publicURL(x.trim().split(/\s+/)[0])).filter(Boolean);
        if(values.length>12)return fail('DOM_LIMIT');
        if(values.length)attributes.srcset=values;
      }
      attributes.alt=clean(el.getAttribute('alt'),200);
      if(tag==='img'){
        attributes.natural_width=Math.min(100000,el.naturalWidth||0);
        attributes.natural_height=Math.min(100000,el.naturalHeight||0);
        attributes.loaded=!!el.complete&&el.naturalWidth>0;
      }
    }
    const text=clean([...el.childNodes].filter(n=>n.nodeType===Node.TEXT_NODE).map(n=>n.textContent).join(' '),400);
    const index=rows.length;ids.set(el,index);
    rows.push({index,parent:parent?ids.get(parent):null,tag,attributes,text});
    if(rows.length>4000)return fail('DOM_LIMIT');
  }
  if(!rows.length)return fail('PAGE_NOT_READY');
  const data={version:1,kind:'tooncn_dom',page_url:location.origin+location.pathname,title:clean(title,200),nodes:rows};
  if(new TextEncoder().encode(JSON.stringify(data)).length>900000)return fail('DOM_LIMIT');
  return {ok:true,data};
}
