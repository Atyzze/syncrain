// Drive web/index.html in Chromium for the browser lane; prints one JSON line.
//   node page.js shot <png> <width> <height> <query>   a screenshot of the page
//   node page.js state <width> <height> <query>        a hash of the raw rain-cell grid
//   node page.js identity                              the build and stream the page says it is
//   node page.js controls                              the control strip at desk and phone sizes
'use strict';
const { chromium } = require('playwright');
const crypto = require('crypto');
const path = require('path');

const PAGE = 'file://' + path.resolve(__dirname, '..', '..', 'web', 'index.html');

(async () => {
  const [mode, ...rest] = process.argv.slice(2);
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const errors = [];
  const open = async (w, h, query) => {
    const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
    page.on('pageerror', e => errors.push('pageerror ' + e.message));
    page.on('console', m => { if (m.type() === 'error') errors.push('console ' + m.text()); });
    // the page's web fonts are decoration; a sandbox cannot fetch them and must not wait for them
    await page.route(/fonts\.(googleapis|gstatic)\.com/, r => r.fulfill({ status: 200, contentType: 'text/css', body: '' }));
    await page.goto(PAGE + (query ? '?' + query : ''), { waitUntil: 'domcontentloaded', timeout: 120000 });
    await page.waitForFunction(() => window.__syncrainReady === true, null, { timeout: 120000 });
    return page;
  };
  let out = {};
  if (mode === 'shot') {
    // the canvas itself, drawn at the page's frozen moment (capture=1 keeps its drawing buffer)
    const [png, w, h, query] = rest;
    const page = await open(Number(w), Number(h), query + '&capture=1&scale=1&fps=1');
    const data = await page.evaluate(() => {
      window.__syncrainDraw(Number(new URLSearchParams(location.search).get('t')) * 1000);
      return document.getElementById('c').toDataURL('image/png');
    });
    require('fs').writeFileSync(png, Buffer.from(data.split(',')[1], 'base64'));
  } else if (mode === 'state') {
    const [w, h, query] = rest;
    const page = await open(Number(w), Number(h), query);
    const s = await page.evaluate(() => window.__syncrainState());
    out = { cols: s.cols, rows: s.rows, hash: crypto.createHash('sha256').update(Buffer.from(s.data)).digest('hex') };
  } else if (mode === 'identity') {
    const page = await open(800, 450, 'hud=0');
    out = await page.evaluate(() => Object.assign({}, window.__syncrainIdentity,
      { ident: document.getElementById('ident').textContent }));
  } else if (mode === 'controls') {
    for (const [name, w, h] of [['desk', 1440, 900], ['phone', 390, 844]]) {
      const page = await open(w, h, 'fps=2');
      await page.mouse.move(w / 2, h / 2);
      await page.waitForTimeout(800);
      out[name] = await page.evaluate(() => ({
        overflow: document.documentElement.scrollWidth > window.innerWidth,
        shown: !document.getElementById('panel').hidden,
      }));
      await page.close();       // a software-rendered page left running slows the next one to a crawl
    }
  } else {
    throw new Error('unknown mode ' + mode);
  }
  out.errors = errors;
  console.log(JSON.stringify(out));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
