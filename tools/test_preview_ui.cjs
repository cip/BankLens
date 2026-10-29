// Only the artificial tools/create_demo_pdf.py input may be opened here.
const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const fs=require('node:fs/promises');
const path=require('node:path');
const {chromium}=require(process.env.BANKLENS_PLAYWRIGHT_PATH||'playwright');

(async()=>{
  const root=path.resolve(__dirname,'..');
  const state=await fs.mkdtemp(path.join(root,'tmp','fields-ui-'));
  const server=spawn('sh',['tools/pdf-toolkit','preview','tmp/demo-input','--state-dir',state],{cwd:root,stdio:['ignore','pipe','pipe']});
  let browser;
  try{
    const url=await new Promise((resolve,reject)=>{let data='';const timeout=setTimeout(()=>reject(new Error('Demo startup timeout')),10000);server.stdout.on('data',chunk=>{data+=chunk;if(data.includes('\n')){clearTimeout(timeout);try{resolve(JSON.parse(data.split('\n')[0]).preview_url);}catch{reject(new Error('Invalid demo startup'));}}});server.on('exit',()=>{clearTimeout(timeout);reject(new Error('Demo exited early'));});});
    browser=await chromium.launch({headless:true,channel:'chrome'});
    const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[],external=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(new URL(r.url()).origin!==new URL(url).origin)external.push(r.url());});
    const loaded=()=>page.waitForFunction(()=>!document.body.classList.contains('busy')&&document.querySelectorAll('.token').length>0);
    await page.goto(url);await loaded();
    await page.waitForFunction(()=>!document.querySelector('#profile-select').disabled);
    assert.equal(await page.locator('#profile-select').inputValue(),'bundled:bank-austria:1');
    assert.equal(await page.locator('#profile-select option[value="examples"]').textContent(),'Eigene Beispiele aus diesem Arbeitsstand');
    assert.equal(await page.locator('#profile-select option[value="bundled:bank-austria:1"]').textContent(),'Bank Austria · Mitgeliefertes Profil · Revision 1');
    assert.match(await page.locator('#profile-status').textContent(),/Bank Austria.*Mitgeliefertes Profil.*Revision 1/);
    const word=text=>page.locator('.token').filter({hasText:new RegExp('^'+text.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'\\s*$')}).first();
    async function example(text,field,whole=false){await word(text).click();if(whole)await page.locator('#whole-line').click();await page.locator('#field').selectOption(field);await page.locator('#add-example').click();}
    // A real mouse drag creates a native browser text selection. Word snapping
    // must include complete words and exclude the following address line.
    const first=await word('Erika').boundingBox(),last=await word('Beispiel').boundingBox();
    await page.mouse.move(first.x+first.width*.15,first.y+first.height*.5);await page.mouse.down();
    await page.mouse.move(last.x+last.width*.8,last.y+last.height*.5,{steps:12});await page.mouse.up();
    await page.waitForFunction(()=>document.querySelector('#selection-preview').textContent==='Erika Beispiel');
    assert.ok(await page.evaluate(()=>window.getSelection().toString().trim().length>0));
    await page.locator('#field').selectOption('owner.name');await page.locator('#add-example').click();
    await example('01.01.2026','transaction.row',true);
    await example('01.01.2026','transaction.booking_date');
    await example('MUSTERGEHALT','transaction.full_text');
    await example('2.000,00','transaction.amount');
    assert.match(await page.locator('#summary').textContent(),/5 Beispiele/);
    await page.locator('#save').click();await page.waitForFunction(()=>document.querySelector('#dirty').textContent==='Gespeichert');
    await page.locator('#scope').selectOption('all');await page.locator('#recognize').click();
    await page.waitForFunction(()=>!document.querySelector('#recognize').disabled,{},{timeout:30000});
    assert.match(await page.locator('#summary').textContent(),/6 Buchungen/);
    assert.equal(await page.locator('#rows-body tr').count(),3);
    assert.match(await page.locator('#rows-body').textContent(),/MUSTERMIETE/);
    assert.match(await page.locator('#rows-body').textContent(),/-700,00/);
    await page.locator('#accept-page').click();
    assert.ok(await page.locator('#accept-page').isDisabled());
    await page.locator('#undo').click();assert.ok(await page.locator('#accept-page').isEnabled());
    await page.locator('#accept-page').click();
    await page.locator('#next-suggestion').click();await loaded();
    assert.equal(await page.locator('#page').inputValue(),'2');
    assert.equal(await page.locator('#rows-body tr').count(),3);
    await page.locator('#filter').selectOption('transaction.full_text');
    const recipient=page.locator('#annotations li').filter({hasText:'Buchung · Gesamter Buchungstext'}).first();
    await recipient.getByRole('button',{name:'Verwerfen',exact:true}).click();
    await page.locator('#save').click();await page.waitForFunction(()=>document.querySelector('#dirty').textContent==='Gespeichert');
    await page.reload();await loaded();
    assert.match(await page.locator('#summary').textContent(),/5 Beispiele/);
    assert.ok(await page.locator('#apply-profile').isEnabled());
    const catalog=await page.evaluate(()=>fetch('api/profiles').then(r=>r.json()));
    const [origin,id,rev]=catalog.selected_profile.split(':');
    assert.equal(origin,'local');
    const profile=JSON.parse(await fs.readFile(path.join(state,'profiles',id,rev+'.json'),'utf8')).profile;
    assert.ok(profile.anchors.length>0);
    assert.ok(!JSON.stringify(profile).includes('Erika'));
    assert.ok(!JSON.stringify(profile).includes('MUSTERGEHALT'));
    await page.locator('#filter').selectOption('transaction.booking_date');
    await fs.mkdir(path.join(root,'output','ui-check'),{recursive:true});
    await page.screenshot({path:path.join(root,'output','ui-check','fields-desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(root,'output','ui-check','fields-mobile.png'),fullPage:true});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile overflow');
    // Switching creates a new session, preserving the previous tab's identity.
    await page.locator('#profile-select').selectOption('bundled:bank-austria:1');
    const oldUrl=page.url();
    await page.locator('#profile-switch').click();
    await page.waitForURL(current=>current.href!==oldUrl);await loaded();
    await page.waitForFunction(()=>!document.querySelector('#profile-select').disabled);
    assert.equal(await page.locator('#profile-select').inputValue(),'bundled:bank-austria:1');
    const oldTab=await browser.newPage();await oldTab.goto(oldUrl);
    await oldTab.waitForFunction(()=>!document.querySelector('#profile-select').disabled);
    assert.equal(await oldTab.locator('#profile-select').inputValue(),catalog.selected_profile);
    await oldTab.close();
    await page.locator('#profile-select').selectOption('examples');
    const bundledUrl=page.url();
    await page.locator('#profile-switch').click();
    await page.waitForURL(current=>current.href!==bundledUrl);await loaded();
    await page.waitForFunction(()=>!document.querySelector('#profile-select').disabled);
    assert.equal(await page.locator('#profile-select').inputValue(),'examples');
    assert.match(await page.locator('#profile-status').textContent(),/Verwendet: Eigene Beispiele aus diesem Arbeitsstand/);
    assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
    console.log(JSON.stringify({browser_checks:'passed',native_text_selection:true,examples:5,recognized_rows:6,save_reload_undo_rejection:true,external_requests:0,page_errors:0,artificial_inputs_only:true}));
  }finally{if(browser)await browser.close();server.kill('SIGTERM');}
})().catch(error=>{console.error(error);process.exitCode=1;});
