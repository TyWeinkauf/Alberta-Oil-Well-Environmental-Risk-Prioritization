// Run against the local app with the imported-water classroom package installed.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

async function main() {
  const url = new URL(process.env.APP_URL || 'http://127.0.0.1:8501');
  url.searchParams.set('dataset_mode', 'PostGIS workflows');
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium',
    headless: true,
    args: ['--no-sandbox'],
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1450, height: 1080 }, acceptDownloads: true });
    await page.route('**/*', (route) =>
      new URL(route.request().url()).origin === url.origin ? route.continue() : route.abort());
    await page.goto(url.href);
    await page.getByRole('heading', { name: /Red Deer.*classroom demo with imported waterways/ }).waitFor();
    const modes = page.getByRole('combobox', { name: 'Dataset mode' });
    await modes.click();
    await page.getByRole('option', { name: 'ST37 well inventory' }).waitFor();
    assert.deepEqual(await page.getByRole('option').allTextContents(), ['Classroom demo', 'ST37 well inventory']);
    await page.keyboard.press('Escape');
    await page.getByText('Both', { exact: true }).first().click();
    await page.getByRole('heading', { name: /Both.*classroom demo/ }).waitFor();

    const visible = page.getByTestId('stMetric').filter({ hasText: 'Visible wells' });
    const markerSelector = '.leaflet-marker-pane .leaflet-marker-icon[title]';
    async function mapWithWells(count) {
      await visible.getByText(String(count), { exact: true }).waitFor();
      const deadline = Date.now() + 15000;
      while (Date.now() < deadline) {
        for (const frame of page.frames()) {
          try {
            if (await frame.locator('.leaflet-overlay-pane path').count() &&
                await frame.locator(markerSelector).count() === count) return frame;
          } catch {
            // A filter change can replace the map iframe during a read.
          }
        }
        await new Promise((resolve) => setTimeout(resolve, 150));
      }
      throw new Error(`Map did not render ${count} well markers`);
    }
    async function buffer(distance, count) {
      await page.locator('.st-key-classroom_threshold').getByText(`${distance} m`, { exact: true }).click();
      return mapWithWells(count);
    }

    await mapWithWells(9);
    await buffer(50, 0);
    const map = await buffer(100, 1);
    await map.locator(markerSelector).click();
    await page.getByText(/100 m buffer around selected well/).waitFor();
    await buffer(250, 5);
    await page.getByText(/250 m buffer around selected well/).waitFor();
    const [download] = await Promise.all([
      page.waitForEvent('download'), page.getByRole('button', { name: 'Download GeoJSON' }).click(),
    ]);
    const chunks = [];
    for await (const chunk of await download.createReadStream()) chunks.push(chunk);
    const geojson = JSON.parse(Buffer.concat(chunks));
    assert.equal(geojson.selection.threshold_m, 250);
    assert.equal(geojson.features.length, 5);
    assert.ok(geojson.features.every((feature) => feature.properties.matches_threshold === true));
    await buffer(500, 9);
    await page.getByText('Only show wells within the buffer', { exact: true }).click();
    await mapWithWells(56);
    assert.equal(await page.getByTestId('stException').count(), 0);
    console.log('Verified the two app modes, offline classroom buffers and GeoJSON parity.');
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
