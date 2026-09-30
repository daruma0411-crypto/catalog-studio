import assert from 'node:assert/strict';
import {answerHTML,runInquiry} from '../static/inquiry.js';
const ctx={state:{id:'c',version:3},actor:{id:'p',role:'editor'},inquiryResult:{catalog_id:'c',revision:3,kind:'prices',query:'価格一覧',model_count:1,occurrence_count:1,message:'候補',scope:'本文',rows:[{id:'o',model:'RX-359NB',page_label:'1',order:1,page_id:'p',element_id:'e',source:{},status:'pending',confirmed:false,prices:[{amount:'9000',kind:'unspecified',relation:'same_frame',element_id:'e',context:'<script>bad</script>'}]}]}};
let html=answerHTML(ctx);assert.match(html,/¥9,000/);assert.match(html,/未確定/);assert.match(html,/同じ文字枠から読取/);assert.match(html,/&lt;script&gt;/);assert.match(html,/inquiry.csv/);
ctx.state.version=4;assert.doesNotMatch(answerHTML(ctx),/¥9,000/);
let calls=0;ctx.busy=()=>{};ctx.api=async()=>++calls===1?{id:'c',version:4}:{revision:5};ctx.render=()=>{throw Error('must not render mixed versions');};
await assert.rejects(()=>runInquiry(ctx,'型番と価格を一覧にして'),/更新/);
console.log('PASS: actual prices, provisional labels, source escapes and version consistency');
