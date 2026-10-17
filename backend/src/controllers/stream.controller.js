const tickets = require('../services/streamTickets');

const isLocal = (ip) => ['127.0.0.1', '::1', '::ffff:127.0.0.1'].includes(ip);

// Called by MediaMTX (authMethod: http) for every stream connection.
// publish: only the edge pipeline on this Pi. read: the RTSP password must be a
// live-view ticket for the device named by the path (issued by
// POST /api/devices/:id/live). 200 allows, 401 denies.
function auth(req, res) {
  if (!isLocal(req.ip)) return res.status(403).end();
  const { action, path, ip, password, token } = req.body || {};

  if (action === 'publish') return res.status(isLocal(ip) ? 200 : 401).end();
  if (action !== 'read') return res.status(401).end();
  return res.status(tickets.check(password || token, path) ? 200 : 401).end();
}

module.exports = { auth };
