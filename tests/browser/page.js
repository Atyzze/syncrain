// Drive index.html in Chromium for the browser lane; prints one JSON line.
//   node page.js shot <png> <width> <height> <query>   a screenshot of the page
//   node page.js state <width> <height> <query>        a hash of the raw rain-cell grid
//   node page.js identity                              the build and stream the page says it is
//   node page.js cph                                   cycles per hour for 0.5 to 7200 s, in halves
//   node page.js controls                              the control strip at desk and phone sizes
//   node page.js configshot <png> <w> <h> <query> <json> a screenshot with that settings file loaded
//   node page.js symbols <json>...                     what the page drew its symbols from, with those files
//   node page.js logo <picture>                       a picture given as the logo: the settings it saves
//   node page.js studio                                the settings panel used as a person would, and saved
//   node page.js video <webm> <w> <h> <seconds> <fps> <loop> <t0>  a video made by the page's Save video
//   node page.js dropdowns                             the colours a dropdown's options are drawn in
'use strict';
const { chromium } = require('playwright');
const crypto = require('crypto');
const path = require('path');

const PAGE = 'file://' + path.resolve(__dirname, '..', '..', 'index.html');

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
  } else if (mode === 'cph') {
    const page = await open(320, 180, 'hud=0&fps=1');
    out.cph = await page.evaluate(n => Array.from({ length: n }, (_, i) => window.__syncrainCph((i + 1) / 2)), 14400);
  } else if (mode === 'identity') {
    const page = await open(800, 450, 'hud=0');
    out = await page.evaluate(() => Object.assign({}, window.__syncrainIdentity,
      { ident: document.getElementById('ident').textContent }));
  } else if (mode === 'video') {
    const [file, w, h, seconds, fps, loop, t0] = rest;
    const page = await open(640, 360, 'fps=1');
    const b64 = await page.evaluate(o => window.__syncrainVideo(o),
      { size: [Number(w), Number(h)], seconds: Number(seconds), fps: Number(fps), loop: loop === '1', t0: Number(t0) });
    require('fs').writeFileSync(file, Buffer.from(b64, 'base64'));
    out.bytes = Buffer.from(b64, 'base64').length;
  } else if (mode === 'dropdowns') {
    const page = await open(1280, 720, 'fps=1');
    await page.click('#open');
    // every list's options as the browser paints them when it opens: the chosen one, and the rest
    out.lists = await page.evaluate(() => Array.from(document.querySelectorAll('select')).map(sel => ({
      id: sel.id,
      options: Array.from(sel.options).map(o => {
        const cs = getComputedStyle(o);
        return { chosen: o.selected, disabled: o.disabled, background: cs.backgroundColor, color: cs.color };
      }),
    })));
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
  } else if (mode === 'configshot') {
    const [png, w, h, query, json] = rest;
    const page = await open(Number(w), Number(h), query + '&capture=1&scale=1&fps=1');
    out.loaded = await page.evaluate(text => window.__syncrainLoad(text), require('fs').readFileSync(json, 'utf8'));
    await page.evaluate(() => window.__syncrainSettled());
    const data = await page.evaluate(() => {
      window.__syncrainDraw(Number(new URLSearchParams(location.search).get('t')) * 1000);
      return document.getElementById('c').toDataURL('image/png');
    });
    require('fs').writeFileSync(png, Buffer.from(data.split(',')[1], 'base64'));
  } else if (mode === 'logo') {
    // a picture given as the logo, as a person picks one: what the settings file then holds
    const [picture] = rest;
    const page = await open(1280, 720, 'fps=1');
    await page.click('#open');
    await page.click('#logo button[data-v="picture"]').catch(() => {});
    await page.setInputFiles('#logo-file', picture);
    await page.waitForFunction(() => JSON.parse(window.__syncrainExport()).logo.startsWith('data:'), null, { timeout: 60000 });
    await page.evaluate(() => window.__syncrainSettled());
    out.exported = JSON.parse(await page.evaluate(() => window.__syncrainExport()));
  } else if (mode === 'symbols') {
    const page = await open(800, 450, 'hud=0&fps=1');
    for (const json of rest)                     // one after another, as a person opens them
      out.loaded = await page.evaluate(text => window.__syncrainLoad(text), require('fs').readFileSync(json, 'utf8'));
    out.symbols = await page.evaluate(() => window.__syncrainSymbols());
    out.exported = JSON.parse(await page.evaluate(() => window.__syncrainExport()));
  } else if (mode === 'studio') {
    for (const [name, w, h] of [['desk', 1440, 900], ['phone', 390, 844]]) {
      const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1, acceptDownloads: true });
      page.on('pageerror', e => errors.push('pageerror ' + e.message));
      page.on('console', m => { if (m.type() === 'error') errors.push('console ' + m.text()); });
      await page.route(/fonts\.(googleapis|gstatic)\.com/, r => r.fulfill({ status: 200, contentType: 'text/css', body: '' }));
      await page.goto(PAGE + '?fps=2', { waitUntil: 'domcontentloaded', timeout: 120000 });
      await page.waitForFunction(() => window.__syncrainReady === true, null, { timeout: 120000 });
      await page.mouse.move(w / 2, h / 2);
      await page.click('#open');
      await page.click('#presets-look button[data-v="matrix"]');
      await page.fill('#motion input[type="number"] >> nth=0', '1.5');
      await page.press('#motion input[type="number"] >> nth=0', 'Enter');
      await page.selectOption('#add-set', 'greek');
      await page.click('#add');
      await page.fill('#channel', 'friends');
      await page.waitForTimeout(400);
      const seen = await page.evaluate(() => {
        const r = e => e.getBoundingClientRect(), s = r(document.getElementById('studio')), c = r(document.getElementById('c'));
        const apart = s.top >= c.bottom - 1 || s.left >= c.right - 1;
        return { overflow: document.documentElement.scrollWidth > window.innerWidth, shown: !document.getElementById('studio').hidden,
                 inside: s.left >= 0 && s.right <= window.innerWidth + 0.5 && s.bottom <= window.innerHeight + 0.5, apart,
                 symbols: window.__syncrainSymbols() };
      });
      const [download] = await Promise.all([page.waitForEvent('download'), page.click('#save')]);
      seen.saved = require('fs').readFileSync(await download.path(), 'utf8');
      seen.filename = download.suggestedFilename();
      out[name] = seen;
      await page.close();
    }
  } else {
    throw new Error('unknown mode ' + mode);
  }
  out.errors = errors;
  console.log(JSON.stringify(out));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
