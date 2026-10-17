const { WebSocketServer } = require('ws');
const { userFromToken, accountOwnerId } = require('../middleware/auth');

// Live feed for the app: driver state, new alerts, acknowledgments and
// escalations. Clients connect to /ws?token=<access token>.
const sockets = new Map(); // ownerId -> Set<WebSocket>

function attach(server) {
  const wss = new WebSocketServer({ server, path: '/ws' });

  wss.on('connection', async (ws, req) => {
    const token = new URL(req.url, 'http://x').searchParams.get('token');
    let ownerId;
    try {
      const user = await userFromToken(token);
      ownerId = String(accountOwnerId(user));
    } catch {
      ws.close(4401, 'Unauthorized');
      return;
    }

    if (!sockets.has(ownerId)) sockets.set(ownerId, new Set());
    sockets.get(ownerId).add(ws);
    ws.isAlive = true;
    ws.on('pong', () => { ws.isAlive = true; });
    ws.on('close', () => sockets.get(ownerId)?.delete(ws));
    ws.send(JSON.stringify({ type: 'hello' }));
  });

  // Drop dead connections so the app reconnects promptly.
  const timer = setInterval(() => {
    for (const ws of wss.clients) {
      if (!ws.isAlive) { ws.terminate(); continue; }
      ws.isAlive = false;
      ws.ping();
    }
  }, 30000);
  wss.on('close', () => clearInterval(timer));
  return wss;
}

function broadcast(ownerId, type, data) {
  const set = sockets.get(String(ownerId));
  if (!set) return;
  const msg = JSON.stringify({ type, data });
  for (const ws of set) if (ws.readyState === ws.OPEN) ws.send(msg);
}

module.exports = { attach, broadcast };
