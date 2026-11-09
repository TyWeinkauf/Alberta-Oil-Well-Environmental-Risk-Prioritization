// Run against the locally started app: node tests/browser/ui_smoke.cjs
// Requires Playwright and Chromium (provided in the managed cloud environment).
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const os=require('node:os');

(async()=>{
 let debugPage;
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1150},acceptDownloads:true});
  const errors=[];
  context.on('page',p=>p.on('pageerror',e=>errors.push(e.message)));
  // This test deliberately proves offline geometry/click/export functionality.
  await context.route('**/*',route=>{
   const url=new URL(route.request().url());
   return ['127.0.0.1','localhost'].includes(url.hostname)||!['http:','https:'].includes(url.protocol)?route.continue():route.abort();
  });
  const page=await context.newPage();debugPage=page;
  await page.goto(process.env.APP_URL||'http://127.0.0.1:8501');
  const frame=page.frameLocator('iframe').first();
  async function until(check,label){
   const limit=Date.now()+15000;
   while(Date.now()<limit){if(await check())return;await new Promise(resolve=>setTimeout(resolve,100));}
   throw new Error(`Timed out: ${label}`);
  }
  async function markers(n){await until(async()=>await frame.locator('.leaflet-marker-icon').count()===n,`${n} map markers`);}
  async function metric(name,value){
   const block=page.locator('[data-testid="stMetric"]').filter({has:page.getByText(name,{exact:true})});
   await until(async()=>await block.locator('[data-testid="stMetricValue"]').innerText()===String(value),`${name}=${value}`);
  }
  async function choose(label,option){
   await page.getByRole('combobox',{name:label,exact:true}).click();
   await page.getByRole('option',{name:option,exact:true}).click();
   await page.keyboard.press('Escape');
  }
  await markers(2);
  assert.equal(await page.getByRole('button',{name:'Refresh production',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'Load synthetic production demo',exact:true}).count(),0);
  await page.getByRole('button',{name:'Use demo dataset',exact:true}).click();
  await page.getByText('Demo ready',{exact:true}).waitFor();
  await markers(2);
  await frame.getByTitle('DEMO-WELL-001',{exact:true}).click();
  await page.getByText('Licensee: Synthetic Company A',{exact:true}).waitFor();
  await frame.getByTitle('DEMO-WELL-002',{exact:true}).click();
  await page.getByText('Licensee: Synthetic Company B',{exact:true}).waitFor();
  await choose('Distance threshold (m)','50');
  await metric('Within threshold',1);
  await page.getByText('Only wells within threshold',{exact:true}).click();
  await metric('Visible wells',1);
  await markers(1);
  await page.getByText('Selected well is outside current filters. Clear the selection or change the filters.',{exact:true}).waitFor();
  await page.getByText('Only wells within threshold',{exact:true}).click();
  await markers(2);
  await page.getByText('Licensee: Synthetic Company B',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Clear filters',exact:true}).click();
  await metric('Within threshold',2);
  await choose('Company (licensee)','Synthetic Company B');
  await metric('Visible wells',1);
  await markers(1);
  await page.getByText('Licensee: Synthetic Company B',{exact:true}).waitFor();
  const directory=await fs.mkdtemp(path.join(os.tmpdir(),'alberta-ui-'));
  async function download(label,name){
   const pending=page.waitForEvent('download');
   await page.getByRole('button',{name:label,exact:true}).click();
   const artifact=await pending;const target=path.join(directory,name);
   await artifact.saveAs(target);return fs.readFile(target,'utf8');
  }
  const csv=(await download('Download CSV','selection.csv')).replace(/^\uFEFF/,'');
  const geo=JSON.parse(await download('Download GeoJSON','selection.geojson'));
  const manifest=JSON.parse(await download('Download selection manifest','manifest.json'));
  const html=await download('Download map HTML','map.html');
  assert.equal(geo.features.length,1);assert.equal(manifest.count,1);
  assert.equal(geo.features[0].properties.source_well_id,'DEMO-WELL-002');
  assert.equal(geo.features[0].properties.distance_m,150);
  assert(csv.includes('DEMO-WELL-002')&&!csv.includes('DEMO-WELL-001'));
  const lines=csv.trim().split(/\r?\n/);assert.equal(lines.length,2);
  const column=lines[0].split(',').indexOf('distance_m');assert.equal(Number(lines[1].split(',')[column]),150);
  assert.deepEqual(manifest.selection.companies,['Synthetic Company B']);
  const exported=await context.newPage();
  await exported.setContent(html,{waitUntil:'load'});
  await exported.getByTitle('DEMO-WELL-002',{exact:true}).waitFor();
  assert.equal(await exported.locator('.leaflet-marker-icon').count(),1);
  await exported.getByTitle('DEMO-WELL-002',{exact:true}).click();
  await exported.locator('.leaflet-popup-content').getByText('DEMO-WELL-002',{exact:true}).waitFor();
  await page.getByRole('tab',{name:'Data quality',exact:true}).click();
  await page.getByRole('heading',{name:'Quarantined records',exact:true}).waitFor();
  await page.getByRole('tab',{name:'Run history',exact:true}).click();
  await page.getByRole('heading',{name:'Workflow actions in this session',exact:true}).waitFor();
  assert.deepEqual(errors,[]);
  console.log('Browser smoke passed: offline startup/action, marker selection, persistence, filters/counts, CSV/GeoJSON/manifest parity, standalone HTML map, quality and history.');
  console.log('Temporary download evidence:',directory);
 }catch(error){if(debugPage){console.error('UI diagnostics:',(await debugPage.locator('body').innerText()).slice(-4000));await debugPage.screenshot({path:path.join(os.tmpdir(),'alberta-ui-failure.png'),fullPage:true});}throw error;}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
