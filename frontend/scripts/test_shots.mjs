import fs from 'fs';
import path from 'path';

const SCREENSHOT_DIR = path.resolve('docs/screenshots');

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function test() {
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

  await new Promise((r, e) => { ws.onopen = r; ws.onerror = e; });
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

  await send('Page.navigate', { url: 'http://localhost:3000' });
  await sleep(2500);

  // Click load demo papers
  await send('Runtime.evaluate', {
    expression: 'document.getElementById("load-demo-papers-btn")?.click()'
  });
  await sleep(1500);

  // Click cross question pill to generate a multi-turn conversation
  await send('Runtime.evaluate', {
    expression: `(() => {
      const pill = Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.includes('Compare the computational'));
      if (pill) pill.click();
    })()`
  });
  await sleep(2000);

  // Capture conversation in split view WITHOUT modal blocking
  console.log('Capturing split view with active multi-turn conversation...');
  const shotA = await send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(path.join(SCREENSHOT_DIR, '03-chat-interrogation-split.png'), Buffer.from(shotA.data, 'base64'));

  // Switch to ChatGPT Mode to see full-width chat conversation
  await send('Runtime.evaluate', {
    expression: `(() => {
      const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'ChatGPT Mode');
      if (btn) btn.click();
    })()`
  });
  await sleep(1500);

  console.log('Capturing ChatGPT mode full-width conversation...');
  const shotB = await send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(path.join(SCREENSHOT_DIR, '03-chat-interrogation-full.png'), Buffer.from(shotB.data, 'base64'));

  ws.close();
  console.log('Test screenshots saved successfully!');
}

test().catch(console.error);
