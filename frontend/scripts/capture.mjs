import { spawn } from 'child_process';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(__dirname, '../..');
const SCREENSHOT_DIR = path.join(ROOT_DIR, 'docs', 'screenshots');
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const TEMP_PROFILE = path.join(ROOT_DIR, 'scratch', 'chrome_profile');
fs.mkdirSync(TEMP_PROFILE, { recursive: true });

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function main() {
  console.log('Launching Chrome...');
  const chrome = spawn(CHROME_PATH, [
    '--headless=new',
    '--remote-debugging-port=9222',
    `--user-data-dir=${TEMP_PROFILE}`,
    '--window-size=1600,1000',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    'about:blank'
  ]);

  let killed = false;
  const cleanup = () => {
    if (!killed) {
      killed = true;
      try { chrome.kill(); } catch (e) {}
    }
  };
  process.on('exit', cleanup);
  process.on('SIGINT', cleanup);

  try {
    await sleep(2500);

    const resp = await fetch('http://127.0.0.1:9222/json/new', { method: 'PUT' });
    const target = await resp.json();
    const ws = new WebSocket(target.webSocketDebuggerUrl);

    let id = 1;
    const pending = new Map();

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && pending.has(msg.id)) {
        const { resolve, reject } = pending.get(msg.id);
        pending.delete(msg.id);
        if (msg.error) reject(new Error(msg.error.message));
        else resolve(msg.result);
      }
    };

    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = reject;
    });

    const send = (method, params = {}) => {
      const callId = id++;
      return new Promise((resolve, reject) => {
        pending.set(callId, { resolve, reject });
        ws.send(JSON.stringify({ id: callId, method, params }));
      });
    };

    await send('Page.enable');
    await send('Runtime.enable');
    await send('Emulation.setDeviceMetricsOverride', {
      width: 1440,
      height: 900,
      deviceScaleFactor: 1.5,
      mobile: false
    });

    console.log('Navigating to http://localhost:3000...');
    await send('Page.navigate', { url: 'http://localhost:3000' });
    await sleep(3500);

    // Stage 1: Landing Workspace & Document Ingestion Setup
    console.log('Capturing Stage 1: 01-landing-workspace.png...');
    const shot1 = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(SCREENSHOT_DIR, '01-landing-workspace.png'), Buffer.from(shot1.data, 'base64'));

    // Stage 2: Load Sample Research Papers (kim25c.pdf & wen25g.pdf) & View Split-Screen Synthesis
    console.log('Loading Sample Research Papers from sample_docs/...');
    await send('Runtime.evaluate', {
      expression: 'window.__loadSamplePapers ? window.__loadSamplePapers() : null'
    });
    await sleep(2500);

    // Focus on Paper 1 (kim25c.pdf: OpenVLA monograph)
    await send('Runtime.evaluate', {
      expression: `(() => {
        const tab = Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.includes('kim25c.pdf'));
        if (tab) tab.click();
      })()`
    });
    await sleep(2000);

    console.log('Capturing Stage 2: 02-paper-synthesis.png...');
    const shot2 = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(SCREENSHOT_DIR, '02-paper-synthesis.png'), Buffer.from(shot2.data, 'base64'));

    console.log('Screenshots captured successfully (Stage 1 & Stage 2)!');
    ws.close();
  } finally {
    cleanup();
  }
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
