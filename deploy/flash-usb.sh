#!/usr/bin/env bash
# Writes Raspberry Pi OS Lite to a USB drive (or SD card) attached to WSL and
# pre-configures hostname, user, Wi-Fi and SSH via cloud-init, like Imager does.
#   sudo bash flash-usb.sh /dev/sdX /path/raspios.img.xz /path/settings-dir
# settings-dir holds user-data and network-config saved from the previous install.
set -euo pipefail
DEV="$1"; IMG="$2"; CFG="$3"
PUBKEY_FILE="${PUBKEY_FILE:-}"

# --- safety checks: only a USB disk smaller than 260 GB, never a WSL system disk
[[ -b "$DEV" ]] || { echo "no such block device $DEV"; exit 1; }
tran=$(lsblk -dno TRAN "$DEV"); size=$(blockdev --getsize64 "$DEV")
echo "target: $DEV  $(lsblk -dno MODEL,SIZE "$DEV")  transport=$tran"
[[ "$tran" == "usb" ]] || { echo "refusing: $DEV is not a USB device"; exit 1; }
(( size < 260000000000 )) || { echo "refusing: $DEV is larger than 260 GB"; exit 1; }
if findmnt -rno SOURCE | grep -q "^$DEV"; then echo "refusing: $DEV is mounted"; exit 1; fi

echo "== writing image (this erases $DEV)"
xzcat "$IMG" | dd of="$DEV" bs=4M conv=fsync status=progress
sync; partprobe "$DEV" 2>/dev/null || blockdev --rereadpt "$DEV"; sleep 2

BOOT="${DEV}1"; [[ -b "$BOOT" ]] || BOOT="${DEV}p1"
mnt=$(mktemp -d); mount "$BOOT" "$mnt"

echo "== cloud-init settings"
id="dms-$(date +%s)"
cp "$CFG/network-config" "$mnt/network-config"
printf 'instance-id: %s\n' "$id" > "$mnt/meta-data"
# Previous user-data minus the Raspberry Pi Connect lines, plus our SSH key.
grep -vE 'raspberrypi\.connect|rpi-connect|linger|vision@\.host|sleep, "2"|\.config/systemd' "$CFG/user-data" > "$mnt/user-data"
if [[ -n "$PUBKEY_FILE" && -f "$PUBKEY_FILE" ]]; then
  key=$(cat "$PUBKEY_FILE")
  sed -i "/^user:/,/^[a-z_]*:/ s|^  shell: /bin/bash|  shell: /bin/bash\n  ssh_authorized_keys:\n    - \"$key\"|" "$mnt/user-data"
fi
grep -q 'ds=nocloud' "$mnt/cmdline.txt" \
  && sed -i -E "s/ds=nocloud;i=[^ ]*/ds=nocloud;i=$id/" "$mnt/cmdline.txt" \
  || sed -i "1 s/\$/ ds=nocloud;i=$id/" "$mnt/cmdline.txt"

echo "cmdline: $(cat "$mnt/cmdline.txt")"
grep -nE 'hostname|name:|ssh_authorized_keys|ssh_pwauth' "$mnt/user-data"
sync; umount "$mnt"; rmdir "$mnt"
echo "== done. Move the drive to the Pi (blue USB port), remove the SD card, power on."
