const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });

  const variants = [
    { name: '001-line-green', url: 'http://localhost:8765/sketches/001-line-green/index.html' },
    { name: '002-premium-dark', url: 'http://localhost:8765/sketches/002-premium-dark/index.html' }
  ];

  for (const v of variants) {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
    await page.goto(v.url, { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(500);
    await page.screenshot({ path: `/home/alan/line-broadcast/sketches/${v.name}.png`, fullPage: true });
    console.log(`✅ ${v.name}.png`);
    await page.close();
  }

  await browser.close();
  console.log('🎉 Done');
})();
