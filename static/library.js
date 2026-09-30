export async function refreshCampaigns(ctx){
 ctx.campaignList=[];ctx.campaignMessage='進捗を取得しています…';ctx.render();
 try{ctx.campaignList=await ctx.api('/api/campaigns');ctx.campaignMessage='';}
 catch(error){ctx.campaignMessage='進捗を取得できませんでした。「進捗を更新」で再読み込みしてください。';throw error;}
 finally{ctx.render();}
}
import {esc,btn,badge,empty,field,textarea} from './ui.js';
import {hasSubmissionDraft} from './intake_pages.js';
export function captureLibraryDraft(ctx){
 const title=document.getElementById('campaign-title'),instruction=document.getElementById('campaign-instruction');
 if(title&&instruction)ctx.libraryDraft={title:title.value,instruction:instruction.value,indices:[...document.querySelectorAll('[data-library-target]:checked')].map(e=>Number(e.dataset.libraryTarget))};
}
const labels={open:'未対応',fixed:'反映済み',verified:'確認済み',recheck:'再確認',missing:'対象・指示なし'};

export function libraryHTML(ctx){
 const books=ctx.libraryBooks||[],result=ctx.libraryResult;
 return `<div class="content-view"><div class="content-head"><div><h1>本棚・横断検索</h1><p>調べる冊子を選び、同じ型番の掲載場所をまとめて確認します。</p></div>${btn('本棚を更新','library-open')}${btn('変更案件の進捗','library-campaigns','primary')}</div><div class="board">${books.map(b=>`<article class="panel"><label><input type="checkbox" data-library-book="${esc(b.id)}" ${!ctx.librarySelection||ctx.librarySelection.includes(b.id)?'checked':''} style="width:auto"> <strong>${esc(b.title)}</strong></label><p>${b.page_count}ページ ／ 作業版 ${b.version}</p><small>${b.published_version?'社内共有版 '+b.published_version:'まだ社内共有していません'}</small>${btn('この冊子を開く','library-paper','full',`data-catalog="${esc(b.id)}"`)}</article>`).join('')||empty('カタログを追加してください。')}</div><div class="search-bar"><input id="library-query" aria-label="横断検索の型番・キーワード" placeholder="例：ERD9717WA" value="${esc(ctx.libraryQuery||'')}">${btn('選んだ冊子を検索','library-search','primary')}</div>${result?`<section class="panel"><h2>${esc(result.query)}：${result.occurrence_count}出現 ／ ${result.target_count}文字枠</h2><p class="scope">${esc(result.scope)}${result.truncated?'<br>表示上限に達しています。表示されていない出現もあるため、表示分だけの完了を全掲載完了とは扱いません。':''}</p>${result.catalogs.map(c=>badge(c.title+'：'+c.count+'出現','neutral')).join(' ')}<div class="product-table-wrap"><table class="product-table"><thead><tr><th>対象</th><th>冊子・ページ</th><th>読取原文</th><th>紙面</th></tr></thead><tbody>${result.results.map((r,i)=>`<tr><td>${ctx.actor.role==='editor'?`<input type="checkbox" data-library-target="${i}" ${ctx.libraryDraft?.indices.includes(i)?'checked':''} aria-label="変更対象 ${i+1}" style="width:auto">`:'閲覧'}</td><td><strong>${esc(r.title)}</strong><small>p.${esc(r.page_label)} ／ 掲載順 ${r.order} ／ 版 ${r.revision}</small></td><td><pre style="white-space:pre-wrap">${esc(r.context)}</pre><small>${esc(r.placement_status)}</small></td><td>${btn('掲載箇所を見る','library-paper','',`data-catalog="${esc(r.catalog_id)}" data-page="${esc(r.page_id)}" data-element="${esc(r.element_id)}"`)}</td></tr>`).join('')||'<tr><td colspan="4">選択した冊子に一致する文章はありません。</td></tr>'}</tbody></table></div>${ctx.actor.role==='editor'&&result.results.length?`<hr class="divider"><h2>選んだ箇所へ共通の変更指示</h2><p>文章を自動で書き換えず、各冊子の「制作への指示」に登録します。</p>${field('変更案件の件名','campaign-title',ctx.libraryDraft?.title||'', 'text','maxlength="200"')}${textarea('変更内容・条件・注意点','campaign-instruction',ctx.libraryDraft?.instruction||'',3)}${btn('選択対象と指示を確認','library-preview','primary full')}`:''}</section>`:''}</div>`;
}

export function campaignsHTML(ctx){return `<div class="content-view"><div class="content-head"><div><h1>商品変更の反映管理</h1><p>選択した掲載箇所を、各冊子の制作指示と同じ状態で追跡します。</p></div>${btn('進捗を更新','library-campaigns')}${btn('本棚・横断検索へ','library-open')}</div><p class="scope">完了は、この案件で選んだ対象が全て確認済みになった状態です。未選択の掲載や検索対象外の画像内文字までの完了を保証しません。確認後に対象ページが変わると、再確認になります。反映済み・確認済みは人が紙面を見て判断する状態で、自動照合ではありません。</p>${(ctx.campaignList||[]).map(c=>`<section class="panel" style="margin-bottom:22px"><div class="row"><h2>${esc(c.title)}</h2>${badge(c.complete?'選択対象は全て確認済み':'対応中',c.complete?'':'neutral')}</div><p>検索語：${esc(c.query)} ／ 登録：${esc(c.author)}</p><pre class="scope" style="white-space:pre-wrap">${esc(c.instruction)}</pre><div class="stat-strip">${Object.entries(labels).map(([key,label])=>`<span><strong>${c.counts[key]}</strong>${label}</span>`).join('')}</div><div class="product-table-wrap"><table class="product-table"><thead><tr><th>冊子・対象</th><th>状態</th><th>操作</th></tr></thead><tbody>${c.targets.map((t,i)=>`<tr><td><strong>${esc(t.catalog_title)}</strong><small>${t.page_id?'p.'+esc(t.page_label):'元の対象がありません'} ／ 版 ${t.catalog_version??'—'}</small><pre style="white-space:pre-wrap">${esc(t.current_text||t.original_text)}</pre></td><td>${badge(labels[t.status],t.status==='recheck'?'amber':'neutral')}<small>${esc(t.reason)}</small></td><td>${t.page_id?btn('紙面を見る','library-paper','',`data-catalog="${esc(t.catalog_id)}" data-page="${esc(t.page_id)}" data-element="${esc(t.element_id)}"`):''}${ctx.actor.role==='editor'&&t.status!=='missing'?`<div class="button-row">${['open','fixed','verified'].map(status=>btn(labels[status]+'にする','library-status','',`data-campaign="${esc(c.id)}" data-index="${i}" data-status="${status}" ${t.status===status?'disabled':''}`)).join('')}</div>`:''}</td></tr>`).join('')}</tbody></table></div></section>`).join('')||empty(ctx.campaignMessage||'変更案件はまだありません。本棚で対象を検索し、共通の指示を登録してください。')}</div>`;}

export async function libraryAction(ctx,action,target){
 if(ctx.actor.role==='reader')throw new Error('本棚・変更案件は販促・開発部門で確認してください。');
 if(action==='library-preview'){
  const result=ctx.libraryResult,indices=[...document.querySelectorAll('[data-library-target]:checked')].map(e=>Number(e.dataset.libraryTarget));
  if(!indices.length)throw new Error('変更対象の文字枠を選んでください。');
  const title=document.getElementById('campaign-title').value.trim(),instruction=document.getElementById('campaign-instruction').value.trim();
  if(!title||!instruction)throw new Error('件名と変更内容を入力してください。');
  const selected=indices.map(i=>result.results[i]);
  ctx.campaignDraft={title,instruction,query:result.query,targets:selected.map(r=>({catalog_id:r.catalog_id,element_id:r.element_id,version:r.revision}))};
  ctx.showModal(`<h2>共通の変更指示を登録</h2><p>${selected.length}文字枠 ／ ${new Set(selected.map(r=>r.catalog_id)).size}冊</p><h3>${esc(title)}</h3><pre style="white-space:pre-wrap">${esc(instruction)}</pre><ul>${selected.map(r=>`<li>${esc(r.title)} p.${esc(r.page_label)}：${esc(r.context)}</li>`).join('')}</ul><p class="notice">各冊子の制作指示に追加します。紙面の文章は変更しません。この横断登録は冊子単位の「元に戻す」では取り消せません。登録前に対象を確認してください。</p>${btn('この対象へ指示を登録','library-create','primary full')}`);return;
 }
 if(action==='library-paper'){
  if((hasSubmissionDraft(ctx)||Object.keys(ctx.drafts||{}).length)&&!confirm('入力中の原稿・文章を破棄して、対象の冊子を開きますか？'))return;
 }
 ctx.busy('カタログと変更状況を確認しています…');
 try{
  if(action==='library-open'){ctx.libraryBooks=await ctx.api('/api/library');ctx.view='library';}
  if(action==='library-search'){
   const ids=[...document.querySelectorAll('[data-library-book]:checked')].map(e=>e.dataset.libraryBook),query=document.getElementById('library-query').value.trim();
   if(!ids.length||!query)throw new Error('対象の冊子と型番・キーワードを指定してください。');
   const params=new URLSearchParams({q:query});ids.forEach(id=>params.append('catalog',id));ctx.libraryResult=await ctx.api('/api/library-search?'+params);ctx.librarySelection=ids;ctx.libraryQuery=query;ctx.libraryDraft=null;
  }
  if(action==='library-create'){
   if(!ctx.campaignDraft||ctx.actor.role!=='editor')throw new Error('登録内容を確認してください。');
   await ctx.api('/api/campaigns','POST',ctx.campaignDraft);ctx.campaignDraft=null;ctx.libraryDraft=null;ctx.closeModal();ctx.libraryResult=null;
   await refreshCampaigns(ctx);ctx.state=await ctx.api('/api/catalogs/'+ctx.state.id);ctx.view='campaigns';ctx.notify('選択した冊子の制作指示へ登録しました。');
  }
  if(action==='library-campaigns'){ctx.view='campaigns';await refreshCampaigns(ctx);}
  if(action==='library-paper'){
   const state=await ctx.api('/api/catalogs/'+target.dataset.catalog);
   const page=target.dataset.page?state.document.pages.find(p=>p.id===target.dataset.page):state.document.pages[0];
   if(!page)throw new Error('対象ページが変更されています。本棚・進捗を更新してください。');
   ctx.state=state;ctx.pageId=page.id;ctx.selection=target.dataset.element||null;ctx.groupMode=false;ctx.groupId=null;ctx.drafts={};ctx.submissionDraft={};ctx.searchResult=null;ctx.inquiryResult=null;ctx.view='edit';ctx.mode='reference';
  }
  if(action==='library-status'){
   const campaign=ctx.campaignList.find(c=>c.id===target.dataset.campaign),t=campaign?.targets[Number(target.dataset.index)];
   if(!t||ctx.actor.role!=='editor')throw new Error('進捗を読み込み直してください。');
   const state=await ctx.api('/api/catalogs/'+t.catalog_id+'/operations','POST',{version:t.catalog_version,operation:{type:'change_status',change_id:t.change_id,status:target.dataset.status}});
   if(ctx.state.id===state.id)ctx.state=state;
   await refreshCampaigns(ctx);
  }
  ctx.render();
 }finally{ctx.busy(false);}
}
