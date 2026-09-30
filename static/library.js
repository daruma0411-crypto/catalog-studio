import {esc,btn,empty} from './ui.js';
import {hasSubmissionDraft} from './intake_pages.js';

export function libraryHTML(ctx){
 const books=ctx.libraryBooks||[];
 return `<div class="content-view"><div class="content-head"><div><h1>本棚</h1><p>カタログを保管し、作業する一冊を開きます。</p></div>${ctx.actor.role==='editor'?btn('＋ カタログを追加','import','primary'):''}${btn('一覧を更新','library-open')}</div><div class="board">${books.map(b=>`<article class="panel"><h2>${esc(b.title)}</h2><p>${b.page_count}ページ</p>${btn('この冊子を開く','library-paper','full',`data-catalog="${esc(b.id)}"`)}</article>`).join('')||empty('カタログはまだありません。')}</div></div>`;
}

export async function libraryAction(ctx,action,target){
 if(ctx.actor.role==='reader')throw new Error('本棚は販促・開発部門で確認してください。');
 if(!['library-open','library-paper'].includes(action))throw new Error('冊子間の連携機能は提供していません。画面を再読み込みしてください。');
 if(action==='library-paper'&&(hasSubmissionDraft(ctx)||Object.keys(ctx.drafts||{}).length)&&!confirm('入力中の原稿・文章を破棄して、対象の冊子を開きますか？'))return;
 ctx.busy('カタログを読み込んでいます…');
 try{
  if(action==='library-open'){ctx.libraryBooks=await ctx.api('/api/library');ctx.view='library';}
  else{
   const state=await ctx.api('/api/catalogs/'+target.dataset.catalog),page=state.document.pages[0];
   if(!page)throw new Error('この冊子にはページがありません。');
   ctx.state=state;ctx.pageId=page.id;ctx.selection=null;ctx.groupMode=false;ctx.groupId=null;ctx.groupIds=[];ctx.drafts={};ctx.submissionDraft={};ctx.searchResult=null;ctx.inquiryResult=null;ctx.view='edit';ctx.mode='reference';
  }
  ctx.render();
 }finally{ctx.busy(false);}
}
