import {esc,btn,field,textarea,dateLabel,badge} from './ui.js';
import {agreementLabel} from './dashboard.js';
const $=id=>document.getElementById(id);
const kindLabel={new:'新規',update:'変更あり',unchanged:'変更なし',local_only:'画面の変更を保持',conflict:'競合：選択が必要'};

function editDialog(ctx,id){
 const s=ctx.state.submissions.find(s=>s.id===id),editor=ctx.actor.role==='editor',editable=editor||s.author_id===ctx.actor.id||(!s.author_id&&s.author===ctx.actor.name);
 ctx.editSubmission={id,version:ctx.state.version};
 const names={title:'件名',target:'対象',text:'本文',asset_ids:'資料ID',assignee:'担当',due_date:'回答・確認期限',ready_date:'原稿確定予定日'};
 ctx.showModal(`<h2>原稿の内容・担当・期限</h2><p>原稿改訂 ${s.content_revision||1} ／ ${agreementLabel(s)}</p><div class="workflow-dialog">${s.import_ref?`<p class="scope">取り込み元：${esc(s.import_ref.namespace)} ／ 原稿ID：${esc(s.import_ref.key)}</p>`:''}${editable?`${field('件名','workflow-title',s.title)}${field('対象の商品・型番','workflow-target',s.target||'')}${textarea('原稿の内容','workflow-text',s.text,6)}${textarea('更新理由・補足','workflow-reason','',2)}`:`<h3>${esc(s.title)}</h3><pre>${esc(s.text)}</pre>`}${editor?`<div class="workflow-date-grid"><div>${field('担当者名','workflow-assignee',s.assignee||'')}</div><div>${field('回答・確認期限','workflow-due',s.due_date||'','date')}</div><div>${field('原稿確定予定日','workflow-ready',s.ready_date||'','date')}</div></div>`:''}${editable?`<p class="notice">原稿の内容を変えると、合意・紙面確認は再確認になります。担当・期限のみの変更では合意を維持します。</p>${btn('原稿を更新','workflow-save','primary full')}`:''}<hr><h3>確認した改訂</h3><p>合意：${s.agreed_content_revision?'原稿改訂 '+s.agreed_content_revision+' ／ '+esc(s.agreed_by||'')+' ／ '+dateLabel(s.agreed_at):'記録なし'}<br>紙面確認：${s.checked_content_revision?'原稿改訂 '+s.checked_content_revision+' ／ '+esc(s.checked_by||'')+' ／ '+dateLabel(s.checked_at):'記録なし'}</p><h3>更新履歴</h3>${[...(s.history||[])].reverse().map(h=>`<article class="thread"><strong>${esc(h.author)} · ${dateLabel(h.created)}</strong><p>${esc(h.reason)} ／ 改訂 ${h.revision_before} → ${h.revision_after}</p>${Object.keys(h.after).map(k=>`<div><small>${names[k]||esc(k)}</small><div class="diff-grid"><pre>${esc(Array.isArray(h.before[k])?h.before[k].join('\n'):h.before[k]??'未設定')}</pre><pre>${esc(Array.isArray(h.after[k])?h.after[k].join('\n'):h.after[k]??'未設定')}</pre></div></div>`).join('')}</article>`).join('')||'<p class="muted">まだ更新履歴はありません。</p>'}</div>`);
}

function importDialog(ctx,settings={}){
 const assets=ctx.state.attachments.filter(a=>a.kind==='spreadsheet');
 if(!assets.length){ctx.showModal('<h2>Excel・CSVから原稿を取り込む</h2><p>まず「原稿・素材をアップロード」からExcelまたはCSVを追加してください。</p>');return;}
 const saved=ctx.state.submission_imports?.at(-1),asset=assets.find(a=>a.id===settings.asset_id)||assets.at(-1),sheet=Number(settings.sheet)||0,header=Number(settings.header_row)||0;
 const rows=asset.preview.sheets[sheet]?.rows||[],head=rows[header]||[];
 const cols=settings.columns||saved?.columns||{key:0,title:1,text:2,target:head.length>3?3:null};
 ctx.importSpec={asset_id:asset.id,sheet,header_row:header,namespace:settings.namespace??saved?.namespace??'開発原稿',columns:cols};
 const select=(key,label)=>`<label for="import-col-${key}">${label}</label><select id="import-col-${key}">${key==='target'?'<option value="">指定しない</option>':''}${head.map((v,i)=>`<option value="${i}" ${cols[key]===i?'selected':''}>${i+1}列目：${esc(v||'見出しなし')}</option>`).join('')}</select>`;
 ctx.showModal(`<h2>Excel・CSVから原稿を取り込む</h2><div class="workflow-dialog"><p>更新しても変わらない「原稿ID」で同じ原稿を見つけます。次回も同じ取り込み元名を使ってください。</p>${field('取り込み元名','import-namespace',ctx.importSpec.namespace)}<label for="import-asset">取り込むファイル</label><select id="import-asset">${assets.map(a=>`<option value="${a.id}" ${a.id===asset.id?'selected':''}>${esc(a.name)}</option>`).join('')}</select><div class="workflow-date-grid"><div><label for="import-sheet">シート</label><select id="import-sheet">${asset.preview.sheets.map((s,i)=>`<option value="${i}" ${i===sheet?'selected':''}>${esc(s.name)}</option>`).join('')}</select></div><div>${field('見出し行（1から）','import-header',header+1,'number',`min="1" max="${rows.length}"`)}</div></div><div class="workflow-date-grid"><div>${select('key','原稿IDの列（重複しない固定ID）')}</div><div>${select('title','件名の列')}</div><div>${select('text','本文の列')}</div><div>${select('target','型番・対象の列')}</div></div><p class="notice">1シート200行（見出し含む）・40列・1セル2000文字まで。数式は計算しません。原稿IDは数式ではなく固定値を使います。原稿IDがない資料は1件ずつ登録してください。</p>${btn('取り込み前に差分を確認','workflow-import-preview','primary full')}</div>`);
}
function readSpec(ctx){return {...ctx.importSpec,namespace:$('import-namespace').value,sheet:Number($('import-sheet').value),header_row:Number($('import-header').value)-1,asset_id:$('import-asset').value,columns:Object.fromEntries(['key','title','text','target'].map(k=>[k,$('import-col-'+k).value===''?null:Number($('import-col-'+k).value)]))};}
function previewDialog(ctx,p){
 ctx.importPreview=p;
 ctx.showModal(`<h2>取り込み前の差分確認</h2><div class="workflow-dialog"><p>${esc(p.namespace)} ／ ${esc(p.sheet_name)}</p><div class="intake-stats">${Object.entries(p.counts).map(([k,v])=>badge(kindLabel[k]+' '+v,k==='conflict'&&v?'amber':'neutral')).join('')}</div><p>${esc(p.note)}</p>${p.missing_keys.length?`<p class="notice">今回の表にないID（保存済み原稿は保持）：${esc(p.missing_keys.join(', '))}</p>`:''}${p.errors.map(e=>`<p class="notice">${e.row||'—'}行目・ID ${esc(e.key)}：${esc(e.message)}</p>`).join('')}<div class="table-wrap"><table class="import-diff"><thead><tr><th>ID・行</th><th>状態</th><th>システムの内容</th><th>Excelの内容</th><th>競合時の扱い</th></tr></thead><tbody>${p.rows.map(r=>`<tr><td>${esc(r.key)}<small>${r.row}行目</small></td><td>${badge(kindLabel[r.kind],r.kind==='conflict'?'amber':'neutral')}</td><td><strong>${esc(r.before?.title||'—')}</strong><small>${esc(r.before?.target||'')}</small><pre>${esc(r.before?.text||'')}</pre></td><td><strong>${esc(r.after.title)}</strong><small>${esc(r.after.target)}</small><pre>${esc(r.after.text)}</pre></td><td>${r.kind==='conflict'?`<select data-import-resolution="${esc(r.key)}" aria-label="${esc(r.key)}の競合解決"><option value="">選んでください</option><option value="keep">システムの内容を保持</option><option value="incoming">Excelの内容を採用</option></select>`:'—'}</td></tr>`).join('')}</tbody></table></div><p>変更がある原稿は合意・紙面確認を再確認に戻します。取り込みは全行まとめて保存します。</p><div class="button-row">${btn('列の指定に戻る','workflow-import-back')}${btn('この内容で取り込む','workflow-import-apply','primary',p.errors.length?'disabled':'')}</div></div>`);
}
export function workflowFilter(ctx){ctx.intakeFilter={query:$('intake-query').value,owner:$('intake-owner').value,status:$('intake-status').value};ctx.render();}
export function workflowChange(ctx,target){
 if(ctx.workflowPending)return false;
 if(!['import-asset','import-sheet','import-header'].includes(target.id))return false;
 const spec=readSpec(ctx);
 if(target.id==='import-asset'){spec.sheet=0;spec.header_row=0;delete spec.columns;}
 if(target.id==='import-sheet'){spec.header_row=0;delete spec.columns;}
 importDialog(ctx,spec);return true;
}
export async function workflowAction(ctx,action,target){
 if(ctx.workflowPending)return;
 if(action==='workflow-edit')return editDialog(ctx,target.dataset.submission);
 if(action==='workflow-quick-filter'){ctx.intakeFilter={...ctx.intakeFilter,status:target.dataset.filter};ctx.render();return;}
 if(action==='workflow-clear-filter'){ctx.intakeFilter={};ctx.render();return;}
 if(action==='workflow-import')return importDialog(ctx);
 if(action==='workflow-import-back')return importDialog(ctx,ctx.importSpec);
 if(action==='workflow-save'){
  const operation={type:'submission_update',submission_id:ctx.editSubmission.id,title:$('workflow-title').value,target:$('workflow-target').value,text:$('workflow-text').value,reason:$('workflow-reason').value};
  if(ctx.actor.role==='editor')Object.assign(operation,{assignee:$('workflow-assignee').value,due_date:$('workflow-due').value,ready_date:$('workflow-ready').value});
  ctx.busy('原稿を保存しています…');
  try{ctx.state=await ctx.api(`/api/catalogs/${ctx.state.id}/operations`,'POST',{version:ctx.editSubmission.version,operation});ctx.closeModal();ctx.render();ctx.notify('原稿を保存しました。');}finally{ctx.busy(false);}return;
 }
 if(action==='workflow-import-preview'){
  const spec=structuredClone(readSpec(ctx)),catalogId=ctx.state.id,actorId=ctx.actor.id;
  ctx.importSpec=spec;ctx.workflowPending=true;ctx.busy('差分を確認しています…');
  try{const p=await ctx.api(`/api/catalogs/${catalogId}/submission-import-preview`,'POST',spec);if(ctx.state.id===catalogId&&ctx.actor.id===actorId)previewDialog(ctx,{...p,spec,catalogId,actorId});}finally{ctx.workflowPending=false;ctx.busy(false);}return;
 }
 if(action==='workflow-import-apply'){
  const preview=ctx.importPreview;
  if(!preview||preview.catalogId!==ctx.state.id||preview.actorId!==ctx.actor.id)throw new Error('取り込み前の差分をもう一度確認してください。');
  const resolutions=Object.fromEntries([...document.querySelectorAll('[data-import-resolution]')].map(e=>[e.dataset.importResolution,e.value]));
  if(ctx.importPreview.rows.some(r=>r.kind==='conflict'&&!resolutions[r.key])){ctx.notify('競合した原稿の扱いをすべて選んでください。',true);return;}
  ctx.workflowPending=true;ctx.busy('原稿を取り込んでいます…');
  try{ctx.state=await ctx.api(`/api/catalogs/${preview.catalogId}/operations`,'POST',{version:preview.version,operation:{type:'import_submissions',...preview.spec,resolutions,reason:'Excel・CSVから原稿を更新'}});ctx.closeModal();ctx.render();ctx.notify('原稿を取り込みました。既存の原稿IDとの対応を保持しています。');}finally{ctx.workflowPending=false;ctx.busy(false);}
 }
}
