#!/usr/bin/env bash
# Runs on the Pi after install: checks services, the API, and the full
# edge → backend → acknowledge path over the real MQTT broker and MongoDB.
set -uo pipefail
API=http://127.0.0.1:3000/api
DEV=pi-vision-01
pass=0; fail=0
ok()  { echo "  PASS  $1"; pass=$((pass+1)); }
bad() { echo "  FAIL  $1"; fail=$((fail+1)); }
check() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
json() { node -e "let d='';process.stdin.on('data',c=>d+=c).on('end',()=>{const o=JSON.parse(d);console.log($1)})"; }

echo "== services"
check "mongod running"      "systemctl is-active --quiet mongod"
check "mosquitto running"   "systemctl is-active --quiet mosquitto"
check "dms-backend running" "systemctl --user is-active --quiet dms-backend"
check "dms-edge running"    "systemctl --user is-active --quiet dms-edge"
check "MongoDB answers"     "LD_LIBRARY_PATH=/opt/mongodb/lib /opt/mongodb/bin/mongod --version"

echo "== API"
for i in $(seq 1 20); do curl -sf $API/health >/dev/null && break; sleep 1; done
check "health endpoint" "curl -sf $API/health"

email="smoke$(date +%s)@test.local"
reg=$(curl -s -X POST $API/auth/register -H 'Content-Type: application/json' \
  -d "{\"name\":\"Smoke Test\",\"email\":\"$email\",\"password\":\"password123\"}")
token=$(echo "$reg" | json 'o.accessToken||""')
[[ -n "$token" ]] && ok "register + JWT" || { bad "register ($reg)"; exit 1; }
H=(-H "Authorization: Bearer $token" -H 'Content-Type: application/json')
# Unpair the device on exit, so the real owner (and the next smoke run) can pair it.
devid=""
trap '[[ -n "$devid" ]] && curl -s "${H[@]}" -X DELETE "$API/devices/$devid" >/dev/null' EXIT

curl -sf "${H[@]}" -X POST $API/contacts -d '{"name":"Test","phone":"+923001234567"}' >/dev/null \
  && ok "add emergency contact" || bad "add emergency contact"

echo "== edge link (MQTT)"
for i in $(seq 1 30); do
  curl -s "${H[@]}" $API/devices/discover | grep -q "$DEV" && break; sleep 2
done
curl -s "${H[@]}" $API/devices/discover | grep -q "$DEV" && ok "edge pipeline seen on MQTT" || bad "edge pipeline not seen on MQTT"
curl -s "${H[@]}" -X POST $API/devices -d "{\"deviceId\":\"$DEV\",\"name\":\"Smoke test car\"}" >/dev/null
sleep 3
devid=$(curl -s "${H[@]}" $API/devices | json 'o[0]?o[0].id:""')
state=$(curl -s "${H[@]}" $API/devices | json 'o[0]&&o[0].online')
[[ "$state" == "true" ]] && ok "device paired and online" || bad "device online ($state)"

eid="smoke-$(date +%s)"
mosquitto_sub -h 127.0.0.1 -t "dms/$DEV/cmd/ack" -C 1 -W 15 > /tmp/ack.txt &
mosquitto_pub -h 127.0.0.1 -q 1 -t "dms/$DEV/event" -m "{\"eventId\":\"$eid\",\"type\":\"drowsiness\",\"severity\":\"critical\",\"detectedAt\":\"$(date -u +%FT%TZ)\",\"description\":\"smoke test\"}"
sleep 2
id=$(curl -s "${H[@]}" $API/events/active | json 'o.length?o[0].id:""')
[[ -n "$id" ]] && ok "event stored in MongoDB" || bad "event not stored"
curl -s "${H[@]}" -X POST "$API/events/$id/acknowledge" | grep -q acknowledged && ok "acknowledge via API" || bad "acknowledge"
wait
grep -q "$eid" /tmp/ack.txt && ok "ack delivered back to edge over MQTT" || bad "ack not received on MQTT"

echo "== camera / AI"
journalctl --user-unit dms-edge --since "-5 min" --no-pager | grep -E "camera opened" >/dev/null \
  && ok "camera opened by pipeline" || bad "camera not opened (check: journalctl --user-unit dms-edge)"
journalctl --user-unit dms-edge --since "-5 min" --no-pager | grep -E "perf:" | tail -1

echo; echo "RESULT: $pass passed, $fail failed"
[[ $fail -eq 0 ]]
