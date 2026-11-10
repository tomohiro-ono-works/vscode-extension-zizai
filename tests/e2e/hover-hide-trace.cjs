"use strict";
const fs=require('node:fs/promises');
const path=require('node:path');
const crypto=require('node:crypto');
const assert=require('node:assert/strict');

// Non-pausing debugger logpoints: observe the close decision; never call UI actions or change editor state.
async function recordHoverHide(page,out) {
  const session=await page.context().newCDPSession(page);
  const scripts=[];
  const events=[];
  session.on('Debugger.scriptParsed',s=>scripts.push(s));
  session.on('Debugger.paused',async event=>{
    events.push({at:Date.now(),unexpectedPause:event.reason});
    await session.send('Debugger.resume').catch(()=>{});
  });
  session.on('Runtime.consoleAPICalled',event=>{
    const label=event.args[0]?.value;
    if (typeof label!=='string' || !label.startsWith('[ZIZAI_HOVER_')) return;
    let data;
    try { data=JSON.parse(event.args[1]?.value); } catch { data=event.args[1]?.value; }
    if(events.length<1500) events.push({at:Date.now(),label,data,stack:event.stackTrace?.callFrames});
  });
  await session.send('Runtime.enable');
  await session.send('Debugger.enable');
  const script=scripts.find(s=>s.url.includes('/workbench.desktop.main.js'));
  assert(script,'Workbench renderer script must be known');
  const {scriptSource:source}=await session.send('Debugger.getScriptSource',{scriptId:script.scriptId});
  const marker='hideContentHover(){';
  const index=source.indexOf(marker);
  assert(index>=0 && source.indexOf(marker,index+marker.length)<0,'Unique ContentHoverController method required');
  const context=`const m=this._mouseMoveEvent; const node=this._contentWidget?.getDomNode(); return {settings:this._hoverSettings,isMouseDown:this._isMouseDown,connected:node?.isConnected,text:node?.textContent,mouse:m&&{x:m.event.posx,y:m.event.posy,targetClass:String(m.event.target?.className||''),targetType:m.target.type,position:m.target.position,range:m.target.range,targetWithin:!!node?.contains(m.event.target)}};`;
  const condition=`(this._contentWidget?.isVisible && console.trace('[ZIZAI_HOVER_HIDE]',JSON.stringify((()=>{${context}})())),false)`;
  const points=[];
  async function point(offset,condition) {
    const before=source.slice(0,offset);
    const location={scriptId:script.scriptId,lineNumber:(before.match(/\n/g)||[]).length,columnNumber:offset-before.lastIndexOf('\n')-1};
    const result=await session.send('Debugger.setBreakpoint',{location,condition});
    points.push({id:result.breakpointId,location:result.actualLocation});
  }
  await point(index+marker.length,condition);
  const matches=[...source.matchAll(/_setCurrentResult\((\w+)\)\{/g)];
  assert.equal(matches.length,1,'Unique hover result method required');
  const clear=matches[0], arg=clear[1];
  await point(clear.index+clear[0].length,`(this._contentHoverWidget?.isVisible && console.trace('[ZIZAI_HOVER_RESULT]',JSON.stringify({nextNull:${arg}===null,nextParts:${arg}?.hoverParts?.length,oldRange:this._currentResult?.options.anchor.range,nextRange:${arg}?.options.anchor.range,text:this._contentHoverWidget.getDomNode().textContent,initialX:this._contentHoverWidget._renderedHover?.initialMousePosX,initialY:this._contentHoverWidget._renderedHover?.initialMousePosY,closestDistance:this._contentHoverWidget._renderedHover?.closestMouseDistance})),false)`);
  return async ()=>{
    for(const p of points) await session.send('Debugger.removeBreakpoint',{breakpointId:p.id});
    await session.send('Debugger.disable');
    await session.detach();
    const data={scriptUrl:script.url,scriptSha256:crypto.createHash('sha256').update(source).digest('hex'),points,events};
    await fs.writeFile(path.join(out,'hover-hide.local.json'),JSON.stringify(data,null,2));
    return {localFile:'hover-hide.local.json',events:events.length,scriptSha256:data.scriptSha256};
  };
}
module.exports={recordHoverHide};
