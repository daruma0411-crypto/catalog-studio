import assert from 'node:assert/strict';
import {productsHTML,reviewHTML,productAction} from '../static/products.js';
const occurrence={id:'o',model:'RX-359NB',page_id:'p',page_label:'1',order:1,element_id:'f',source:{},text:'<script>bad</script>',status:'recheck',price_candidates:[{id:'x',amount:'9000',kind:'body',context:'¥9,000',relation:'same_frame'}],image_candidates:[],description_candidates:[],review:{prices:[{id:'x',kind:'body'}],price_state:'confirmed'}};
const ctx={actor:{role:'editor'},state:{id:'c',version:2},productReport:{catalog_id:'c',revision:2,scope:'scope',model_count:1,occurrence_count:1,counts:{recheck:1},occurrences:[occurrence]}};
assert.match(productsHTML(ctx),/価格の対応は未確定/);
assert.doesNotMatch(productsHTML(ctx),/本体価格 ¥9,000/);
assert.doesNotMatch(reviewHTML(ctx,occurrence),/data-product-price="x" checked/);
assert.match(reviewHTML(ctx,occurrence),/&lt;script&gt;/);
ctx.state.version=3;assert.doesNotMatch(productsHTML(ctx),/RX-359NB/);ctx.state.version=2;
ctx.actor.role='developer';assert.match(reviewHTML(ctx,occurrence),/fieldset disabled/);assert.doesNotMatch(reviewHTML(ctx,occurrence),/確認内容を保存/);
ctx.actor.role='reader';await assert.rejects(()=>productAction(ctx,'product-open',{}),/販促・開発/);
console.log('PASS: stale prices excluded, stale selection reset, escaped evidence, role permissions');

const {imageResourcesHTML}=await import('../static/products.js');
const resources={catalog_id:'c',model:'RX-359NB',page_label:'1',revision:2,scope:'scope',images:[{name:'<x>',product_confirmed:false,relation:'nearby',preview:{id:'p.png',available:true},originals:[{id:'a.tif',name:'original.tif',association:'name_candidate',available:true},{id:'missing.tif',name:'missing',association:'explicit',available:false}],uses:[{page_label:'1',element_id:'i'}]}]};
const imageHTML=imageResourcesHTML(ctx,resources);assert.match(imageHTML,/同名の原本候補/);assert.match(imageHTML,/型番との対応は未確認/);assert.match(imageHTML,/&lt;x&gt;/);assert.match(imageHTML,/p.png\?download=1/);assert.doesNotMatch(imageHTML,/missing.tif\?download/);
console.log('PASS: image provenance, downloadable preview, missing original and escaped names');
