import assert from 'node:assert/strict';
import {libraryHTML,libraryAction} from '../static/library.js';
const ctx={actor:{role:'editor'},libraryBooks:[{id:'a',title:'<script>A</script>',page_count:2}],drafts:{},busy(){},render(){},api:async()=>({id:'a',document:{pages:[{id:'p'}]}})};
let html=libraryHTML(ctx);assert.match(html,/&lt;script&gt;/);assert.match(html,/カタログを追加/);assert.match(html,/この冊子を開く/);assert.doesNotMatch(html,/checkbox|横断|共通|変更案件|campaign|library-search/);
ctx.actor.role='developer';assert.doesNotMatch(libraryHTML(ctx),/カタログを追加/);
await libraryAction(ctx,'library-paper',{dataset:{catalog:'a'}});assert.equal(ctx.state.id,'a');assert.equal(ctx.pageId,'p');assert.equal(ctx.view,'edit');
await assert.rejects(()=>libraryAction(ctx,'library-create',{}),/連携機能は提供していません/);
console.log('PASS: simple shelf, role permissions, book opening, retired actions blocked');
