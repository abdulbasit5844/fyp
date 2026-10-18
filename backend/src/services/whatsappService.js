const fs = require('fs');
const QRCode = require('qrcode');
const config = require('../config');

// WhatsApp escalation messages through a linked WhatsApp account (the same
// mechanism as WhatsApp Web, via the Baileys library). The owner links it once
// by scanning a QR code in the app; the session is kept in config.whatsapp.authDir
// so the Pi reconnects on its own after a restart.

const LINK_WINDOW_MS = 3 * 60 * 1000; // how long to keep offering QR codes
const silent = {
  level: 'silent', trace() {}, debug() {}, info() {}, warn() {}, error() {}, fatal() {},
  child() { return silent; },
};

const state = { status: 'disconnected', qr: null, phone: null, error: null };
let sock = null;
let starting = null;
let linkUntil = 0;
let testSender = null;

const hasSession = () => fs.existsSync(`${config.whatsapp.authDir}/creds.json`);

function clearSession() {
  fs.rmSync(config.whatsapp.authDir, { recursive: true, force: true });
}

function getStatus() {
  return { ...state, enabled: config.whatsapp.enabled };
}

async function connect() {
  if (!config.whatsapp.enabled || sock) return;
  if (starting) { await starting; return; }
  starting = (async () => {
    const {
      default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestWaWebVersion, Browsers,
    } = await import('baileys');
    const { state: auth, saveCreds } = await useMultiFileAuthState(config.whatsapp.authDir);
    let version;
    try {
      ({ version } = await fetchLatestWaWebVersion());
    } catch { /* use the library default */ }

    Object.assign(state, { status: 'connecting', error: null });
    const s = makeWASocket({
      auth, version, logger: silent, browser: Browsers.ubuntu('Driver Monitor'),
      markOnlineOnConnect: false, syncFullHistory: false,
    });
    sock = s;
    s.ev.on('creds.update', saveCreds);
    s.ev.on('connection.update', async (u) => {
      if (u.qr) {
        state.status = 'qr';
        state.qr = await QRCode.toDataURL(u.qr, { margin: 1, width: 320 });
      }
      if (u.connection === 'open') {
        Object.assign(state, { status: 'connected', qr: null, error: null, phone: s.user?.id?.split(/[:@]/)[0] });
        console.log(`[whatsapp] linked as +${state.phone}`);
      }
      if (u.connection === 'close') {
        if (sock === s) sock = null;
        const code = u.lastDisconnect?.error?.output?.statusCode;
        if (code === DisconnectReason.loggedOut) {
          clearSession();
          Object.assign(state, { status: 'disconnected', qr: null, phone: null, error: 'Unlinked from the phone' });
          console.log('[whatsapp] unlinked from the phone');
        } else if (!auth.creds.registered && Date.now() > linkUntil) {
          // QR offered but never scanned: stop instead of looping.
          clearSession();
          Object.assign(state, { status: 'disconnected', qr: null, error: 'QR code expired. Press Link again.' });
        } else {
          state.status = 'connecting';
          setTimeout(() => connect().catch(onError), code === DisconnectReason.restartRequired ? 0 : 3000);
        }
      }
    });
  })().finally(() => { starting = null; });
  await starting;
}

function onError(e) {
  Object.assign(state, { status: 'disconnected', error: e.message });
  console.error('[whatsapp]', e.message);
}

// Reconnect a saved session when the server starts.
function init() {
  if (config.whatsapp.enabled && hasSession()) connect().catch(onError);
}

// Start linking: the app polls getStatus() for the QR code.
async function link() {
  if (!config.whatsapp.enabled) throw new Error('WhatsApp is disabled on this server');
  if (state.status === 'connected') return getStatus();
  linkUntil = Date.now() + LINK_WINDOW_MS;
  await connect();
  return getStatus();
}

async function unlink() {
  const s = sock;
  sock = null;
  if (s) await s.logout().catch(() => s.end?.());
  clearSession();
  Object.assign(state, { status: 'disconnected', qr: null, phone: null, error: null });
  return getStatus();
}

async function sendText(phone, text) {
  if (testSender) return testSender(phone, text);
  if (state.status !== 'connected' || !sock) {
    return { ok: false, error: 'WhatsApp not configured: link it in Settings → WhatsApp alerts' };
  }
  const digits = String(phone).replace(/\D/g, '');
  const [found] = (await sock.onWhatsApp(digits)) || [];
  if (!found?.exists) return { ok: false, error: `${phone} is not on WhatsApp` };
  const msg = await sock.sendMessage(found.jid, { text });
  return { ok: true, id: msg?.key?.id };
}

// A JPEG with a caption (the unknown-driver photo).
async function sendImage(phone, jpeg, caption) {
  if (testSender) return testSender(phone, caption, jpeg);
  if (state.status !== 'connected' || !sock) {
    return { ok: false, error: 'WhatsApp not configured: link it in Settings → WhatsApp alerts' };
  }
  const digits = String(phone).replace(/\D/g, '');
  const [found] = (await sock.onWhatsApp(digits)) || [];
  if (!found?.exists) return { ok: false, error: `${phone} is not on WhatsApp` };
  const msg = await sock.sendMessage(found.jid, { image: jpeg, caption, mimetype: 'image/jpeg' });
  return { ok: true, id: msg?.key?.id };
}

// Tests replace the sender so nothing leaves the machine.
function setTestSender(fn) { testSender = fn; }

module.exports = { init, link, unlink, getStatus, sendText, sendImage, setTestSender };
