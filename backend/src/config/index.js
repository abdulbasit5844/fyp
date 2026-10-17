require('dotenv').config();

const env = process.env.NODE_ENV || 'development';

const config = {
  env,
  port: Number(process.env.PORT) || 3000,
  mongoUri: process.env.MONGODB_URI || 'mongodb://127.0.0.1:27017/dms',
  mqttUrl: process.env.MQTT_URL || 'mqtt://127.0.0.1:1883',
  rtspPort: Number(process.env.RTSP_PORT) || 8554, // MediaMTX on the Pi (live view)
  jwt: {
    secret: process.env.JWT_SECRET,
    accessTtl: '24h', // FR5.2
    refreshTtlMs: 7 * 24 * 60 * 60 * 1000, // FR5.3
  },
  clipsDir: process.env.CLIPS_DIR || '/var/lib/dms/clips',
  tls: { cert: process.env.TLS_CERT, key: process.env.TLS_KEY },
  firebaseServiceAccount: process.env.FIREBASE_SERVICE_ACCOUNT,
  twilio: {
    accountSid: process.env.TWILIO_ACCOUNT_SID,
    authToken: process.env.TWILIO_AUTH_TOKEN,
    from: process.env.TWILIO_FROM,
  },
  // WhatsApp via a linked account (QR code in the app). Off in tests.
  whatsapp: {
    enabled: process.env.WHATSAPP !== 'off' && env !== 'test',
    authDir: process.env.WHATSAPP_AUTH_DIR || require('path').join(__dirname, '..', '..', 'whatsapp-auth'),
  },
  // Gmail by default; EMAIL_PASS is a Google app password, not the account password.
  email: {
    user: process.env.EMAIL_USER,
    pass: process.env.EMAIL_PASS,
    host: process.env.SMTP_HOST || 'smtp.gmail.com',
    port: Number(process.env.SMTP_PORT) || 465,
  },
};

if (!config.jwt.secret || config.jwt.secret === 'change-me') {
  if (env === 'production') throw new Error('JWT_SECRET must be set in production');
  config.jwt.secret = 'dev-only-secret';
}

module.exports = config;
