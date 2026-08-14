#!/bin/sh
set -eu

project_dir="/Users/samsamson/Projects/helios"
backup_dir="$project_dir/.secrets/backups"
key_file="$project_dir/.secrets/backup.key"
ssh_key="/Users/samsamson/.ssh/helios_oci"
remote_host="opc@168.107.79.27"
remote_snapshot="/tmp/helios-automatic-backup.sqlite"
timestamp="$(date '+%Y-%m-%d_%H%M%S')"
destination="$backup_dir/helios-automatic-$timestamp.tar.gz.enc"
partial="$destination.partial"

mkdir -p "$backup_dir"
test -s "$key_file"
test -s "$ssh_key"

cleanup() {
  rm -f "$partial"
  ssh -i "$ssh_key" -o BatchMode=yes "$remote_host" \
    "sudo rm -f '$remote_snapshot'" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

ssh -i "$ssh_key" -o BatchMode=yes "$remote_host" \
  "sudo /usr/bin/python3 -c \"import sqlite3; source=sqlite3.connect('/opt/helios/data/helios.db'); target=sqlite3.connect('$remote_snapshot'); source.backup(target); target.close(); source.close()\""

ssh -i "$ssh_key" -o BatchMode=yes "$remote_host" \
  "sudo tar -czf - '$remote_snapshot' /opt/helios/.env /etc/caddy/Caddyfile /etc/systemd/system/helios.service /etc/systemd/system/helios.service.d" \
  | openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
      -pass "file:$key_file" -out "$partial"

test -s "$partial"
mv "$partial" "$destination"
chmod 600 "$destination"

openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -pass "file:$key_file" -in "$destination" \
  | tar -tzf - >/dev/null

printf '%s\n' "$destination"
