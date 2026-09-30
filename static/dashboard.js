import {esc,btn,badge,field} from './ui.js';
export const today=()=>new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Tokyo'});
export function submissionFlags(s,threads,day=today()){
 const open=threads.filter(t=>t.submission_id===s.id&&t.status==='open');
 const unanswered=open.filter(t=>t.messages?.at(-1)?.role!==t.destination).length;
 const waiting=s.agreement!=='agreed'||open.length>0;
 const dueLate=!!s.due_date&&s.due_date<day&&waiting;
 const readyLate=!!s.ready_date&&s.ready_date<day&&s.agreement!=='agreed';
 return {open:open.length,unanswered,dueLate,readyLate,overdue:dueLate||readyLate,complete:s.agreement==='agreed'&&s.paper_checked&&s.status==='applied'&&!open.length};
}
export function filteredSubmissions(ctx){
 const f=ctx.intakeFilter||{},needle=(f.query||'').trim().toLocaleLowerCase(),owner=(f.owner||'').trim().toLocaleLowerCase();
 return ctx.state.submissions.filter(s=>{
  if(needle&&!`${s.title} ${s.target||''} ${s.text||''}`.toLocaleLowerCase().includes(needle))return false;
  if(owner&&!(s.assignee||'').toLocaleLowerCase().includes(owner))return false;
  const v=submissionFlags(s,ctx.state.threads);
  return !f.status||f.status==='all'||({overdue:v.overdue,unanswered:v.unanswered>0,questions:v.open>0,agreement:s.agreement!=='agreed',paper:!s.paper_checked,unassigned:!s.assignee,complete:v.complete}[f.status]??false);
 });
}
export const agreementLabel=s=>({agreed:'合意済み',recheck:'再合意が必要',pending:'未合意'}[s.agreement]||'未合意');
export function dashboardHTML(ctx){
 const st=ctx.state,editor=ctx.actor.role==='editor',items=st.submissions,shown=filteredSubmissions(ctx),filter=ctx.intakeFilter||{};
 const options={all:'すべて',overdue:'期限超過',unanswered:'回答待ち',questions:'未解決の質問あり',agreement:'未合意・再合意',paper:'紙面未確認',unassigned:'担当未設定',complete:'対応完了'};
 return `<section class="panel intake-dashboard"><div class="row"><h2>原稿・指示の管理表</h2><span class="push muted">${shown.length} / ${items.length}件</span></div><p class="muted">合意・回答・紙面確認は別々に管理します。原稿・資料・質疑が変わったら再確認になります。</p><div class="intake-stats">${[['all','原稿',items.length],['overdue','期限超過',items.filter(s=>submissionFlags(s,st.threads).overdue).length],['unanswered','回答待ち',items.filter(s=>submissionFlags(s,st.threads).unanswered).length],['agreement','未合意・再合意',items.filter(s=>s.agreement!=='agreed').length],['paper','紙面未確認',items.filter(s=>!s.paper_checked).length]].map(([value,label,count])=>btn(`${label} <strong>${count}</strong>`,'workflow-quick-filter',filter.status===value?'active':'',`data-filter="${value}"`)).join('')}</div>
 <form id="workflow-filters" class="intake-filters"><div>${field('件名・型番・本文','intake-query',filter.query||'')}</div><div>${field('担当者','intake-owner',filter.owner||'','text','placeholder="担当者名で絞り込み"')}</div><div><label for="intake-status">対応状況</label><select id="intake-status">${Object.entries(options).map(([v,l])=>`<option value="${v}" ${v===(filter.status||'all')?'selected':''}>${l}</option>`).join('')}</select></div><button type="submit" class="primary">絞り込む</button>${btn('解除','workflow-clear-filter','ghost')}</form>
 <div class="table-wrap"><table class="intake-table"><thead><tr><th>原稿・担当</th><th>期限</th><th>合意・反映</th><th>質問</th><th>確認する紙面</th><th>資料</th><th>操作</th></tr></thead><tbody>${shown.map(s=>{
 const flags=submissionFlags(s,st.threads),editable=editor||s.author_id===ctx.actor.id||(!s.author_id&&s.author===ctx.actor.name);
 return `<tr><td><strong>${esc(s.title)}</strong><small>${esc(s.target||'対象未指定')} ／ 原稿改訂 ${s.content_revision||1}</small><small>担当：${esc(s.assignee||'未設定')}</small></td><td><small>回答・確認：${esc(s.due_date||'未設定')} ${flags.dueLate?badge('超過','amber'):''}</small><small>原稿確定：${esc(s.ready_date||'未設定')} ${flags.readyLate?badge('超過','amber'):''}</small></td><td>${editor?`<select aria-label="${esc(s.title)}の合意" data-review="agreement" data-submission="${s.id}">${['pending','agreed','recheck'].map(v=>`<option value="${v}" ${(s.agreement||'pending')===v?'selected':''}>${agreementLabel({agreement:v})}</option>`).join('')}</select>`:badge(agreementLabel(s),s.agreement==='recheck'?'amber':'')}
 <small>${badge({received:'受け取り',checking:'確認中',applied:'反映済み'}[s.status]||s.status)}</small>${s.agreed_content_revision?`<small>合意記録：原稿改訂 ${s.agreed_content_revision}</small>`:''}</td><td>${badge(flags.open?`未解決 ${flags.open}件`:'未解決なし',flags.open?'amber':'neutral')}${flags.unanswered?`<small>回答待ち ${flags.unanswered}件</small>`:''}</td><td>${editor?`<select aria-label="${esc(s.title)}の確認ページ" data-review="page_id" data-submission="${s.id}"><option value="">未指定</option>${st.document.pages.map(p=>`<option value="${p.id}" ${s.review_page_id===p.id?'selected':''}>p.${esc(p.label)} ${esc(p.title.slice(0,16))}</option>`).join('')}</select><select aria-label="${esc(s.title)}の紙面確認" data-review="paper_checked" data-submission="${s.id}"><option value="false" ${!s.paper_checked?'selected':''}>未確認</option><option value="true" ${s.paper_checked?'selected':''}>確認済み</option></select>`:badge(s.paper_checked?'確認済み':'未確認')}${s.review_page_id?btn('紙面を開く','open-page','',`data-page="${s.review_page_id}"`):''}${s.paper_recheck_reason&&!s.paper_checked?`<small class="recheck-reason">${esc(s.paper_recheck_reason)}</small>`:''}</td><td>${(s.asset_ids||[]).map(id=>{const a=st.attachments.find(a=>a.id===id);return a?btn(esc(a.name),'preview-asset','',`data-asset="${a.id}"`):''}).join('')||'<small>関連資料なし</small>'}${editable?btn('資料を関連付け','submission-assets','',`data-submission="${s.id}"`):''}</td><td>${btn(editor?'内容・担当・期限':editable?'内容を更新':'詳細・履歴','workflow-edit','',`data-submission="${s.id}"`)}${btn('原稿・質疑を見る','source-detail','',`data-submission="${s.id}"`)}</td></tr>`;
 }).join('')||'<tr><td colspan="7">条件に合う原稿がありません。条件を解除するか、原稿を登録してください。</td></tr>'}</tbody></table></div><small>期限は日本時間の日付で判定。当日は超過に含めません。担当者名は管理用の記録で、アクセス権限ではありません。</small></section>`;
}
