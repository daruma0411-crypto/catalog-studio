import {esc,btn,badge,empty} from './ui.js';
const kinds={body:'本体',set:'セット',list:'定価',unspecified:'区分未確認'};
const evidence={same_frame:'同じ文字枠から読取',manual_group:'同じ商品ブロック',nearby:'位置からの候補'};
function priceHTML(p,confirmed,page){return `<div style="margin:8px 0"><strong>¥${esc(Number(p.amount).toLocaleString('ja-JP'))}</strong> ${esc(kinds[p.kind]||'区分未確認')}<small>${confirmed?'対応を確認済み':esc(evidence[p.relation]||'未確認')+'・対応未確認'}</small>${btn('価格の出典','locate','ghost',`data-page="${esc(page)}" data-element="${esc(p.element_id)}"`)}<details><summary>読取原文</summary><pre>${esc(p.context)}</pre></details></div>`;}

export function answerHTML(ctx){
 const r=ctx.inquiryResult;if(!r||r.catalog_id!==ctx.state.id)return '';
 if(r.revision!==ctx.state.version)return '<p class="notice">紙面の版が変わりました。もう一度「調べる」を押してください。</p>';
 if(['unsupported','restricted'].includes(r.kind))return `<section class="panel"><h2>質問内容を確認してください</h2><p>${esc(r.message)}</p>${r.examples?`<ul>${r.examples.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}</section>`;
 if(r.kind!=='prices')return '';
 return `<section class="panel"><h2>型番と価格の一覧</h2><p>${esc(r.message)}</p><div class="row" style="margin:15px 0">${badge(r.model_count+'型番候補')}${badge(r.occurrence_count+'掲載箇所','neutral')}<span class="muted">版 ${r.revision}</span><a class="button" href="/api/catalogs/${esc(ctx.state.id)}/inquiry.csv?q=${encodeURIComponent(r.query)}">この回答をCSV保存</a></div><div class="notice">確認済みの価格と、まだ紐づけを確認していない価格を別列にしています。同じ文字枠でも複数型番がある場合があります。候補に挙がった価格が全てその商品の価格という意味ではありません。</div><div class="product-table-wrap"><table class="product-table"><thead><tr><th>型番／掲載場所</th><th>確認済みの価格</th><th>未確認の価格候補</th><th>確認</th></tr></thead><tbody>${r.rows.map(o=>{
 const same=o.prices.filter(p=>p.relation==='same_frame'),other=o.prices.filter(p=>p.relation!=='same_frame');
 const shown=same.length?same:other.slice(0,1),remaining=same.length?other:other.slice(1);
 const candidates=o.confirmed?'—':(!same.length?'<small>同じ文字枠に価格なし。近い価格を候補表示</small>':'')+shown.map(p=>priceHTML(p,false,o.page_id)).join('')+(remaining.length?`<details><summary>ほかの周辺候補 ${remaining.length}件（未確認）</summary>${remaining.map(p=>priceHTML(p,false,o.page_id)).join('')}</details>`:'');
 return `<tr><td><strong>${esc(o.model)}</strong><small>p.${esc(o.page_label)} ／ 掲載順 ${o.order}</small>${btn('型番の出典','locate','',`data-page="${esc(o.page_id)}" data-element="${esc(o.element_id)}"`)}${o.source.linked||o.source.placement_estimated?'<small>連結枠・位置は要確認</small>':''}</td><td>${o.confirmed?o.prices.map(p=>priceHTML(p,true,o.page_id)).join(''):'未確定'}</td><td>${candidates||'価格を読み取れていません'}</td><td>${badge(o.status==='recheck'?'再確認が必要':o.confirmed?'確認済み':'未確認','neutral')}${ctx.actor.role==='editor'?btn('対応を確認・保存','inquiry-review','',`data-model="${esc(o.model)}" data-id="${esc(o.id)}"`):''}</td></tr>`;
 }).join('')||'<tr><td colspan="4">条件に合う価格データはありません。確認済み限定の場合は、未確認の候補を含めて調べられます。</td></tr>'}</tbody></table></div><p class="scope">${esc(r.scope)} 価格候補は掲載箇所ごとに最大12件です。</p></section>`;
}

export async function runInquiry(ctx,query){
 ctx.busy('カタログのデータを調べています…');
 try{
  const id=ctx.state.id,actor=ctx.actor.id;const state=await ctx.api('/api/catalogs/'+id);
  const result=await ctx.api(`/api/catalogs/${id}/inquiry?q=${encodeURIComponent(query)}`);
  if(ctx.state.id!==id||ctx.actor.id!==actor)throw new Error('カタログを開き直してから調べてください。');
  if(state.version!==result.revision)throw new Error('読み込み中に更新されました。もう一度調べてください。');
  ctx.state=state;ctx.searchQuery=query;ctx.inquiryResult=result;
  ctx.searchResult=result.search?{...result.search,revision:result.revision}:null;
  ctx.view='research';ctx.render();
 }finally{ctx.busy(false);}
}
