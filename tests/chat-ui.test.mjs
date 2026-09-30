import assert from 'node:assert/strict';
import {chatHTML,markdown} from '../static/chat.js';
const ctx={state:{id:'c',title:'Test'},actor:{id:'a'}};
let html=chatHTML(ctx);assert.match(html,/カタログに相談/);assert.doesNotMatch(html,/商品候補・型番と価格の一覧|product-open|2万円/);
ctx.chats.c.messages=[{role:'assistant',content:'<script>alert(1)</script>\n**価格**\n| 型番 | 価格 |\n|---|---|\n| ABC | 9000 |',revision:1,sources:[{id:'S1',page_id:'p',element_id:'e',page_label:'1'}]}];
html=chatHTML(ctx);assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>/);assert.match(html,/<table/);assert.match(html,/data-act="chat-locate"/);
assert.doesNotMatch(markdown('[x](javascript:alert(1))'),/<a/);
console.log('PASS: chat UI, no fixed list button, safe Markdown and source actions');

ctx.chats.c.messages[0].sources[0].page_label='<img src=x onerror=alert(1)>';assert.doesNotMatch(chatHTML(ctx),/<img src=x/);

const {locateChat}=await import('../static/chat.js');
const nav={state:{id:'c'},busy(){},render(){},api:async()=>({id:'c',version:3,document:{pages:[{id:'p',elements:[{id:'e'}]}]}})};
await assert.rejects(()=>locateChat(nav,{dataset:{version:'2',page:'p',element:'e'}}),/紙面が変わっています/);
await locateChat(nav,{dataset:{version:'3',page:'p',element:'e'}});assert.equal(nav.pageId,'p');assert.equal(nav.view,'edit');
