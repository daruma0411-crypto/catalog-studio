import {esc} from './ui.js';

export function assetURL(ctx,id){return `/api/catalogs/${ctx.state.id}/assets/${encodeURIComponent(id)}`;}
function boundsStyle(b){return `left:${b[0]}px;top:${b[1]}px;width:${Math.max(b[2],1)}px;height:${Math.max(b[3],1)}px;`;}
function textRuns(e){if(e.modified||!e.runs)return esc(e.text||'');return e.runs.map(r=>`<span style="font-size:${r.size||8}px;font-weight:${r.bold?700:400};color:${esc(r.color||'#202020')}">${esc(r.text)}</span>`).join('');}

export function paperContent(ctx,page){
 const reference=ctx.mode!=='html'&&!!page.reference_asset;
 const original=ctx.mode==='original';
 let html=reference?`<img class="reference" src="${assetURL(ctx,page.reference_asset)}" alt="原版PDFの紙面">`:'';
 const hits=[];
 if(reference&&!original)for(const r of page.removed_regions||[])html+=`<div class="element moved-mask" style="${boundsStyle(r.bounds)}"></div>`;
 page.elements.forEach((e,i)=>{
  const b=e.bounds;
  if(reference&&!original&&(e.modified||e.deleted)&&e.source?.page_id===page.id&&e.source?.original_bounds&&JSON.stringify(e.source.original_bounds)!==JSON.stringify(b))html+=`<div class="element moved-mask" style="${boundsStyle(e.source.original_bounds)}"></div>`;
  if(e.deleted){if(reference&&!original)html+=`<div class="element deleted-mask" style="${boundsStyle(b)}">削除指定</div>`;return;}
  if(!reference||(!original&&e.modified)){
   let inner='',style=boundsStyle(b)+`z-index:${i+1};`;
   if(e.kind==='text'){
    style+=`font-size:${e.font_size||8}px;background:${e.modified?'white':esc(e.fill||'transparent')};`;
    if(e.padding&&!e.modified)style+=`padding:${e.padding.map(v=>v+'px').join(' ')};`;
    if(e.border_bottom)style+=`border-bottom:${e.border_bottom}px solid #333;`;
    inner=textRuns(e);
   }else if(e.kind==='image'){inner=e.asset_id?`<img src="${assetURL(ctx,e.asset_id)}" alt="${esc(e.name)}">`:'<span style="font-size:8px">画像未解決</span>';if(e.modified)style+='background:white;';}
   else if(e.kind==='shape')style+=`background:${esc(e.fill||'transparent')};border:${e.stroke_width||0}px solid ${esc(e.stroke||'#333')};`;
   else{inner='連結先は要確認';style+='font-size:8px;border:1px dashed #bb8e2c;';}
   html+=`<div class="element ${e.kind}" data-render-id="${esc(e.id)}" style="${style}">${inner}</div>`;
  }
  if(!original&&(e.kind==='text'||e.kind==='image'))hits.push(`<button type="button" class="element-hit ${ctx.selection===e.id?'selected':''}" data-element="${esc(e.id)}" aria-label="${esc((e.kind==='text'?e.text:e.name).slice(0,90))}" style="${boundsStyle(b)}z-index:${1000+i}"></button>`);
 });
 return html+hits.join('');
}

export function renderPaper(ctx){
 const page=ctx.currentPage();if(!page)return;
 const stage=document.getElementById('stage');if(!stage)return;
 const available=Math.max(220,stage.clientWidth-60);
 const scale=ctx.zoom==='fit'?Math.min(1.3,available/page.width):Number(ctx.zoom);
 ctx.scale=scale;
 stage.innerHTML=`<div class="page-shell" style="width:${page.width*scale}px;height:${page.height*scale}px"><div class="paper" id="paper" style="width:${page.width}px;height:${page.height}px;transform:scale(${scale})">${paperContent(ctx,page)}</div></div>`;
 const input=document.getElementById('zoom-label');if(input)input.textContent=Math.round(scale*100)+'%';
 stage.querySelectorAll('[data-element]').forEach(hit=>{
  hit.addEventListener('click',()=>{if(ctx.dragMoved)return;ctx.selection=hit.dataset.element;ctx.renderInspector();stage.querySelectorAll('.element-hit').forEach(el=>el.classList.toggle('selected',el.dataset.element===ctx.selection));});
  if(ctx.actor.role!=='editor')return;
  let drag=null;
  hit.addEventListener('pointerdown',event=>{
   if(event.button!==0||ctx.selection!==hit.dataset.element)return;
   const el=ctx.element();if(!el)return;
   drag={x:event.clientX,y:event.clientY,b:[...el.bounds]};ctx.dragMoved=false;
   hit.setPointerCapture(event.pointerId);
  });
  hit.addEventListener('pointermove',event=>{
   if(!drag)return;const dx=(event.clientX-drag.x)/scale,dy=(event.clientY-drag.y)/scale;
   if(Math.abs(dx)+Math.abs(dy)<3)return;ctx.dragMoved=true;
   const x=Math.max(0,Math.min(page.width-drag.b[2],drag.b[0]+dx));const y=Math.max(0,Math.min(page.height-drag.b[3],drag.b[1]+dy));
   hit.style.left=x+'px';hit.style.top=y+'px';
   const display=stage.querySelector(`[data-render-id="${CSS.escape(hit.dataset.element)}"]`);if(display){display.style.left=x+'px';display.style.top=y+'px';}
  });
  hit.addEventListener('pointerup',async()=>{
   if(!drag)return;drag=null;
   if(ctx.dragMoved){try{const el=ctx.element();const b=[parseFloat(hit.style.left),parseFloat(hit.style.top),el.bounds[2],el.bounds[3]];await ctx.op({type:'move',element_id:el.id,bounds:b},'配置を保存しました');}catch(error){ctx.notify(error.message,true);renderPaper(ctx);}finally{setTimeout(()=>{ctx.dragMoved=false;},100);}}
  });
  hit.addEventListener('pointercancel',()=>{drag=null;ctx.dragMoved=false;renderPaper(ctx);});
 });
}

export function overflowCount(ctx){return [...document.querySelectorAll('#paper .element.text')].filter(e=>e.scrollHeight>e.clientHeight+2||e.scrollWidth>e.clientWidth+2).length;}

// Browser measurement for an explicitly chosen new text frame; never InDesign composition.
export function estimateSplit(text,bounds,fontSize){
 const probe=document.createElement('div');probe.style.cssText=`position:fixed;left:-10000px;top:0;width:${bounds[2]}px;font:${fontSize}px/1.18 "Yu Gothic",Meiryo,sans-serif;white-space:pre-wrap;overflow-wrap:anywhere;`;
 document.body.append(probe);let lo=0,hi=text.length;
 while(lo<hi){const mid=Math.ceil((lo+hi)/2);probe.textContent=text.slice(0,mid);if(probe.getBoundingClientRect().height<=bounds[3])lo=mid;else hi=mid-1;}
 probe.remove();
 if(lo>0&&lo<text.length){const ch=text.charCodeAt(lo-1);if(ch>=0xD800&&ch<=0xDBFF)lo--;}
 return lo;
}
