// Requires a locally running app plus managed Playwright/Chromium.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const os=require('node:os');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1200},acceptDownloads:true});
  await context.route('**/*',route=>{
   const u=new URL(route.request().url());return ['127.0.0.1','localhost'].includes(u.hostname)||!['http:','https:'].includes(u.protocol)?route.continue():route.abort();
  });
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.env.APP_URL||'http://127.0.0.1:8501');
  await page.getByRole('heading',{name:'Alberta well screening',exact:true}).waitFor();
  await page.getByText('Production',{exact:true}).click();
  await page.getByRole('button',{name:'Load synthetic production demo',exact:true}).click();
  await page.getByText('Production ready',{exact:true}).waitFor();
  const frame=page.frameLocator('iframe').first();
  await frame.getByTitle('DEMO-WELL-001',{exact:true}).click();
  await page.getByText('Synthetic production demonstration — these observations are not Petrinex data.',{exact:true}).waitFor();
  await page.getByText('Latest reported month: 2026-09 · unit: m3 · exact, uniquely verified source identifiers',{exact:true}).waitFor();
  await page.locator('[data-testid="stVegaLiteChart"]').locator('canvas,svg').first().waitFor();
  await page.getByRole('combobox',{name:'Production series',exact:true}).focus();
  await page.getByRole('combobox',{name:'Production series',exact:true}).press('ArrowDown');
  await page.getByRole('option').first().waitFor();
  await page.getByRole('option',{name:'OIL · ADJUSTMENT (m3)',exact:true}).click();
  await page.getByText('Latest reported month: 2026-10 · unit: m3 · exact, uniquely verified source identifiers',{exact:true}).waitFor();
  await frame.getByTitle('DEMO-WELL-002',{exact:true}).click();
  await page.getByText('Well-level production not available/verified. No facility volumes have been allocated to this well.',{exact:true}).waitFor();
  assert.equal(await page.locator('[data-testid="stVegaLiteChart"]').count(),0);
  await page.getByRole('tab',{name:'Data quality',exact:true}).click();
  const pending=page.waitForEvent('download');
  await page.getByRole('button',{name:'Download production audit',exact:true}).click();
  const download=await pending;const directory=await fs.mkdtemp(path.join(os.tmpdir(),'alberta-production-ui-'));
  const output=path.join(directory,'production_audit.json');await download.saveAs(output);
  const audit=JSON.parse(await fs.readFile(output,'utf8'));
  assert.equal(audit.batch.source_mode,'synthetic');
  assert.equal(audit.batch.validation.accepted,6);assert.equal(audit.quarantine.length,2);
  assert.equal(audit.audit.filter(r=>r.link_status==='verified').length,3);
  assert.equal(audit.audit.find(r=>r.link_status==='facility').volume,'900.00');
  assert.deepEqual(errors,[]);
  console.log('Production browser smoke passed: explicit synthetic import, verified monthly chart, separate adjustment series, unavailable other well and audited facility/unmatched/quarantined records.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
