#!/usr/bin/env bash
set -euo pipefail

readonly gmail_address="helios.byerosenterprise@gmail.com"
readonly ssh_key="/Users/samsamson/.ssh/helios_oci"
readonly remote_host="opc@168.107.79.27"
readonly remote_secret="/opt/helios/secrets/gmail-import.env"

if [[ ! -s "$ssh_key" ]]; then
  printf 'SSH key not found: %s\n' "$ssh_key" >&2
  exit 1
fi

printf 'Paste the 16-character Google app password for %s.\n' "$gmail_address"
printf 'It will not be displayed or stored in shell history.\n'
IFS= read -r -s -p 'Gmail app password: ' app_password
printf '\n'

# Google displays app passwords in groups. IMAP expects the same value without
# spaces, so normalize only spaces and leave every other character unchanged.
app_password="${app_password// /}"
if [[ ${#app_password} -ne 16 ]]; then
  unset app_password
  printf 'Expected a 16-character Google app password. Nothing was uploaded.\n' >&2
  exit 1
fi

{
  printf 'HELIOS_GMAIL_USERNAME=%s\n' "$gmail_address"
  printf 'HELIOS_GMAIL_APP_PASSWORD=%s\n' "$app_password"
} | ssh -i "$ssh_key" -o BatchMode=yes "$remote_host" \
  "sudo install -d -o opc -g opc -m 0700 /opt/helios/secrets &&
   sudo -u opc sh -c 'umask 077; tmp=\"${remote_secret}.tmp\"; cat > \"\$tmp\"; mv \"\$tmp\" \"${remote_secret}\"'"

unset app_password
ssh -i "$ssh_key" -o BatchMode=yes "$remote_host" \
  "sudo test -s '$remote_secret' && sudo test \"\$(stat -c %a '$remote_secret')\" = 600"

printf 'Helios Gmail credential stored securely on the Oracle VM.\n'
