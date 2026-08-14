#!/bin/sh
set -eu

oci_cli="${OCI_CLI:-/opt/helios/oci-cli/bin/oci}"
namespace="${HELIOS_BACKUP_NAMESPACE:-axuuyimzgqfy}"
bucket="${HELIOS_BACKUP_BUCKET:-helios-backups}"
key_file="${HELIOS_BACKUP_KEY_FILE:-/opt/helios/backup/backup.key}"
database="${HELIOS_DATABASE:-/opt/helios/data/helios.db}"
retention_count="${HELIOS_BACKUP_RETENTION_COUNT:-30}"
work_dir="${HELIOS_BACKUP_WORK_DIR:-/opt/helios/backup/work}"
timestamp="$(date -u '+%Y-%m-%d_%H%M%SZ')"
snapshot="$work_dir/helios-$timestamp.sqlite"
archive="$work_dir/helios-$timestamp.tar.gz.enc"
object_name="daily/helios-$timestamp.tar.gz.enc"
objects_json="$work_dir/objects.json"
status_file="${HELIOS_BACKUP_STATUS_FILE:-/opt/helios/data/cloud_backup_status.json}"

mkdir -p "$work_dir"
test -x "$oci_cli"
test -s "$key_file"
test -s "$database"

cleanup() {
  rm -f "$snapshot" "$archive" "$objects_json"
}
trap cleanup EXIT INT TERM

python3 - "$database" "$snapshot" <<'PY'
import sqlite3
import sys

source = sqlite3.connect(sys.argv[1])
target = sqlite3.connect(sys.argv[2])
try:
    source.backup(target)
finally:
    target.close()
    source.close()
PY

tar -czf - \
  "$snapshot" \
  /opt/helios/.env \
  /etc/caddy/Caddyfile \
  /etc/systemd/system/helios.service \
  /etc/systemd/system/helios.service.d \
  | openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 \
      -pass "file:$key_file" -out "$archive"

test -s "$archive"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -pass "file:$key_file" -in "$archive" \
  | tar -tzf - >/dev/null

"$oci_cli" os object put \
  --auth instance_principal \
  --namespace "$namespace" \
  --bucket-name "$bucket" \
  --name "$object_name" \
  --file "$archive" \
  --no-multipart \
  --force >/dev/null

archive_size="$(wc -c <"$archive" | tr -d ' ')"
success_timestamp="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
status_tmp="$status_file.tmp"
python3 - "$status_tmp" "$success_timestamp" "$object_name" "$archive_size" "$retention_count" <<'PY'
import json
import os
import sys

path, timestamp, object_name, size, retention = sys.argv[1:]
payload = {
    "last_success_at": timestamp,
    "last_object": object_name,
    "size_bytes": int(size),
    "retention_count": int(retention),
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, separators=(",", ":"))
    handle.write("\n")
os.chmod(path, 0o644)
PY
mv "$status_tmp" "$status_file"

"$oci_cli" os object list \
  --auth instance_principal \
  --namespace "$namespace" \
  --bucket-name "$bucket" \
  --prefix daily/ \
  --all >"$objects_json"

python3 - "$objects_json" "$retention_count" <<'PY' | while IFS= read -r expired_name; do
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    objects = json.load(handle).get("data", [])

objects.sort(key=lambda item: item.get("time-created", ""), reverse=True)
for item in objects[int(sys.argv[2]):]:
    name = item.get("name")
    if name:
        print(name)
PY
  "$oci_cli" os object delete \
    --auth instance_principal \
    --namespace "$namespace" \
    --bucket-name "$bucket" \
    --name "$expired_name" \
    --force
done

printf 'Uploaded %s\n' "$object_name"
