import {esc,btn,field,textarea,threadHTML} from './ui.js';

export const members=ctx=>ctx.currentPage().elements.filter(e=>(ctx.groupIds||[]).includes(e.id)&&!e.deleted);
function instructionPanel(ctx,group){
 const page=ctx.currentPage(),threads=ctx.state.threads.filter(t=>t.group_id===group.id);
 return `<hr><h3>① 制作会社へ移動を指示する</h3><p class="scope">対象：${esc(group.name)} ／ 元 p.${esc(page.printed_label||page.label||page.source_label)} ／ ${group.element_ids.length}要素</p><p class="muted">指示は紙面に印字しません。未登録のページ番号も指定できます。</p>${field('移動先（例：165ページ左下）','group-destination','')}${textarea('補足・移動後の空きや重なりの扱い','group-instruction','',3)}${btn('このブロックへの移動指示を保存','group-instruct','primary full')}<p class="muted">保存後は「制作への指示」にも表示されます。</p>${threads.map(t=>threadHTML(t,ctx)).join('')}<hr><h3>② 紙面上で配置を試す</h3><p class="muted">下の操作は紙面の配置を変更します。移動先の重なりを確認してください。</p>`;
}
export function groupInspector(ctx){
 const selected=members(ctx),group=(ctx.state.document.groups||[]).find(g=>g.id===ctx.groupId);
 return `<h2>${group?esc(group.name):'商品をまとめて選択'}</h2><p class="muted">ドラッグで完全に囲んだ要素を追加。クリックで追加・除外できます。離れた場所も選べます。</p><p style="margin:12px 0">${selected.length}個を選択 ${group?'／ 選択した要素をドラッグで一緒に移動':''}</p>${!group?field('商品ブロック名','group-name','商品ブロック'):''}<div class="button-row">${!group?btn('商品としてまとめる','group-save','primary',selected.length<2?'disabled':''):btn('選択内容を組み直す','group-edit','')}${btn('選択を終了','group-exit','ghost')}</div>${group?`${instructionPanel(ctx,group)}${field('横の移動量（mm）','group-dx',0,'number')}${field('縦の移動量（mm）','group-dy',0,'number')}<label>移動先ページ</label><select id="group-page">${ctx.state.document.pages.map(p=>`<option value="${p.id}" ${p.id===ctx.pageId?'selected':''}>p.${esc(p.printed_label||p.label||p.source_label)} · ${esc(p.title)}</option>`).join('')}</select>${btn('まとめて移動','group-move','primary full')}${btn('グループを解除','group-ungroup','full')}`:''}<hr><p class="muted">不要な要素は下の一覧からも外せます。図形や共有の説明を含めるか確認してください。</p><div style="max-height:360px;overflow:auto">${selected.map(e=>`<button class="full" data-act="group-remove" data-id="${esc(e.id)}">− ${esc((e.text||e.name||'図形・罫線').slice(0,70))}</button>`).join('')}</div>`;
}
export function groupToolbar(ctx){
 const groups=(ctx.state.document.groups||[]).filter(g=>g.element_ids.some(id=>ctx.currentPage().elements.some(e=>e.id===id&&!e.deleted)));
 return `<div class="row" style="padding:8px 14px;border-bottom:1px solid #dce4e5;background:white">${btn('まとめて選択','group-start',ctx.groupMode?'active':'')}<span class="muted">商品ブロック</span>${groups.map(g=>btn(esc(g.name),'group-open',ctx.groupId===g.id?'active':'',`data-id="${esc(g.id)}"`)).join('')}</div>`;
}
export async function groupAction(ctx,action,target){
 const repaint=()=>{ctx.render();};
  if(action==='group-instruct'){
  const g=ctx.state.document.groups.find(g=>g.id===ctx.groupId),page=ctx.currentPage();
  const destination=document.getElementById('group-destination').value.trim();
  if(!destination){ctx.notify('移動先を入力してください。',true);return;}
  const detail=document.getElementById('group-instruction').value;
  await ctx.op({type:'comment',group_id:g.id,destination:'production',text:`【ブロック移動指示】${g.name}\n元ページ：p.${page.printed_label||page.label||page.source_label}\n移動先：${destination}\n${detail}`},'移動指示を保存しました。紙面の文章・配置は変更していません。');return;
 }
 if(action==='group-start'){ctx.groupMode=true;ctx.groupId=null;ctx.groupIds=[];ctx.selection=null;ctx.mode='html';repaint();}
 if(action==='group-exit'){ctx.groupMode=false;ctx.groupId=null;ctx.groupIds=[];repaint();}
 if(action==='group-open'){const g=ctx.state.document.groups.find(g=>g.id===target.dataset.id);ctx.groupMode=true;ctx.groupId=g.id;ctx.groupIds=[...g.element_ids];ctx.selection=null;ctx.mode='html';repaint();}
 if(action==='group-remove'){if(ctx.groupId){ctx.notify('「選択内容を組み直す」を押してから外してください。');return;}ctx.groupIds=ctx.groupIds.filter(id=>id!==target.dataset.id);repaint();}
 if(action==='group-save'){const st=await ctx.op({type:'create_group',name:document.getElementById('group-name').value,element_ids:ctx.groupIds},'商品ブロックを保存しました。');ctx.groupId=st.document.groups.at(-1).id;repaint();}
 if(action==='group-edit'||action==='group-ungroup'){await ctx.op({type:'ungroup',group_id:ctx.groupId},'まとまりを解除しました。紙面は変わりません。');ctx.groupId=null;if(action==='group-ungroup'){ctx.groupMode=false;ctx.groupIds=[];}repaint();}
 if(action==='group-move'){const targetPage=document.getElementById('group-page').value;await ctx.op({type:'move_group',group_id:ctx.groupId,page_id:targetPage,delta:['group-dx','group-dy'].map(id=>Number(document.getElementById(id).value)*72/25.4)},'商品ブロックを移動しました。');ctx.pageId=targetPage;repaint();}
}
export function attachGroupSelection(ctx,renderPaper){
 if(!ctx.groupMode||ctx.actor.role!=='editor'||ctx.mode!=='html')return;
 const paper=document.getElementById('paper'),page=ctx.currentPage();
 const eligible=page.elements.filter(e=>!e.deleted&&['text','image','shape'].includes(e.kind));
 for(const e of members(ctx)){const ring=document.createElement('div');ring.className='group-selection-ring';const [x,y,w,h]=e.bounds;ring.style.cssText=`position:absolute;left:${x}px;top:${y}px;width:${Math.max(w,2)}px;height:${Math.max(h,2)}px;border:2px solid #077cbb;background:#148bc21a;pointer-events:none;z-index:5000;`;paper.append(ring);}
 paper.style.touchAction='none';let gesture;
 const point=ev=>{const r=paper.getBoundingClientRect();return [(ev.clientX-r.left)/ctx.scale,(ev.clientY-r.top)/ctx.scale];};
 const at=([x,y])=>[...eligible].reverse().find(e=>{const [a,b,w,h]=e.bounds;return x>=a&&x<=a+Math.max(w,3)&&y>=b&&y<=b+Math.max(h,3);});
 paper.addEventListener('click',ev=>{ev.stopImmediatePropagation();ev.preventDefault();},true);
 paper.addEventListener('pointerdown',ev=>{if(ev.button!==0)return;ev.stopImmediatePropagation();ev.preventDefault();const start=point(ev),hit=at(start);const moving=ctx.groupId&&hit&&ctx.groupIds.includes(hit.id);if(ctx.groupId&&!moving)return;gesture={start,hit,moving};paper.setPointerCapture(ev.pointerId);const box=document.createElement('div');box.id='group-marquee';box.style.cssText='position:absolute;border:1px dashed #077cbb;background:#148bc21a;pointer-events:none;z-index:6000';paper.append(box);},true);
 paper.addEventListener('pointermove',ev=>{if(!gesture)return;ev.stopImmediatePropagation();const end=point(ev),dx=end[0]-gesture.start[0],dy=end[1]-gesture.start[1];const box=document.getElementById('group-marquee');if(gesture.moving){for(const e of members(ctx)){const node=paper.querySelector(`[data-render-id="${CSS.escape(e.id)}"]`);if(node)node.style.transform=`translate(${dx}px,${dy}px)`;}for(const ring of paper.querySelectorAll('.group-selection-ring'))ring.style.transform=`translate(${dx}px,${dy}px)`;}else box.style.cssText+=`;left:${Math.min(end[0],gesture.start[0])}px;top:${Math.min(end[1],gesture.start[1])}px;width:${Math.abs(dx)}px;height:${Math.abs(dy)}px;`;},true);
 paper.addEventListener('pointerup',async ev=>{if(!gesture)return;ev.stopImmediatePropagation();const g=gesture;gesture=null;const end=point(ev),dx=end[0]-g.start[0],dy=end[1]-g.start[1];try{if(g.moving){if(Math.abs(dx)+Math.abs(dy)>3)await ctx.op({type:'move_group',group_id:ctx.groupId,delta:[dx,dy]},'商品ブロックを移動しました。');}else{const ids=new Set(ctx.groupIds||[]);if(Math.abs(dx)+Math.abs(dy)<3){if(g.hit){if(ids.has(g.hit.id))ids.delete(g.hit.id);else ids.add(g.hit.id);}}else{const l=Math.min(g.start[0],end[0]),t=Math.min(g.start[1],end[1]),r=Math.max(g.start[0],end[0]),b=Math.max(g.start[1],end[1]);for(const e of eligible){const [x,y,w,h]=e.bounds;if(x>=l&&y>=t&&x+w<=r&&y+h<=b)ids.add(e.id);}}ctx.groupIds=[...ids];}}catch(error){ctx.notify(error.message,true);}finally{renderPaper(ctx);ctx.renderInspector();}},true);
 paper.addEventListener('pointercancel',()=>{gesture=null;renderPaper(ctx);});
}
