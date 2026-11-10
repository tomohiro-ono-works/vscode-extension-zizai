"use strict";
const fs=require('node:fs/promises');
const path=require('node:path');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');

// Add logging to a newly installed, owned test copy only; retain its original bytes.
async function instrumentInstalledExtension(extensions,out) {
  const dirs=(await fs.readdir(extensions)).filter(name=>name.startsWith('zizai-lab.zizai-notebook-input-'));
  assert.equal(dirs.length,1);
  const file=path.join(extensions,dirs[0],'extension.cjs');
  const before=await fs.readFile(file,'utf8');
  let code=before;
  function replace(needle,value) { assert(code.includes(needle),needle); code=code.replace(needle,value); }
  const log=JSON.stringify(path.join(out,'extension-events.local.jsonl'));
  replace('const PICK_PATH = "zizai.pickPath";', 'const PICK_PATH = "zizai.pickPath";\nconst trace=(kind,data)=>require("node:fs").appendFileSync('+log+',JSON.stringify({at:Date.now(),kind,...data})+"\\n");');
  replace('async function setValue(request) {','async function setValue(request) { trace("request",{field:request?.field,value:request?.value,version:request?.version});');
  replace('const applied = await vscode.workspace.applyEdit(edit);','trace("apply-send",{field:field.field,version:document.version});\n      const applied = await vscode.workspace.applyEdit(edit);\n      trace("apply-return",{field:field.field,version:document.version,applied});');
  replace('if (applied) await vscode.commands.executeCommand("editor.action.hideHover");','if (applied) { trace("hide-send",{field:field.field,version:document.version}); await vscode.commands.executeCommand("editor.action.hideHover"); trace("hide-return",{field:field.field,version:document.version}); }');
  replace('provideHover(document, position) {','provideHover(document, position) { trace("hover",{line:position.line,character:position.character,version:document.version,settings:vscode.workspace.getConfiguration("editor",document).get("hover")});');
  replace('editor.setDecorations(decoration, fields.map(field => {','trace("decoration-set",{version:document.version,scheme:document.uri.scheme,fields:fields.map(f=>({field:f.field,start:f.start,end:f.end,label:f.label}))});\n      editor.setDecorations(decoration, fields.map(field => {');
  await fs.writeFile(path.join(out,'extension-before-trace.local.cjs'),before,{flag:'wx'});
  await fs.writeFile(file,code);
  const hash=text=>crypto.createHash('sha256').update(text).digest('hex');
  return {instrumentedCopy:true,originalSha256:hash(before),instrumentedSha256:hash(code),localFile:'extension-events.local.jsonl'};
}

async function recordHoverLifecycle(page,out) {
  await page.evaluate(()=>{
    const events=[];
    const ids=new WeakMap();let seq=0;
    const id=e=>{if(!ids.has(e))ids.set(e,++seq);return ids.get(e);};
    const add=(kind,data={})=>{if(events.length<4000)events.push({at:Date.now(),kind,focused:document.hasFocus(),visibility:document.visibilityState,...data});};
    const describe=e=>e instanceof Element?{id:id(e),class:String(e.className?.baseVal??e.className??'')}:null;
    const snapshot=()=>[...document.querySelectorAll('.monaco-resizable-hover')].map(root=>({id:id(root),style:root.getAttribute('style'),class:root.className,
      innerClass:root.querySelector('.monaco-hover')?.className,
      links:[...root.querySelectorAll('a')].map(link=>{
        const href=link.getAttribute('data-href')||link.getAttribute('href')||'';
        let request;
        try {if(href.startsWith('command:zizai.'))request=JSON.parse(decodeURIComponent(href.slice(href.indexOf('?')+1)))[0];}catch{}
        return {text:link.textContent,field:request?.field,version:request?.version};
      })}));
    const focus=e=>{if(e.target===window)add('window-'+e.type);};
    const visibility=()=>add('visibility');
    const mouse=e=>{
      const t=e.target instanceof Element?e.target:null,r=e.relatedTarget instanceof Element?e.relatedTarget:null;
      if(!t?.closest('.monaco-resizable-hover')&&!r?.closest('.monaco-resizable-hover'))return;
      add(e.type,{x:e.clientX,y:e.clientY,buttons:e.buttons,target:describe(t),related:describe(r)});
    };
    window.addEventListener('focus',focus);window.addEventListener('blur',focus);
    document.addEventListener('visibilitychange',visibility);
    document.addEventListener('mouseover',mouse,{capture:true,passive:true});
    document.addEventListener('mouseout',mouse,{capture:true,passive:true});
    let last='';
    const observer=new MutationObserver(()=>{const roots=snapshot(),key=JSON.stringify(roots);if(key===last)return;last=key;add('hover-state',{roots});});
    observer.observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:['class','style']});
    add('start');
    window.__zizaiHoverLifecycle={events,stop(){observer.disconnect();window.removeEventListener('focus',focus);window.removeEventListener('blur',focus);document.removeEventListener('visibilitychange',visibility);document.removeEventListener('mouseover',mouse,true);document.removeEventListener('mouseout',mouse,true);}};
  });
  return async()=>{
    const events=await page.evaluate(()=>{const t=window.__zizaiHoverLifecycle;t.stop();delete window.__zizaiHoverLifecycle;return t.events;});
    await fs.writeFile(path.join(out,'hover-lifecycle.local.json'),JSON.stringify(events,null,2));
    return {events:events.length,localFile:'hover-lifecycle.local.json'};
  };
}
module.exports={instrumentInstalledExtension,recordHoverLifecycle};
