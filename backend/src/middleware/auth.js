const { User } = require('../models');
const ApiError = require('../utils/ApiError');
const { verifyAccessToken } = require('../services/tokenService');

// Family members and guests act on their owner's vehicle data.
function accountOwnerId(user) {
  return ['family', 'guest'].includes(user.role) && user.owner ? user.owner : user._id;
}

async function userFromToken(token) {
  let payload;
  try {
    payload = verifyAccessToken(token);
  } catch {
    throw ApiError.unauthorized('Invalid or expired token');
  }
  const user = await User.findById(payload.sub);
  if (!user || !user.isActive) throw ApiError.unauthorized('Account not found or deactivated');
  return user;
}

async function requireAuth(req, res, next) {
  const header = req.get('authorization') || '';
  const token = header.startsWith('Bearer ') ? header.slice(7) : null;
  if (!token) throw ApiError.unauthorized();
  req.user = await userFromToken(token);
  req.ownerId = accountOwnerId(req.user);
  next();
}

const requireRole = (...roles) => (req, res, next) => {
  if (!roles.includes(req.user.role)) throw ApiError.forbidden();
  next();
};

module.exports = { requireAuth, requireRole, userFromToken, accountOwnerId };
