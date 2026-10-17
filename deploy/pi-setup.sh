#!/usr/bin/env bash
# One-time Raspberry Pi 4 setup: Node.js, MongoDB 7 (community Pi 4 build),
# Mosquitto MQTT broker and the Python packages used by the edge pipeline.
# Safe to re-run. Usage: sudo bash pi-setup.sh
set -euo pipefail

MONGO_VERSION="7.0.40"
MONGO_URL="https://github.com/themattman/mongodb-raspberrypi-binaries/releases/download/r${MONGO_VERSION}-rpi-unofficial/mongodb.ce.pi4.r${MONGO_VERSION}.tar.gz"
LIBSSL11_URL="https://deb.debian.org/debian/pool/main/o/openssl/libssl1.1_1.1.1w-0+deb11u1_arm64.deb"
NODE_MAJOR=22

echo "==> apt packages"
apt-get update -y
apt-get install -y --no-install-recommends \
  ca-certificates curl gnupg ffmpeg \
  mosquitto mosquitto-clients \
  python3-venv python3-pip python3-numpy python3-opencv python3-picamera2 \
  python3-paho-mqtt python3-serial python3-gpiozero python3-pytest \
  libgles2 libegl1   # MediaPipe's native library links these, even on the CPU

echo "==> Node.js ${NODE_MAJOR}"
if ! command -v node >/dev/null || [[ "$(node -v)" != v${NODE_MAJOR}.* ]]; then
  curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash -
  apt-get install -y nodejs
fi
node -v

echo "==> MongoDB ${MONGO_VERSION} (unofficial Pi 4 build)"
if ! LD_LIBRARY_PATH=/opt/mongodb/lib /opt/mongodb/bin/mongod --version 2>/dev/null | grep -q "${MONGO_VERSION}"; then
  tmp=$(mktemp -d)
  curl -fsSL "$MONGO_URL" -o "$tmp/mongo.tgz"
  mkdir -p /opt/mongodb/bin
  tar -xzf "$tmp/mongo.tgz" -C "$tmp"
  find "$tmp" -maxdepth 2 -type f \( -name mongod -o -name mongo -o -name mongos -o -name mongosh \) \
    -exec install -m 0755 {} /opt/mongodb/bin/ \;
  rm -rf "$tmp"
fi
# The Pi builds link OpenSSL 1.1, which Debian 12+/13 no longer ship. Keep a
# private copy for mongod only (bound to 127.0.0.1); the system OpenSSL is untouched.
if ! ldconfig -p | grep -q 'libcrypto.so.1.1' && [[ ! -f /opt/mongodb/lib/libcrypto.so.1.1 ]]; then
  tmp=$(mktemp -d)
  curl -fsSL "$LIBSSL11_URL" -o "$tmp/libssl.deb"
  dpkg-deb -x "$tmp/libssl.deb" "$tmp/x"
  mkdir -p /opt/mongodb/lib
  find "$tmp/x" -name 'lib*.so.1.1' -exec install -m 0644 {} /opt/mongodb/lib/ \;
  rm -rf "$tmp"
fi
id mongodb >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin mongodb
mkdir -p /var/lib/mongodb /var/log/mongodb
chown -R mongodb:mongodb /var/lib/mongodb /var/log/mongodb

cat >/etc/mongod.conf <<'CONF'
storage:
  dbPath: /var/lib/mongodb
  wiredTiger:
    engineConfig:
      cacheSizeGB: 0.25   # keep RAM free for the AI pipeline
systemLog:
  destination: file
  path: /var/log/mongodb/mongod.log
  logAppend: true
net:
  port: 27017
  bindIp: 127.0.0.1       # only the local backend can connect
CONF

cat >/etc/systemd/system/mongod.service <<'UNIT'
[Unit]
Description=MongoDB (Pi 4 community build)
After=network.target

[Service]
User=mongodb
Group=mongodb
Environment=LD_LIBRARY_PATH=/opt/mongodb/lib
ExecStart=/opt/mongodb/bin/mongod --config /etc/mongod.conf
Restart=on-failure
LimitNOFILE=64000

[Install]
WantedBy=multi-user.target
UNIT

echo "==> Mosquitto (localhost only)"
cat >/etc/mosquitto/conf.d/dms.conf <<'CONF'
listener 1883 127.0.0.1
allow_anonymous true
CONF

systemctl daemon-reload
systemctl enable --now mongod mosquitto
systemctl restart mosquitto

echo "==> App user permissions"
APP_USER="${SUDO_USER:-vision}"
mkdir -p /var/lib/dms/clips
chown -R "$APP_USER:$APP_USER" /var/lib/dms
usermod -aG video,gpio,dialout,systemd-journal "$APP_USER" || true   # camera, buzzer/LED/button, GPS serial, logs
# Lets the backend and edge run as user services that start at boot
# and can be restarted on redeploy without sudo.
loginctl enable-linger "$APP_USER"

echo "==> done"
LD_LIBRARY_PATH=/opt/mongodb/lib /opt/mongodb/bin/mongod --version | head -1
