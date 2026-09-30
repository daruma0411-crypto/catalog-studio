import {esc,btn} from './ui.js';
export function markdown(text){
 const inline=s=>esc(s).replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>').replace(/`([^`]+)`/g,'<code>$1</code>');
 const lines=String(text).split('\n');let out='';
 for(let i=0;i<lines.length;i++){
  if(lines[i].includes('|')&&i+1<lines.length&&/^\s*\|?[ :|-]+\|[ :|-]*$/.test(lines[i+1])){
   const cells=s=>s.trim().replace(/^\||\|$/g,'').split('|').map(v=>inline(v.trim()));
   out+='<div class="product-table-wrap"><table class="product-table"><thead><tr>'+cells(lines[i]).map(c=>'<th>'+c+'</th>').join('')+'</tr></thead><tbody>';i+=2;
   while(i<lines.length&&lines[i].includes('|')){out+='<tr>'+cells(lines[i]).map(c=>'<td>'+c+'</td>').join('')+'</tr>';i++;}i--;out+='</tbody></table></div>';
  }else if(lines[i].trim())out+='<p>'+inline(lines[i].replace(/^#{1,6}\s+/,''))+'</p>';
 }
 return out;
}
function conversation(ctx){ctx.chats??={};const c=ctx.chats[ctx.state.id]??={messages:[],draft:''};c.id??=crypto.randomUUID();return c;}
export function chatHTML(ctx){
 const c=conversation(ctx),asset=id=>'/api/catalogs/'+encodeURIComponent(ctx.state.id)+'/assets/'+encodeURIComponent(id);
 return `<div class="content-view catalog-chat"><div class="content-head"><div><h1>カタログに相談</h1><p>${esc(ctx.state.title)}について、知りたいことをそのまま聞いてください。</p></div>${btn('新しい会話','chat-reset','ghost')}<details><summary>データ取得・AI連携</summary>${ctx.state.published_version?`<a class="button" href="/api/catalogs/${encodeURIComponent(ctx.state.id)}/released.zip">社内共有版を保存</a>`:''}${btn('AI・MCP連携について','mcp-info','ghost')}</details></div><div class="chat-history" aria-live="polite">${c.messages.length?c.messages.map(m=>`<article class="chat-message ${m.role}"><strong>${m.role==='user'?'あなた':'カタログAI'}</strong>${markdown(m.content)}${m.revision?`<small class="muted">版 ${m.revision} の情報${m.context_reset?' ／ 紙面更新のため以前の会話文脈をリセットしました':''}</small>`:''}${m.sources?.length?`<details><summary>参照した紙面</summary><div class="button-row">${m.sources.map(s=>btn(esc('['+s.id+'] p.'+s.page_label),'chat-locate','',`data-version="${m.revision}" data-page="${esc(s.page_id)}" data-element="${esc(s.element_id)}"`)).join('')}</div></details>`:''}${m.images?.length?`<div class="chat-images">${m.images.map(im=>`<section class="panel"><strong>${esc(im.name)}</strong><small>${im.product_confirmed?'型番との対応を確認済み':'型番との対応は未確認の候補'}</small>${im.preview.available?`<img src="${esc(asset(im.preview.id))}" alt="${esc(im.name)}" loading="lazy"><a class="text-link" href="${esc(asset(im.preview.id))}?download=1">表示用PNGを保存</a>`:'<p>表示用画像は未収録</p>'}${im.originals.map(a=>a.available?`<a class="text-link" href="${esc(asset(a.id))}?download=1">${a.association==='explicit'?'元ファイル':'同名の原本候補（要確認）'}：${esc(a.name)}</a>`:'').join('')}</section>`).join('')}</div>`:''}</article>`).join(''):'<p class="empty">価格や掲載ページ、画像、原稿の確認など。回答を見ながら続けて質問できます。</p>'}</div>${c.error?`<p class="notice" role="alert">${esc(c.error)}</p>`:''}<form id="chat-form" class="chat-composer"><textarea id="chat-message" aria-label="カタログへの質問" maxlength="3000" rows="3" placeholder="カタログについて質問する">${esc(c.draft)}</textarea><button type="submit" class="primary">送信</button></form><small class="muted">AIが選択中の冊子を調べます。質問と必要な情報をOpenAIへ送信します。原稿・紙面の変更は行いません。</small></div>`;
}
export async function sendChat(ctx){
 const c=conversation(ctx),message=document.getElementById('chat-message').value.trim();if(!message)return;
 c.draft=message;c.error='';const id=ctx.state.id,actor=ctx.actor.id;
 ctx.busy('カタログを調べて回答しています…');
 try{const r=await ctx.api('/api/catalogs/'+id+'/chat','POST',{message,conversation_id:c.id});if(ctx.state.id!==id||ctx.actor.id!==actor)return;const latest=await ctx.api('/api/catalogs/'+id);if(latest.version!==r.revision)throw new Error('回答後に紙面が更新されました。もう一度質問してください。');ctx.state=latest;c.messages.push({role:'user',content:message},{role:'assistant',content:r.answer,...r});c.draft='';}
 catch(e){c.error=e.message;}
 finally{ctx.busy(false);ctx.render();document.getElementById('chat-message')?.focus();}
}
export async function resetChat(ctx){ctx.busy('会話をリセットしています…');try{await ctx.api('/api/catalogs/'+ctx.state.id+'/chat','POST',{reset:true,conversation_id:conversation(ctx).id});ctx.chats[ctx.state.id]={messages:[],draft:''};ctx.render();}finally{ctx.busy(false);}}
export function captureChat(ctx){const el=document.getElementById('chat-message');if(el&&ctx.state)conversation(ctx).draft=el.value;}

export async function locateChat(ctx,target){
 ctx.busy('参照した紙面を確認しています…');
 try{const st=await ctx.api('/api/catalogs/'+ctx.state.id);if(st.version!==Number(target.dataset.version))throw new Error('回答した時点から紙面が変わっています。もう一度質問して最新の掲載場所を確認してください。');const p=st.document.pages.find(p=>p.id===target.dataset.page);if(!p||!p.elements.some(e=>e.id===target.dataset.element))throw new Error('参照箇所がありません。もう一度質問してください。');ctx.state=st;ctx.pageId=p.id;ctx.selection=target.dataset.element;ctx.groupMode=false;ctx.groupId=null;ctx.view='edit';ctx.mode='reference';ctx.render();}finally{ctx.busy(false);}
}
