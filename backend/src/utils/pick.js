// Copies only the allowed keys from a request body, so clients cannot set
// fields like `owner` or `role` on themselves.
function pick(obj, keys) {
  const out = {};
  for (const k of keys) if (obj && obj[k] !== undefined) out[k] = obj[k];
  return out;
}

module.exports = pick;
