// Fixed artificial fixture only. Never point this test at real statements.
const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const fs=require('node:fs/promises');
const path=require('node:path');
const {chromium}=require('/Users/cip/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

(async()=>{
  const root=path.resolve(__dirname,'..'),state=await fs.mkdtemp(path.join(root,'tmp','multiline-ui-'));
  const server=spawn('sh',['tools/pdf-toolkit','preview','tmp/multiline-input','--state-dir',state],{cwd:root,stdio:['ignore','pipe','pipe']});
  let browser;
  try{
    const url=await new Promise((resolve,reject)=>{let text='';const timeout=setTimeout(()=>reject(new Error('Artificial server timeout')),10000);server.stdout.on('data',chunk=>{text+=chunk;if(text.includes('\n')){clearTimeout(timeout);resolve(JSON.parse(text.split('\n')[0]).preview_url);}});server.on('exit',()=>{clearTimeout(timeout);reject(new Error('Artificial server exited'));});});
    browser=await chromium.launch({headless:true,channel:'chrome'});
    const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],external=[];
    page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(new URL(r.url()).origin!==new URL(url).origin)external.push(r.url());});
    await page.goto(url);await page.waitForFunction(()=>document.querySelectorAll('.token').length>0&&!document.body.classList.contains('busy'));
    const word=text=>page.locator('.token').filter({hasText:new RegExp('^'+text.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'\\s*$')}).first();
    // Native multi-line selection crosses a distant printed heading. Assigning
    // names must keep the two name lines separate and exclude other columns.
    await page.evaluate(()=>{const words=[...document.querySelectorAll('.token')],first=words.find(w=>w.textContent.trim()==='Erika'),last=words.find(w=>w.textContent.trim()==='Muster');const range=document.createRange();range.setStart(first.firstChild,0);range.setEnd(last.firstChild,last.textContent.trim().length);const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);document.querySelector('#text-layer').dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));});
    await page.locator('#field').selectOption('owner.name');await page.locator('#add-example').click();
    assert.equal(await page.locator('#owners div').count(),2);
    assert.equal(await page.locator('#owners div span').first().textContent(),'Erika Beispiel');
    assert.equal(await page.locator('#owners div span').last().textContent(),'Alex Muster');
    assert.equal(await page.locator('#field option[value="transaction.recipient"]').count(),0);
    await word('Betrag').click();await page.locator('#field').selectOption('transaction.amount');await page.locator('#add-example').click();
    assert.match(await page.locator('#status').textContent(),/kein passender Feldwert/);
    assert.match(await page.locator('#summary').textContent(),/2 Beispiele/);
    await word('POS').click();await page.locator('#whole-booking').click();
    await page.waitForFunction(()=>document.querySelector('#selection-preview').textContent.includes('12,34-'));
    assert.equal(await page.locator('#field').inputValue(),'transaction.row');
    assert.ok(!(await page.locator('#selection-preview').textContent()).includes('Lastschrift'));
    await page.locator('#add-example').click();
    await word('04.10').click();await page.locator('#field').selectOption('transaction.booking_date');await page.locator('#add-example').click();
    await word('12,34-').click();await page.locator('#field').selectOption('transaction.amount');await page.locator('#add-example').click();
    // These two fields are examples before their booking row exists.
    await word('25,00-').click();await page.locator('#field').selectOption('transaction.amount');await page.locator('#add-example').click();
    await page.locator('.token').filter({hasText:/^04\.10\s*$/}).last().click();await page.locator('#field').selectOption('transaction.value_date');await page.locator('#add-example').click();
    // An already saved example at a page boundary must still carry forward.
    await word('06.10').click();await page.locator('#whole-booking').click();
    await page.waitForFunction(()=>document.querySelector('#field').value==='transaction.row');
    await page.locator('#add-example').click();
    await page.locator('#scope').selectOption('all');await page.locator('#recognize').click();
    await page.waitForFunction(()=>!document.querySelector('#recognize').disabled,{},{timeout:30000});
    assert.match(await page.locator('#summary').textContent(),/5 Buchungen/);
    assert.equal(await page.locator('#rows-body tr').count(),4);
    const debit=page.locator('#rows-body tr').filter({hasText:'MUSTER?STROM?AG'});
    assert.equal(await debit.count(),1);assert.match(await debit.textContent(),/Mandatsref/);assert.match(await debit.textContent(),/25,00-/);
    assert.equal(await debit.locator('td').nth(2).textContent(),'04.10');
    assert.match(await page.locator('#rows-body').textContent(),/Weiter auf Seite 2/);
    const rotated=await page.locator('.token').evaluateAll(words=>words.filter(w=>w.textContent.includes('STAMP-VERTIKAL')).map(w=>w.style.transform));
    assert.equal(rotated.length,1);assert.ok(rotated[0].includes('270deg'));
    await page.locator('#save').click();await page.waitForFunction(()=>document.querySelector('#dirty').textContent==='Gespeichert');
    await page.locator('#next').click();await page.waitForFunction(()=>!document.body.classList.contains('busy'));
    assert.match(await page.locator('#rows-body').textContent(),/Fortsetzung/);assert.match(await page.locator('#rows-body').textContent(),/18,00-/);
    const lastBooking=page.locator('#rows-body tr').filter({hasText:'LETZTER MUSTERLADEN'});
    assert.equal(await lastBooking.locator('td').nth(4).textContent(),'7,50-');
    assert.ok(!(await page.locator('#rows-body').textContent()).includes('876,54'));
    // Simulate the older saved state, with values present but no parent link.
    const brokenFile=(await fs.readdir(state)).find(name=>name.startsWith('field-workspace-'));
    const broken=JSON.parse(await fs.readFile(path.join(state,brokenFile),'utf8'));
    for(const annotation of broken.documents[0].annotations)if(annotation.kind==='example'&&['transaction.amount','transaction.value_date'].includes(annotation.field)&&annotation.row_id){const parent=broken.documents[0].annotations.find(row=>row.id===annotation.row_id);if(parent?.kind==='suggestion')annotation.row_id=null;}
    await fs.writeFile(path.join(state,brokenFile),JSON.stringify(broken));
    await page.reload();await page.waitForFunction(()=>document.querySelectorAll('.token').length>0&&!document.body.classList.contains('busy'));
    assert.equal(await page.locator('#owners div').count(),2);
    const repairedRow=page.locator('#rows-body tr').filter({hasText:'MUSTER?STROM?AG'});
    assert.equal(await repairedRow.locator('td').nth(2).textContent(),'04.10');
    assert.equal(await repairedRow.locator('td').nth(4).textContent(),'25,00-');
    assert.match(await page.locator('#status').textContent(),/wieder mit ihren Buchungen verknüpft/);
    await page.locator('#save').click();await page.waitForFunction(()=>document.querySelector('#dirty').textContent==='Gespeichert');
    // Only artificial saved state is edited here. Legacy predictions must be
    // clearly marked instead of being mistaken for new recognition results.
    const stateFile=(await fs.readdir(state)).find(name=>name.startsWith('field-workspace-'));
    const legacy=JSON.parse(await fs.readFile(path.join(state,stateFile),'utf8'));
    const obsolete=legacy.documents[0].annotations.find(a=>a.kind==='suggestion'&&a.field==='transaction.row');
    delete obsolete.recognition_revision;
    await fs.writeFile(path.join(state,stateFile),JSON.stringify(legacy));
    await page.reload();await page.waitForFunction(()=>document.querySelectorAll('.token').length>0&&!document.body.classList.contains('busy'));
    assert.match(await page.locator('#revision-message').textContent(),/1 alte Vorschläge/);
    await page.locator('#refresh-suggestions').click();
    await page.waitForFunction(()=>!document.querySelector('#recognize').disabled,{},{timeout:30000});
    assert.ok(await page.locator('#revision-notice').isHidden());
    assert.match(await page.locator('#summary').textContent(),/5 Buchungen/);
    await page.locator('#save').click();await page.waitForFunction(()=>document.querySelector('#dirty').textContent==='Gespeichert');
    await fs.mkdir(path.join(root,'output','ui-check'),{recursive:true});
    await page.locator('#filter').selectOption('transaction.row');
    await page.screenshot({path:path.join(root,'output','ui-check','multiline-desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(root,'output','ui-check','multiline-mobile.png'),fullPage:true});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    const profile=JSON.parse(await fs.readFile(path.join(state,'field-profile.json'),'utf8'));
    assert.equal(profile.engine,'layout-examples-v2');assert.ok(!JSON.stringify(profile).includes('Erika'));assert.ok(!JSON.stringify(profile).includes('MUSTER?STROM'));
    const filename=(await fs.readdir(state)).find(name=>name.startsWith('field-workspace-'));
    const workspace=JSON.parse(await fs.readFile(path.join(state,filename),'utf8'));
    assert.equal(new Set(workspace.documents[0].annotations.filter(a=>a.field==='owner.name').map(a=>a.entity_id)).size,2);
    assert.ok(workspace.documents[0].annotations.some(a=>a.continuation_of));
    assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
    console.log(JSON.stringify({multiline_browser_checks:'passed',owners:2,bookings:5,variable_line_count:true,full_text_preserved:true,page_continuation:true,caption_rejected:true,external_requests:0,stale_predictions_regenerated:true,confirmed_continuation:true,orphan_values_relinked:true,closing_balance_excluded:true,artificial_inputs_only:true}));
  }finally{if(browser)await browser.close();server.kill('SIGTERM');}
})().catch(error=>{console.error(error);process.exitCode=1;});
