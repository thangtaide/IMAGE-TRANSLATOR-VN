// Fixed, observed reader scope. No cookie/storage/header extraction or arbitrary JS.
export async function fetchReaderImage(expectedPage,publicSource){
  const fail=code=>({ok:false,code});
  if(location.origin!=='https://tooncn.net'||location.origin+location.pathname!==expectedPage)return fail('UNEXPECTED_NAVIGATION');
  const strip=value=>{try{const u=new URL(value,location.href);return u.origin==='https://tooncn.net'&&!u.username&&!u.password?u.origin+u.pathname:null;}catch{return null;}};
  if(!publicSource.startsWith('https://tooncn.net/wp-content/uploads/'))return fail('IMAGE_SOURCE_CHANGED');
  const candidates=[...document.querySelectorAll('#readerarea img.ts-main-image')];
  let actual=null;
  for(const image of candidates){
    const urls=[image.getAttribute('data-src'),image.getAttribute('data-lazy-src'),image.currentSrc,image.getAttribute('src')];
    actual=urls.find(value=>value&&strip(value)===publicSource);
    if(actual)break;
  }
  if(!actual)return fail('IMAGE_SOURCE_CHANGED');
  const controller=new AbortController();globalThis.__itvnToonCNAbort=controller;
  const timer=setTimeout(()=>controller.abort(),25000),limit=8*1024*1024;
  try{
    const response=await fetch(new URL(actual,location.href).href,{credentials:'same-origin',redirect:'error',signal:controller.signal});
    if(response.status===429)return fail('RATE_LIMITED');
    if(response.status===401||response.status===403)return fail('ACCESS_DENIED');
    if(response.status!==200)return fail('IMAGE_UNAVAILABLE');
    const mime=(response.headers.get('Content-Type')||'').split(';')[0].trim().toLowerCase();
    if(!['image/jpeg','image/png','image/webp','image/bmp'].includes(mime))return fail('INVALID_RESPONSE');
    const encoding=(response.headers.get('Content-Encoding')||'identity').toLowerCase();
    const declared=encoding==='identity'?response.headers.get('Content-Length'):null;
    if(declared&&(!/^\d+$/.test(declared)||Number(declared)>limit))return fail('IMAGE_LIMIT');
    const reader=response.body.getReader(),parts=[];let size=0;
    while(true){
      const {done,value}=await reader.read();if(done)break;
      size+=value.length;
      if(size>limit){await reader.cancel();return fail('IMAGE_LIMIT');}
      parts.push(value);
    }
    if(!size||(declared&&Number(declared)!==size))return fail('INVALID_RESPONSE');
    const joined=new Uint8Array(size);let offset=0;
    for(const part of parts){joined.set(part,offset);offset+=part.length;}
    let binary='';for(let i=0;i<size;i+=16384)binary+=String.fromCharCode(...joined.subarray(i,i+16384));
    return {ok:true,mime,bytes:size,base64:btoa(binary)};
  }catch(error){return fail(error.name==='AbortError'?'BROWSER_TIMEOUT':'NETWORK_ERROR');}
  finally{clearTimeout(timer);delete globalThis.__itvnToonCNAbort;}
}
