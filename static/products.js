import {esc,btn,badge,empty} from './ui.js';
import {assetURL} from './paper.js';

const statuses={pending:'未確認',confirmed:'確認済み',recheck:'再確認',ignored:'対象外'};
const priceStates={unconfirmed:'未確認',confirmed:'価格を確認済み',not_applicable:'価格は該当なし',unavailable:'読取不能・不明'};
const kinds={body:'本体価格',set:'セット価格',list:'定価・希望小売',unspecified:'区分未確認'};
const relations={same_frame:'同じ文字枠',manual_group:'同じ商品ブロック',nearby:'近くにある候補'};
const options=(values,selected)=>Object.entries(values).map(([k,v])=>`<option value="${k}" ${k===selected?'selected':''}>${esc(v)}</option>`).join('');

export function productsHTML(ctx){
 const r=ctx.productReport;
 if(!r||r.catalog_id!==ctx.state.id||r.revision!==ctx.state.version)return `<div class="content-view"><p>最新の紙面から商品候補を読み込んでください。</p>${btn('商品候補を読み込む','product-open','primary')}</div>`;
 return `<div class="content-view"><div class="content-head"><div><h1>商品候補・型番と価格の一覧</h1><p>型番を入口に、価格・画像・説明の対応を紙面で確認します。</p></div>${btn('一覧を更新','product-open')}${btn('キーワード検索へ','nav','', 'data-view="research"')}</div><div class="scope">${esc(r.scope)}<br>価格候補は円表記のみ。同じページから価格は最大12件、画像6件、説明8件を提示します。候補にない情報は紙面で確認し、メモに残してください。</div><div class="stat-strip"><span><strong>${r.model_count}</strong>型番候補（対象外を除く）</span><span><strong>${r.occurrence_count}</strong>掲載箇所</span>${Object.entries(statuses).map(([k,v])=>`<span><strong>${r.counts[k]}</strong>${v}</span>`).join('')}</div>${r.orphan_review_count?`<p class="notice">削除・型番変更などで対応する掲載箇所がなくなった確認記録：${r.orphan_review_count}件。履歴は保持しています。</p>`:''}<div class="row" style="margin:20px 0"><input id="product-query" aria-label="型番候補の絞り込み" placeholder="型番で絞り込む" value="${esc(ctx.productQuery||'')}"><select id="product-status" aria-label="商品候補の確認状態"><option value="">すべての状態</option>${options(statuses,ctx.productStatus||'')}</select>${btn('絞り込む','product-filter')}<a class="button" href="/api/catalogs/${esc(ctx.state.id)}/products.csv">全候補をCSV保存</a></div><p class="muted">版 ${r.revision} の一覧。型番候補数は、同じ表記をまとめた数です。商品マスターの確定件数ではありません。</p><div class="product-table-wrap"><table class="product-table"><thead><tr><th>型番候補／掲載場所</th><th>確認状態</th><th>価格・関連情報</th><th>操作</th></tr></thead><tbody>${r.occurrences.filter(o=>(!ctx.productQuery||o.model.toUpperCase().includes(ctx.productQuery.toUpperCase()))&&(!ctx.productStatus||o.status===ctx.productStatus)).map(o=>{
 const review=o.review||{},confirmed=o.status==='confirmed',selected=confirmed?review.prices||[]:[];
 const prices=selected.map(p=>{const c=o.price_candidates.find(c=>c.id===p.id);return c?`${kinds[p.kind]} ¥${Number(c.amount).toLocaleString('ja-JP')}`:''}).filter(Boolean);
 return `<tr><td><strong>${esc(o.model)}</strong><small>p.${esc(o.page_label)} ／ 掲載順 ${o.order}</small><small>文字枠：${esc(o.element_id)}</small></td><td>${badge(statuses[o.status],o.status==='recheck'?'warning':'neutral')}<small>${confirmed?esc(priceStates[review.price_state]):'価格の対応は未確定'}</small>${o.status==='recheck'?'<small>元データが変わりました</small>':''}</td><td>${prices.length?prices.map(esc).join('<br>'):`<span class="muted">${o.price_candidates.length}件の価格候補（未確定）</span>`}<small>${confirmed?`関連を確認した画像 ${(review.image_ids||[]).length}件・説明 ${(review.description_ids||[]).length}件`:`画像候補 ${o.image_candidates.length}件・説明候補 ${o.description_candidates.length}件`}</small></td><td>${btn('画像・素材','product-images','',`data-id="${o.id}"`)}${btn('紙面で確認','product-locate','',`data-id="${o.id}"`)}${btn(ctx.actor.role==='editor'?'対応を確認・保存':'候補と確認内容を見る','product-review','',`data-id="${o.id}"`)}</td></tr>`;
 }).join('')||'<tr><td colspan="4">該当する候補はありません。</td></tr>'}</tbody></table></div></div>`;
}

export function reviewHTML(ctx,o){
 const r=o.review||{},stale=o.status==='recheck',locked=ctx.actor.role!=='editor';
 return `<h2>${esc(o.model)} の対応を確認</h2><p>p.${esc(o.page_label)} ／ 掲載順 ${o.order} ／ 元Story：${esc(o.source.story_id||'新規')}</p><pre class="scope">${esc(o.text)}</pre>${stale?'<p class="notice">元データが変わったため、選択を解除しています。前回のメモを参考に、改めて確認してください。</p>':''}<p class="muted">位置から提示した候補です。紐づけを保存しても紙面は変更されません。未選択の画像・説明は未確認として残ります。</p><fieldset ${locked?'disabled':''}><label for="product-decision">型番の確認</label><select id="product-decision">${options({confirmed:'型番候補を確認済みにする',ignored:'商品型番ではない（対象外）'},stale?'confirmed':r.status||'confirmed')}</select><h3>価格の対応</h3><select id="product-price-state" aria-label="価格の確認状態">${options(priceStates,stale?'unconfirmed':r.price_state||'unconfirmed')}</select>${o.price_candidates.map(p=>{const selected=!stale&&(r.prices||[]).find(s=>s.id===p.id);return `<div class="product-candidate"><label><input type="checkbox" data-product-price="${esc(p.id)}" ${selected?'checked':''}> ¥${esc(Number(p.amount).toLocaleString('ja-JP'))} <span class="muted">${relations[p.relation]}</span></label><select data-product-kind="${esc(p.id)}" aria-label="価格区分">${options(kinds,selected?.kind||p.kind)}</select><pre>${esc(p.context)}</pre><small>文字枠：${esc(p.element_id)}</small></div>`}).join('')||empty('円表記の価格は読み取れていません。原版を確認してください。')}<h3>画像の対応</h3><div class="product-images">${o.image_candidates.map(i=>`<label class="product-candidate"><input type="checkbox" data-product-image="${esc(i.id)}" ${!stale&&(r.image_ids||[]).includes(i.id)?'checked':''}>${esc(i.name)}<small>${relations[i.relation]}</small>${i.asset_id?`<img src="${esc(assetURL(ctx,i.asset_id))}" alt="${esc(i.name)}" loading="lazy">`:'<small>素材なし・原版で確認</small>'}<small>画像枠：${esc(i.element_id)}</small></label>`).join('')||empty('画像候補はありません。')}</div><h3>説明の対応</h3>${o.description_candidates.map(d=>`<label class="product-candidate"><input type="checkbox" data-product-description="${esc(d.id)}" ${!stale&&(r.description_ids||[]).includes(d.id)?'checked':''}>${relations[d.relation]}<pre>${esc(d.text)}</pre><small>文字枠：${esc(d.id)}</small></label>`).join('')||empty('説明候補はありません。')}<label for="product-note">確認メモ（候補不足・注意点など）</label><textarea id="product-note" maxlength="3000">${esc(r.note||'')}</textarea>${locked?'':btn('確認内容を保存','product-save','primary full')}</fieldset>${r.author?`<p class="muted">前回確認：${esc(r.author)} ／ ${esc(r.created)}</p>`:''}${btn('閉じる','close-modal','full')}`;
}

export async function productAction(ctx,action,target){
 if(ctx.actor.role==='reader')throw new Error('商品候補は販促・開発部門で確認してください。');
 if(action==='product-open'){
  ctx.busy('商品候補と掲載場所を読み込んでいます…');
  try{const id=ctx.state.id;const state=await ctx.api('/api/catalogs/'+id);const result=await ctx.api('/api/catalogs/'+id+'/products');if(state.version!==result.revision)throw new Error('読み込み中に別の変更がありました。もう一度一覧を開いてください。');ctx.state=state;ctx.productReport=result;ctx.view='products';ctx.render();}finally{ctx.busy(false);}return;
 }
 if(action==='product-filter'){ctx.productQuery=document.getElementById('product-query').value.trim();ctx.productStatus=document.getElementById('product-status').value;ctx.render();return;}
 const o=ctx.productReport?.occurrences.find(o=>o.id===target.dataset.id);
 if(action==='product-locate'){
  if(!o)throw new Error('一覧を更新してください。');
  ctx.pageId=o.page_id;ctx.selection=o.element_id;ctx.groupMode=false;ctx.groupId=null;ctx.view='edit';ctx.mode='reference';ctx.render();return;
 }
 if(action==='product-images'){
  if(!o)throw new Error('一覧を更新してください。');
  ctx.busy('画像と元ファイルを確認しています…');
  try{const r=await ctx.api('/api/catalogs/'+ctx.state.id+'/product-images?occurrence='+encodeURIComponent(o.id));if(r.revision!==ctx.productReport.revision)throw new Error('紙面が更新されています。商品一覧を更新してください。');ctx.showModal(imageResourcesHTML(ctx,r));}finally{ctx.busy(false);}return;
 }
 if(action==='product-review'){
  if(!o)throw new Error('一覧を更新してください。');
  ctx.productReviewTarget={catalog_id:ctx.state.id,revision:ctx.productReport.revision,occurrence:o};ctx.showModal(reviewHTML(ctx,o));return;
 }
 if(action==='product-save'){
  const t=ctx.productReviewTarget;
  if(ctx.actor.role!=='editor'||!t||t.catalog_id!==ctx.state.id)throw new Error('一覧を開き直してください。');
  const root=document.getElementById('modal-content'),val=id=>root.querySelector('#'+id).value;
  const prices=[...root.querySelectorAll('[data-product-price]:checked')].map(input=>({id:input.dataset.productPrice,kind:[...root.querySelectorAll('[data-product-kind]')].find(s=>s.dataset.productKind===input.dataset.productPrice).value}));
  const op={type:'product_review',occurrence_id:t.occurrence.id,fingerprint:t.occurrence.fingerprint,status:val('product-decision'),price_state:val('product-price-state'),prices,image_ids:[...root.querySelectorAll('[data-product-image]:checked')].map(e=>e.dataset.productImage),description_ids:[...root.querySelectorAll('[data-product-description]:checked')].map(e=>e.dataset.productDescription),note:val('product-note')};
  ctx.busy('確認内容を保存しています…');
  try{ctx.state=await ctx.api('/api/catalogs/'+t.catalog_id+'/operations','POST',{version:t.revision,operation:op});ctx.productReport=await ctx.api('/api/catalogs/'+t.catalog_id+'/products');ctx.closeModal();ctx.view='products';ctx.render();ctx.notify('商品候補の確認内容を保存しました。');}finally{ctx.busy(false);}
 }
}

export function imageResourcesHTML(ctx,r){
 const url=id=>'/api/catalogs/'+encodeURIComponent(r.catalog_id)+'/assets/'+encodeURIComponent(id);
 const download=(id,label)=>`<a class="button" href="${esc(url(id))}?download=1">${esc(label)}</a>`;
 return `<h2>${esc(r.model)} の画像・素材</h2><p>p.${esc(r.page_label)} ／ 版 ${r.revision}</p><p class="scope">${esc(r.scope)}</p>${r.images.map(i=>`<section class="panel"><h3>${esc(i.name)}</h3>${badge(i.product_confirmed?'型番との対応を確認済み':'型番との対応は未確認',i.product_confirmed?'':'neutral')}<p>${esc(relations[i.relation])}</p>${i.preview.available?`<img src="${esc(url(i.preview.id))}" alt="${esc(i.name)}" style="max-width:100%;max-height:240px;object-fit:contain"><p>${download(i.preview.id,'表示用PNGを保存')}</p>`:'<p class="notice">表示用画像は未収録、またはファイルがありません。</p>'}<h4>元ファイル</h4>${i.originals.map(a=>`<p><strong>${esc(a.name)}</strong><br>${a.association==='explicit'?'アップロードした元ファイル':'同名の原本候補（内容を確認してください）'}<br>${a.available?download(a.id,a.association==='explicit'?'元ファイルを保存':'原本候補を保存'):'ファイルがありません'}</p>`).join('')||'<p>対応する元ファイルは未収録、または特定できていません。</p>'}<p class="muted">この冊子内の使用箇所：${i.uses.map(u=>'p.'+esc(u.page_label)+'（'+esc(u.element_id)+'）').join('、')}</p></section>`).join('')||empty('この掲載箇所に画像候補はありません。')}${btn('閉じる','close-modal','full')}`;
}
