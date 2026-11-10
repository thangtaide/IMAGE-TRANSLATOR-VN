// Synthetic DOM projection tests, NOT fixtures of the actual ToonCN reader.
import assert from 'node:assert/strict';
import {captureToonCN} from '../extensions/tooncn_bridge/capture.mjs';
class Element{
  constructor(tag,attrs={},parent=null,text=''){
    this.tagName=tag.toUpperCase();this.attrs=attrs;this.parentElement=parent;
    this.childNodes=[{nodeType:3,textContent:text}];this.naturalWidth=800;this.naturalHeight=1200;this.complete=true;
  }
  getAttribute(n){return this.attrs[n]||null;}
  closest(){return this.excluded?this:null;}
  getBoundingClientRect(){return {width:800,height:1200};}
}
function setup(){
  globalThis.location=new URL('https://tooncn.net/webtoon/123/');
  globalThis.Node={TEXT_NODE:3};globalThis.getComputedStyle=()=>({display:'block',visibility:'visible'});
  const container=new Element('article',{id:'fixture-reader'});
  const first=new Element('img',{src:'https://cdn.example/002.jpg?token=DO_NOT_EXPORT',alt:'fixture'},container);
  const second=new Element('img',{'data-src':'https://cdn.example/001.jpg'},container);
  const formText=new Element('p',{},null,'DO_NOT_EXPORT');formText.excluded=true;
  globalThis.document={readyState:'complete',title:'Fixture page, NOT live ToonCN',body:{
    innerText:'Fixture',querySelectorAll:()=>[container,first,second,formText]}};
}
setup();let d=captureToonCN();assert.equal(d.ok,true);assert.equal(d.data.nodes.length,3);
assert.equal(d.data.nodes[1].attributes.src,'https://cdn.example/002.jpg');
assert.equal(d.data.nodes[2].attributes.data_src,'https://cdn.example/001.jpg');
assert.equal(d.data.nodes[2].parent,0);assert(!JSON.stringify(d).includes('DO_NOT_EXPORT'));
setup();document.title='Just a moment...';assert.equal(captureToonCN().code,'CHALLENGE_PENDING');
setup();document.body.innerText='Sorry, you have been blocked';assert.equal(captureToonCN().code,'ACCESS_DENIED');
setup();document.readyState='loading';assert.equal(captureToonCN().code,'PAGE_NOT_READY');
setup();globalThis.location=new URL('https://other.example/');assert.equal(captureToonCN().code,'TOONCN_TAB_REQUIRED');
setup();globalThis.location=new URL('https://tooncn.net/account/');assert.equal(captureToonCN().code,'TOONCN_TAB_REQUIRED');
setup();document.body.querySelectorAll=()=>Array(20001).fill({});assert.equal(captureToonCN().code,'DOM_LIMIT');
setup();document.body.querySelectorAll=()=>[];assert.equal(captureToonCN().code,'PAGE_NOT_READY');
console.log('Synthetic DOM capture checks passed; no live browser or site used.');
