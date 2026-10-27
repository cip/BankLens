// Fixed artificial fixtures only. Never point this test at real statements.
const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const fs=require('node:fs/promises');
const path=require('node:path');
const {chromium}=require('/Users/cip/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

(async()=>{
  const root=path.resolve(__dirname,'..'),temporary=await fs.mkdtemp(path.join(root,'tmp','proof-ui-'));
  const source=path.join(temporary,'source'),state=path.join(temporary,'state'),output=path.join(root,'output','ui-check');
  await fs.mkdir(source);await fs.mkdir(output,{recursive:true});
  for(const name of ['first.pdf','second.pdf'])await fs.copyFile(path.join(root,'tmp','multiline-input','example.pdf'),path.join(source,name));
  const server=spawn('sh',['tools/pdf-toolkit','preview',source,'--state-dir',state],{cwd:root,stdio:['ignore','pipe','pipe']});
  let browser;
  try{
    const url=await new Promise((resolve,reject)=>{let text='';const timeout=setTimeout(()=>reject(new Error('Artificial server timeout')),10000);server.stdout.on('data',chunk=>{text+=chunk;if(text.includes('\n')){clearTimeout(timeout);resolve(JSON.parse(text.split('\n')[0]).preview_url);}});server.on('exit',()=>{clearTimeout(timeout);reject(new Error('Artificial server exited'));});});
    browser=await chromium.launch({headless:true,channel:'chrome'});
    const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],external=[];
    page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(new URL(r.url()).origin!==new URL(url).origin)external.push(r.url());});
    await page.goto(url+'proof.html');await page.waitForFunction(()=>!document.querySelector('#index').disabled);
    await page.locator('#index').click();
    await page.waitForFunction(()=>document.querySelectorAll('#result-rows tr').length===10,{},{timeout:30000});
    assert.match(await page.locator('#index-status').textContent(),/10 Buchungen aus 4 Seiten/);
    const query=async value=>{await page.locator('#query').fill(value);await page.locator('#search').click();await page.waitForFunction(()=>document.querySelectorAll('#result-rows tr').length===2);};
    await query('MUSTER?ENERGIE 18,00');
    assert.match(await page.locator('#result-rows tr').first().textContent(),/REF-EXAMPLE-002/);
    assert.match(await page.locator('#selection-count').textContent(),/2 Buchungen auf 4 Seiten/);
    assert.match(await page.locator('#result-rows tr').first().textContent(),/Mehrseitig/);
    await page.locator('#result-rows input').last().uncheck();
    assert.match(await page.locator('#selection-count').textContent(),/1 Buchung auf 2 Seiten/);
    await page.locator('#preview').click();await page.locator('#preview-image').waitFor({state:'visible'});
    await page.waitForFunction(()=>document.querySelector('#preview-image').complete&&document.querySelector('#preview-image').naturalWidth>0);
    await page.locator('#preview-page').selectOption('document-001/2');
    await page.waitForFunction(()=>document.querySelector('#preview-hint').textContent.startsWith('Sichtbar bleiben'));
    await page.locator('#export').click();await page.locator('#downloads a').first().waitFor({timeout:30000});
    assert.equal(await page.locator('#downloads a').count(),1);
    let pending=page.waitForEvent('download');await page.locator('#downloads a').first().click();let download=await pending;
    await download.saveAs(path.join(output,'proof-download.pdf'));
    assert.equal((await fs.readFile(path.join(output,'proof-download.pdf'))).subarray(0,4).toString(),'%PDF');
    await page.screenshot({path:path.join(output,'proof-desktop.png'),fullPage:true});
    // Searching a signed amount matches the same complete, cross-page rows.
    await query('-18,00');await page.waitForFunction(()=>document.querySelector('#select-all').checked);
    assert.equal(await page.locator('#downloads a').count(),0);
    await page.locator('#export').click();await page.locator('#downloads a').nth(2).waitFor({timeout:30000});
    assert.equal(await page.locator('#downloads a').count(),3);
    pending=page.waitForEvent('download');await page.locator('#downloads a').last().click();download=await pending;
    await download.saveAs(path.join(output,'proof-download.zip'));
    assert.equal((await fs.readFile(path.join(output,'proof-download.zip'))).subarray(0,2).toString(),'PK');
    await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(output,'proof-mobile.png'),fullPage:true});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.getByRole('link',{name:'Feldwerkstatt',exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll('.token').length>0&&!document.body.classList.contains('busy'));
    await page.getByRole('link',{name:'Zahlungsnachweise',exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll('#result-rows tr').length===10);
    assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
    console.log(JSON.stringify({proof_browser_checks:'passed',artificial_documents:2,logical_bookings:10,cross_page_search:true,selection:true,sanitized_preview:true,pdf_download:true,zip_download:true,mode_switch:true,external_requests:0,artificial_inputs_only:true}));
  }finally{if(browser)await browser.close();server.kill('SIGTERM');await new Promise(resolve=>server.once('close',resolve));await fs.rm(temporary,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1;});
