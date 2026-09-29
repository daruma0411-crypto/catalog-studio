import {esc,btn,badge,empty,field,textarea,roleName,threadHTML} from './ui.js';
import {renderPaper,assetURL,estimateSplit,overflowCount} from './paper.js';
import {workspaceHTML,inspectorHTML} from './workspace.js';
import {sourceHTML,planHTML,researchHTML,handoffHTML} from './views.js';

const root=document.getElementById('app'),modal=document.getElementById('modal');
const $=id=>document.getElementById(id);
const demo={editor:['promo','promo-demo'],developer:['development','development-demo'],reader:['reader','reader-demo']};
let resizeObserver,toastTimer;
const ctx={actor:null,csrf:'',state:null,catalogs:[],pageId:null,selection:null,view:'edit',railTab:'inbox',mode:'reference',zoom:'fit',scale:1,searchQuery:'ERD9717WA',searchResult:null,drafts:{},dragMoved:false,
 notify,
 currentPage(){return this.state?.document.pages.find(p=>p.id===this.pageId)||this.state?.document.pages[0]},
 element(){return this.currentPage()?.elements.find(e=>e.id===this.selection)},
 renderInspector(){const el=$('inspector');if(el)el.innerHTML=inspectorHTML(this)},
 async api(path,method='GET',data){const res=await fetch(path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':this.csrf},...(data?{body:JSON.stringify(data)}:{})});const body=await res.json();if(!res.ok){const error=new Error(body.error||'処理に失敗しました。');error.status=res.status;throw error;}return body;},
 async op(operation,message='保存しました'){
  busy('変更を保存しています…');
  try{this.state=await this.api(`/api/catalogs/${this.state.id}/operations`,'POST',{version:this.state.version,operation});
   if(operation.type==='edit_text'||operation.type==='replace_text')delete this.drafts[operation.element_id];
   if(operation.type==='flow_text'){const c=this.state.changes.at(-1);this.pageId=c.destination_page_id;this.selection=c.continuation.id;}
   else if(operation.type==='add_page'){this.pageId=this.state.changes.at(-1).page_id;this.selection=null;}
   else if(this.selection){const p=this.state.document.pages.find(p=>p.elements.some(e=>e.id===this.selection));if(p)this.pageId=p.id;}
   render();notify(message);return this.state;
  }finally{busy(false);}
 },
};

function notify(message,error=false){const el=$('toast');clearTimeout(toastTimer);el.hidden=false;el.classList.toggle('error',error);el.textContent=message;toastTimer=setTimeout(()=>el.hidden=true,error?10000:4300);}
function busy(message){document.querySelector('.busy-cover')?.remove();if(message){const cover=document.createElement('div');cover.className='busy-cover';cover.innerHTML=`<div role="status">${esc(message)}</div>`;document.body.append(cover);}}
function showModal(html){$('modal-content').innerHTML=html;if(!modal.open)modal.showModal();}
function closeModal(){modal.close();}

function loginHTML(){return `<main class="login"><div class="row"><div class="brand-mark">編</div><strong>カタログ編集室</strong>${badge('ローカル実証版','neutral')}</div><div class="hero"><h1>届いた原稿から、<br>伝わる紙面と指示へ。</h1><p>開発からの情報を受け取り、紙面で試し、制作へ渡す。<br>商品情報を探すときも、掲載された場所まで戻れます。</p></div><div class="login-grid"><section class="demo-roles">${Object.entries(demo).map(([r])=>`<button class="role-choice" data-act="demo-login" data-role="${r}"><div><strong>${roleName(r)}として開く</strong><small>${{editor:'原稿確認・紙面編集・台割・制作指示',developer:'原稿と素材の登録・質疑応答',reader:'共有カタログ閲覧・検索・ダウンロード'}[r]}</small></div><span class="push">→</span></button>`).join('')}</section><section class="panel"><h3>アカウントでログイン</h3><form id="login-form">${field('ユーザー名','username','promo')}${field('パスワード','password','promo-demo','password')}<button class="primary full" type="submit">ログイン</button></form><p class="login-foot">このPC内の実証用アカウントです。上の役割ボタンでも切り替えられます。本番向けSSO・組織管理は含みません。</p></section></div></main>`;}

function headerHTML(){const st=ctx.state;const tabs=ctx.actor.role==='editor'?[['source','原稿・質疑応答'],['edit','紙面を編集'],['plan','台割'],['research','調査・データ活用'],['handoff','制作への指示']]:ctx.actor.role==='developer'?[['source','原稿・質疑応答'],['edit','紙面を確認'],['research','調査']]:[['edit','カタログを閲覧'],['research','調査・データ活用']];return `<header class="header"><div class="brand-mark">編</div><div class="header-title"><strong>カタログ編集室</strong><small>情報を受け取り、紙面で考える</small></div><select id="catalog-select" aria-label="カタログ">${ctx.catalogs.map(c=>`<option value="${c.id}" ${c.id===st?.id?'selected':''}>${esc(c.title)}</option>`).join('')||'<option>カタログなし</option>'}</select>${ctx.actor.role==='editor'?btn('＋ 取り込み','import','ghost'):''}<div class="push user"><strong>${esc(ctx.actor.name)}</strong><small>ローカル実証版</small></div><select id="account-select" aria-label="実証用アカウント" style="width:150px">${Object.keys(demo).map(r=>`<option value="${r}" ${ctx.actor.role===r?'selected':''}>${roleName(r)}</option>`).join('')}</select>${btn('ログアウト','logout','ghost')}</header>${st?`<nav class="nav">${tabs.map(([v,label])=>btn(label+(v==='handoff'?` <span class="badge neutral">${st.changes.length}</span>`:''),'nav',ctx.view===v?'active':'',`data-view="${v}"`)).join('')}<span class="save-state push">保存済み · 版 ${st.version}${ctx.actor.role==='reader'?'（共有版）':''}</span>${ctx.actor.role==='editor'?btn('元に戻す','undo','ghost',!st.can_undo?'disabled':''):''}${btn('更新','reload','ghost')}</nav>`:''}<input type="file" id="catalog-upload" accept=".zip,.idml" hidden>`;}

function render(){
 resizeObserver?.disconnect();
 if(!ctx.actor){root.innerHTML=loginHTML();return;}
 if(!ctx.state){root.innerHTML=headerHTML()+`<main class="blank-app"><section class="panel"><h1>${ctx.actor.role==='reader'?'まだ共有されたカタログがありません':'カタログから始めましょう'}</h1><p class="empty">${ctx.actor.role==='reader'?'販促担当が社内閲覧用の版を共有すると、ここから閲覧・検索できます。':'IDML、またはIDML・画像・PDFをまとめたZIPを取り込めます。原版を残して編集を始めます。'}</p>${ctx.actor.role==='editor'?btn('IDML・ZIPを取り込む','import','primary'):''}</section></main>`;return;}
 const page=ctx.currentPage();ctx.pageId=page.id;
 if(ctx.actor.role==='reader')ctx.mode='html';
 const content=ctx.view==='edit'?workspaceHTML(ctx):ctx.view==='source'?sourceHTML(ctx):ctx.view==='plan'?planHTML(ctx):ctx.view==='research'?researchHTML(ctx):handoffHTML(ctx);
 root.innerHTML=headerHTML()+content;
 if(ctx.view==='edit'){
  if(!page.reference_asset)ctx.mode='html';
  $('render-mode').value=ctx.mode;
  renderPaper(ctx);
  resizeObserver=new ResizeObserver(()=>renderPaper(ctx));resizeObserver.observe($('stage'));
  if(ctx.mode==='html'){const n=overflowCount(ctx);if(n)$('overflow-label').textContent=` ／ 収まり要確認 ${n}枠`;}
 }
}

async function loadCatalog(id){ctx.state=await ctx.api('/api/catalogs/'+id);ctx.pageId=ctx.state.document.pages[0].id;const page=ctx.currentPage();const first=page.elements.find(e=>e.kind==='text'&&/18,500/.test(e.text))||page.elements.find(e=>e.kind==='text');ctx.selection=first?.id;ctx.searchResult=null;ctx.drafts={};render();}
async function refreshCatalogs(){ctx.catalogs=await ctx.api('/api/catalogs');if(!ctx.catalogs.length){ctx.state=null;render();return;}const id=ctx.catalogs.some(c=>c.id===ctx.state?.id)?ctx.state.id:ctx.catalogs[0].id;await loadCatalog(id);}
async function login(user,password){busy('編集室を開いています…');try{const session=await ctx.api('/api/login','POST',{username:user,password});ctx.actor=session.actor;ctx.csrf=session.csrf;ctx.state=null;ctx.view=ctx.actor.role==='developer'?'source':ctx.actor.role==='reader'?'research':'edit';await refreshCatalogs();}finally{busy(false);}}
async function search(query=ctx.searchQuery){ctx.searchQuery=query;ctx.searchResult=await ctx.api(`/api/catalogs/${ctx.state.id}/search?q=${encodeURIComponent(query)}`);ctx.view='research';render();}
function readFile(file){if(file.size>60*1024*1024)throw new Error('ファイルは60MB以下にしてください。');return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result).split(',')[1]);r.onerror=()=>reject(new Error('ファイルを読み取れませんでした。'));r.readAsDataURL(file);});}
async function upload(files,importing=false){busy(importing?'IDMLを解析しています。画像と比較用紙面を準備します…':'原稿・素材を取り込んでいます…');try{for(const file of files){const content=await readFile(file);if(importing){ctx.state=await ctx.api('/api/catalogs','POST',{filename:file.name,content});ctx.catalogs=await ctx.api('/api/catalogs');ctx.pageId=ctx.state.document.pages[0].id;ctx.selection=null;ctx.view='edit';ctx.mode='reference';}else{ctx.state=await ctx.api(`/api/catalogs/${ctx.state.id}/attachments`,'POST',{filename:file.name,content,version:ctx.state.version});}}render();notify(importing?'カタログを取り込みました。原版を保持しています。':'素材を保存しました。表データは「内容を見る」から確認できます。');}finally{busy(false);}}

function previewAsset(a){
 if(a.kind==='spreadsheet'){
  showModal(`<h2>${esc(a.name)}</h2><div class="scope">${esc(a.preview.note)}</div>${a.preview.sheets.map((sheet,si)=>`<h3>${esc(sheet.name)}</h3><div class="table-wrap" style="margin:12px 0 22px"><table><tbody>${sheet.rows.map((row,ri)=>`<tr>${row.map(v=>`<${ri===0?'th':'td'}>${esc(v)}</${ri===0?'th':'td'}>`).join('')}${ri>0?`<td>${btn('原稿にする','row-submission','',`data-asset="${a.id}" data-sheet="${si}" data-row="${ri}"`)}</td>`:''}</tr>`).join('')}</tbody></table></div>`).join('')}`);
 }else if(a.kind==='image')showModal(`<h2>${esc(a.name)}</h2><img style="max-width:100%;max-height:60vh;object-fit:contain" src="${assetURL(ctx,a.preview_asset)}" alt="素材画像">`);
 else showModal(`<h2>${esc(a.name)}</h2>${a.text_preview?`<pre>${esc(a.text_preview)}</pre>`:''}<a class="button primary" href="${assetURL(ctx,a.id)}" download>ファイルを保存</a>`);
}

function flowDialog(){
 const el=ctx.element();if(!el||el.kind!=='text')return;
 const draft=$('edit-text')?.value;
 if(draft!==undefined&&draft!==el.text)throw new Error('文章を上書き保存してから、ページ送りを試してください。');
 const fit=estimateSplit(el.text,el.bounds,el.font_size||8),codepoints=[...el.text.slice(0,fit)].length;
 const total=[...el.text].length;
 showModal(`<h2>続きを次ページへ送る</h2><p class="muted">ブラウザの表示で収まりを見積もります。送り始める位置を確認して保存してください。</p><div class="notice" style="margin-top:15px">${fit>=el.text.length?'この枠には全文が収まる見積もりです。0文字を指定すると文章全体を移動します。':`先頭${codepoints}文字までが収まる見積もりです。`} InDesignの組版結果を保証するものではありません。</div>${field('この文字数を元ページに残す','flow-count',fit>=el.text.length?0:codepoints,'number',`min="0" max="${total-1}"`)}${field('新規ページの掲載内容','flow-title','追加説明・続き')}<div class="diff-grid"><div><small>元ページに残す</small><pre id="flow-head"></pre></div><div><small>次ページへ送る</small><pre id="flow-tail"></pre></div></div>${btn('この位置で分けて、新規ページに送る','confirm-flow','primary full')}`);updateFlowPreview();
}
function updateFlowPreview(){const el=ctx.element();if(!el||!$('flow-count'))return;const chars=[...el.text],n=Number($('flow-count').value);$('flow-head').textContent=chars.slice(0,n).join('');$('flow-tail').textContent=chars.slice(n).join('');}

async function act(action,target){
 const el=ctx.element();
 switch(action){
 case 'demo-login':return login(...demo[target.dataset.role]);
 case 'logout':await ctx.api('/api/logout','POST',{});ctx.actor=null;ctx.state=null;return render();
 case 'import':return $('catalog-upload').click();
 case 'nav':ctx.view=target.dataset.view;return render();
 case 'reload':if(ctx.state){const page=ctx.pageId;ctx.state=await ctx.api('/api/catalogs/'+ctx.state.id);ctx.pageId=page;render();notify('最新の保存内容を読み込みました。');}return;
 case 'rail-tab':ctx.railTab=target.dataset.tab;return render();
 case 'go-source':ctx.view='source';return render();
 case 'open-page':ctx.pageId=target.dataset.page;ctx.selection=null;ctx.view='edit';return render();
 case 'source-detail':ctx.view='source';render();document.getElementById('submission-'+target.dataset.submission)?.scrollIntoView({behavior:'smooth'});return;
 case 'locate':{
  const found=ctx.state.document.pages.find(p=>p.elements.some(e=>e.id===target.dataset.element));ctx.pageId=found?.id||target.dataset.page;ctx.selection=target.dataset.element;ctx.view='edit';ctx.mode=ctx.actor.role==='reader'?'html':'reference';render();return;
 }
 case 'zoom-fit':ctx.zoom='fit';return renderPaper(ctx);
 case 'zoom-in':ctx.zoom=Math.min(1.8,ctx.scale+.15);return renderPaper(ctx);
 case 'zoom-out':ctx.zoom=Math.max(.3,ctx.scale-.15);return renderPaper(ctx);
 case 'undo':return ctx.op({type:'undo'},'直前の編集を取り消しました。');
 case 'save-text':return ctx.op({type:'edit_text',element_id:el.id,text:$('edit-text').value},'文章と変更前後を保存しました。');
 case 'replace-text':return ctx.op({type:'replace_text',element_id:el.id,before:$('replace-before').value,after:$('replace-after').value},'指定した文字列だけを変更しました。');
 case 'save-bounds':return ctx.op({type:'move',element_id:el.id,bounds:[0,1,2,3].map(i=>Number($('bound-'+i).value)*72/25.4)},'位置・サイズを保存しました。');
 case 'move-page':return ctx.op({type:'move',element_id:el.id,page_id:$('move-page').value,bounds:el.bounds},'ページ間の移動を保存しました。');
 case 'replace-image':return ctx.op({type:'replace_image',element_id:el.id,asset_id:$('replacement-image').value},'画像を差し替えました。元素材は履歴に残ります。');
 case 'restore-element':return ctx.op({type:'restore',element_id:el.id},'削除指定を取り消しました。');
 case 'delete-dialog':showModal(`<h2>選択した箇所を削除指定</h2><pre>${esc(el.text||el.name)}</pre><label for="delete-policy">空きスペースの扱い</label><select id="delete-policy"><option>空きを残す</option><option>空きを詰める（制作へ指示）</option><option>配置を制作会社に相談</option></select><p class="muted" style="margin-top:10px">元データは保持します。「元に戻す」で取り消せます。</p>${btn('この箇所を削除指定','confirm-delete','primary full')}`);return;
 case 'confirm-delete':{const policy=$('delete-policy').value;closeModal();return ctx.op({type:'delete',element_id:el.id,space_policy:policy},'削除対象と空きの扱いを保存しました。');}
 case 'new-text':showModal(`<h2>紙面に文章を追加</h2>${textarea('追加する文章','new-text-value','',6)}${btn('このページに追加','confirm-new-text','primary full')}`);return;
 case 'confirm-new-text':{const value=$('new-text-value').value;closeModal();const st=await ctx.op({type:'add_text',page_id:ctx.pageId,text:value});ctx.selection=st.changes.at(-1).element_id;render();return;}
 case 'flow-dialog':return flowDialog();
 case 'confirm-flow':{const split=Number($('flow-count').value),title=$('flow-title').value;closeModal();return ctx.op({type:'flow_text',element_id:el.id,split_at:split,title},'続きを新規ページに送りました。');}
 case 'new-page':showModal(`<h2>新規ページ</h2>${field('掲載する内容','new-page-title','新規ページ')}${btn('台割に追加','confirm-new-page','primary full')}`);return;
 case 'confirm-new-page':{const title=$('new-page-title').value;closeModal();return ctx.op({type:'add_page',title},'新規ページを追加しました。');}
 case 'rename-page':return ctx.op({type:'rename_page',page_id:target.dataset.page,title:$('page-title-'+target.dataset.page).value});
 case 'order-page':{const ids=ctx.state.document.pages.map(p=>p.id),i=ids.indexOf(target.dataset.page),j=i+Number(target.dataset.dir);if(j<0||j>=ids.length)return;[ids[i],ids[j]]=[ids[j],ids[i]];return ctx.op({type:'reorder_pages',page_ids:ids},'掲載順を保存しました。');}
 case 'delete-page':return ctx.op({type:'delete_page',page_id:target.dataset.page},'ページの削除を保存しました。');
 case 'add-element-comment':return ctx.op({type:'comment',element_id:el.id,destination:$('comment-destination').value,text:$('element-comment').value},'この箇所にコメントを記録しました。');
 case 'reply':return ctx.op({type:'reply',thread_id:target.dataset.thread,text:$('reply-'+target.dataset.thread).value},'回答を記録しました。解決状態は別に確認します。');
 case 'resolve-thread':return ctx.op({type:target.dataset.status==='open'?'resolve_thread':'reopen_thread',thread_id:target.dataset.thread});
 case 'add-submission':return ctx.op({type:'add_submission',title:$('submission-title').value,target:$('submission-target').value,text:$('submission-text').value},'受け取り原稿を登録しました。');
 case 'submission-search':return search(target.dataset.target||ctx.searchQuery);
 case 'submission-question':case 'general-question':showModal(`<h2>原稿について確認する</h2><label for="question-to">宛先</label><select id="question-to"><option value="developer">開発部門へ</option><option value="editor">販促担当へ</option><option value="production">制作会社へ</option></select>${textarea('確認したいこと','question-text','',4)}${btn('確認事項を記録','confirm-question','primary full',`data-submission="${target.dataset.submission||''}"`)}`);return;
 case 'confirm-question':{const op={type:'comment',text:$('question-text').value,destination:$('question-to').value,submission_id:target.dataset.submission||null};closeModal();return ctx.op(op,'確認事項を記録しました。');}
 case 'preview-asset':return previewAsset(ctx.state.attachments.find(a=>a.id===target.dataset.asset));
 case 'row-submission':{const a=ctx.state.attachments.find(a=>a.id===target.dataset.asset),sheet=a.preview.sheets[Number(target.dataset.sheet)],ri=Number(target.dataset.row),row=sheet.rows[ri];closeModal();return ctx.op({type:'add_submission',title:`${a.name} · ${sheet.name} ${ri+1}行目`,target:row[0]||'',text:row.map((v,i)=>`${sheet.rows[0][i]||'列'+(i+1)}：${v}`).join('\n'),asset_ids:[a.id],source_ref:{asset_id:a.id,sheet:sheet.name,row:ri+1}},'表の行を、出典付きの原稿として登録しました。');}
 case 'publish':await ctx.op({type:'publish'},'この版を社内閲覧用に共有しました。');ctx.catalogs=await ctx.api('/api/catalogs');render();return;
 case 'mcp-info':showModal(`<h2>同じ商品情報を、AIから調べる</h2><p class="muted">ローカルの読み取り専用MCPサーバーを用意しています。社内共有された版だけを参照します。</p><div class="scope">利用できるツール：catalog.list_catalogs ／ catalog.find_occurrences ／ catalog.get_page</div><pre>python mcp_server.py --data ./data</pre><p class="muted">接続設定はアプリのREADMEを参照してください。未公開原稿や作業版はMCPに返しません。現在のアプリへの自動登録は行っていません。</p>`);return;
 }
}

document.addEventListener('click',event=>{const target=event.target.closest('[data-act]');if(target&&!target.disabled){event.preventDefault();Promise.resolve(act(target.dataset.act,target)).catch(error=>notify(error.message,true));}});
document.addEventListener('submit',event=>{if(event.target.id==='login-form'){event.preventDefault();login($('username').value,$('password').value).catch(e=>notify(e.message,true));}if(event.target.id==='search-form'){event.preventDefault();search($('search-query').value).catch(e=>notify(e.message,true));}});
document.addEventListener('input',event=>{if(event.target.id==='edit-text'&&ctx.selection)ctx.drafts[ctx.selection]=event.target.value;if(event.target.id==='flow-count')updateFlowPreview();});
document.addEventListener('change',event=>{
 const target=event.target;
 (async()=>{
  if(target.id==='catalog-select')return loadCatalog(target.value);
  if(target.id==='account-select')return login(...demo[target.value]);
  if(target.id==='catalog-upload')return upload([...target.files],true);
  if(['asset-upload','asset-upload-inspector','source-upload'].includes(target.id))return upload([...target.files]);
  if(target.id==='render-mode'){ctx.mode=target.value;renderPaper(ctx);return;}
  if(target.dataset.submissionStatus)return ctx.op({type:'submission_status',submission_id:target.dataset.submissionStatus,status:target.value});
  if(target.dataset.changeStatus)return ctx.op({type:'change_status',change_id:target.dataset.changeStatus,status:target.value});
 })().catch(e=>notify(e.message,true));
});
document.addEventListener('keydown',event=>{if((event.ctrlKey||event.metaKey)&&event.key==='s'&&ctx.view==='edit'&&ctx.actor?.role==='editor'&&!modal.open){event.preventDefault();if($('edit-text'))act('save-text',{}).catch(e=>notify(e.message,true));}});
window.addEventListener('beforeunload',event=>{if(Object.entries(ctx.drafts).some(([id,value])=>ctx.state?.document.pages.flatMap(p=>p.elements).find(e=>e.id===id)?.text!==value)){event.preventDefault();event.returnValue='';}});

try{const session=await ctx.api('/api/session');ctx.actor=session.actor;ctx.csrf=session.csrf;ctx.view=ctx.actor.role==='developer'?'source':ctx.actor.role==='reader'?'research':'edit';await refreshCatalogs();}catch{ctx.actor=null;render();}
