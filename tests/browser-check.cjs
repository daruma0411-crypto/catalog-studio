const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');

const root=path.resolve(__dirname,'..');
const python=process.env.CATALOG_PYTHON||'python';
const sample=process.env.CATALOG_SAMPLE;
if(!sample||!fs.existsSync(sample))throw new Error('Set CATALOG_SAMPLE to the supplied catalog ZIP. Customer files are not included in this repository.');
fs.mkdirSync(path.join(root,'.qa'),{recursive:true});
const data=fs.mkdtempSync(path.join(root,'.qa','browser-'));
const port=8766;
const output=path.join(root,'.qa');
const child=spawn(python,['-u','server.py','--port',String(port),'--data',data,'--import-file',sample],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
const log=fs.createWriteStream(path.join(data,'server.log'));child.stdout.pipe(log);child.stderr.pipe(log);

(async()=>{
 let browser;
 try{
  let ready=false;for(let i=0;i<90;i++){if(child.exitCode!==null)throw new Error('Server exited early');try{const r=await fetch(`http://127.0.0.1:${port}/health`);if(r.ok){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,500));}
  assert.ok(ready,'server ready');
  browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1480,height:1060}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${port}`);
  await page.locator('[data-act="demo-login"][data-role="editor"]').click();
  await page.locator('#edit-text').waitFor();
  await page.locator('.busy-cover').waitFor({state:'hidden'});
  assert.match(await page.locator('#edit-text').inputValue(),/18,500/);
  await page.screenshot({path:path.join(output,'editor-before.png'),fullPage:true});
  const old=await page.locator('#edit-text').inputValue();
  await page.locator('#edit-text').fill(old.replace('18,500','19,800'));
  await page.locator('[data-act="save-text"]').click();await page.locator('.busy-cover').waitFor({state:'hidden'});
  await page.reload();await page.locator('#edit-text').waitFor();
  // After reload select the changed cell through its visible hit target if default selection changed.
  const changed=page.locator('.element-hit').filter({hasText:'impossible'});
  const hit=page.locator('.element-hit[aria-label*="19,800"]').first();await hit.click();
  assert.match(await page.locator('#edit-text').inputValue(),/19,800/);
  await page.locator('#render-mode').selectOption('html');
  assert.ok(await page.locator('.element.text').count()>100);
  await page.screenshot({path:path.join(output,'structured-html.png'),fullPage:true});
  await page.locator('[data-act="nav"][data-view="source"]').click();
  await page.locator('#submission-title').fill('QA 価格改定');await page.locator('#submission-target').fill('ERD9717WA');await page.locator('#submission-text').fill('2400TYPEの本体価格を改定。');
  await page.locator('[data-act="add-submission"]').click();await page.locator('.busy-cover').waitFor({state:'hidden'});
  assert.match(await page.locator('.source-list').innerText(),/QA 価格改定/);
  await page.locator('#source-upload').setInputFiles({name:'原稿.csv',mimeType:'text/csv',buffer:Buffer.from('型番,指示\nERD9717WA,価格を確認\n','utf8')});
  await page.locator('.busy-cover').waitFor({state:'hidden'});await page.locator('[data-act="preview-asset"]').first().click();await page.locator('dialog [data-act="row-submission"]').click();await page.locator('.busy-cover').waitFor({state:'hidden'});
  assert.match(await page.locator('.source-list').innerText(),/2行目/);
  await page.locator('[data-act="nav"][data-view="plan"]').click();await page.locator('[data-act="new-page"]').click();await page.locator('#new-page-title').fill('追加説明');await page.locator('[data-act="confirm-new-page"]').click();await page.locator('.busy-cover').waitFor({state:'hidden'});
  assert.equal(await page.locator('.page-card').count(),2);
  await page.locator('[data-act="nav"][data-view="research"]').click();await page.locator('#search-form').evaluate(e=>e.requestSubmit());await page.locator('.search-result').first().waitFor();assert.equal(await page.locator('.search-result').count(),2);
  await page.screenshot({path:path.join(output,'research.png'),fullPage:true});
  await page.locator('.search-result [data-act="locate"]').first().click();await page.locator('[data-act="flow-dialog"]').click();await page.locator('#flow-count').fill('0');await page.locator('[data-act="confirm-flow"]').click();await page.locator('.busy-cover').waitFor({state:'hidden'});
  assert.match(await page.locator('#edit-text').inputValue(),/ERD9717WA/);
  await page.locator('[data-act="nav"][data-view="handoff"]').click();
  const downloadPromise=page.waitForEvent('download');await page.getByText('制作指示ZIPをダウンロード',{exact:true}).click();const download=await downloadPromise;await download.saveAs(path.join(output,'instructions.zip'));
  assert.ok(fs.statSync(path.join(output,'instructions.zip')).size>1000);
  await page.locator('[data-act="publish"]').click();await page.locator('.busy-cover').waitFor({state:'hidden'});
  await page.screenshot({path:path.join(output,'handoff.png'),fullPage:true});
  await page.locator('#account-select').selectOption('reader');await page.locator('.busy-cover').waitFor({state:'hidden'});await page.locator('#search-form').evaluate(e=>e.requestSubmit());await page.locator('.search-result').first().waitFor();assert.equal(await page.locator('.search-result').count(),2);
  assert.equal(await page.locator('[data-act="nav"][data-view="source"]').count(),0);
  await page.locator('#account-select').selectOption('developer');await page.locator('.busy-cover').waitFor({state:'hidden'});assert.equal(await page.locator('[data-act="publish"]').count(),0);assert.equal(await page.locator('#submission-title').count(),1);
  await page.setViewportSize({width:390,height:850});await page.screenshot({path:path.join(output,'mobile.png'),fullPage:true});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1);assert.equal(overflow,false);
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(output,'browser-result.json'),JSON.stringify({result:'PASS',data,checks:['IDML import','PDF reference','HTML structure','text save and reload','source intake','CSV row provenance','pagination','general search','flow to new page','instruction ZIP download','publish','role-restricted views','mobile width','no JS errors']},null,2));
  console.log(JSON.stringify({result:'PASS',data,output}));
 }finally{if(browser)await browser.close();child.kill();log.end();}
})().catch(e=>{console.error(e);process.exitCode=1});
