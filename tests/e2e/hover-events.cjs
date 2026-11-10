"use strict";
const fs = require('node:fs/promises');
const path = require('node:path');

// Passive observation only. Inputs still come exclusively from Playwright's mouse/keyboard.
async function recordHoverEvents(page, out) {
  await page.evaluate(() => {
    const events = [];
    const ids = new WeakMap();
    let sequence = 0;
    const id = node => { if (!ids.has(node)) ids.set(node,++sequence); return ids.get(node); };
    const element = node => node instanceof Element ? node : node?.parentElement;
    const describe = node => {
      const e = element(node);
      if (!e) return null;
      return { id:id(e),tag:e.tagName,class:String(e.className?.baseVal ?? e.className ?? ''),
        ancestors:[e.parentElement,e.parentElement?.parentElement,e.parentElement?.parentElement?.parentElement].filter(Boolean).map(x=>({id:id(x),class:String(x.className)})) };
    };
    const roots = (target, related) => [...document.querySelectorAll('.monaco-resizable-hover')].map(e => {
      const rect = e.getBoundingClientRect();
      const style = getComputedStyle(e);
      const owner = e.closest('.monaco-editor');
      return { id:id(e),visible:rect.width>0 && rect.height>0 && style.display!=='none' && style.visibility!=='hidden',
        rect:rect.toJSON(), inner:e.querySelector('.monaco-hover')?.getBoundingClientRect().toJSON(),
        owner:describe(owner),targetWithin:!!target && e.contains(target),relatedWithin:!!related && e.contains(related) };
    });
    const append = item => { if (events.length>=6000) events.splice(0,1000); events.push({at:Date.now(),...item}); };
    const types = ['pointermove','mousemove','mouseover','mouseout','mousedown','mouseup'];
    const listener = event => {
      const target = element(event.target), related = element(event.relatedTarget);
      if (!target?.closest('.monaco-editor,.monaco-resizable-hover') && !related?.closest('.monaco-editor,.monaco-resizable-hover')) return;
      append({type:event.type,trusted:event.isTrusted,client:{x:event.clientX,y:event.clientY},page:{x:event.pageX,y:event.pageY},
        buttons:event.buttons,button:event.button,target:describe(target),related:describe(related),
        hit:describe(document.elementFromPoint(event.clientX,event.clientY)),roots:roots(target,related)});
    };
    for (const type of types) document.addEventListener(type,listener,{capture:true,passive:true});
    let last = '';
    const observer = new MutationObserver(() => {
      const state = roots(null,null);
      const key = JSON.stringify(state.map(r=>({id:r.id,visible:r.visible,rect:r.rect})));
      if (key===last) return;
      last=key;
      append({type:'hover-state',roots:state});
    });
    observer.observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:['class','style']});
    window.__zizaiPassiveHoverTrace = { events,environment:{devicePixelRatio,innerWidth,innerHeight,visualViewport:{scale:visualViewport?.scale,offsetLeft:visualViewport?.offsetLeft,offsetTop:visualViewport?.offsetTop}},
      stop() { observer.disconnect(); for (const type of types) document.removeEventListener(type,listener,true); } };
  });
  return async () => {
    const trace = await page.evaluate(() => {
      const trace=window.__zizaiPassiveHoverTrace;
      trace.stop();
      const data={environment:trace.environment,events:trace.events};
      delete window.__zizaiPassiveHoverTrace;
      return data;
    });
    const file=path.join(out,'hover-events.local.json');
    await fs.writeFile(file,JSON.stringify(trace,null,2));
    return {localFile:'hover-events.local.json',events:trace.events.length,environment:trace.environment};
  };
}
module.exports={recordHoverEvents};
