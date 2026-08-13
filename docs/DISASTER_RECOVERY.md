# Helios disaster recovery

Helios cannot guarantee that Oracle will retain an idle Always Free instance.
Recovery is therefore based on two independent backups, with no artificial
traffic and no paid resources.

## Backups

- OCI boot-volume backup: `helios-sprint1-2026-08-14`
- Encrypted local archive:
  `.secrets/backups/helios-recovery-2026-08-14.tar.gz.enc`
- Encryption key: `.secrets/backup.key`

The encrypted archive contains the persistent SQLite data, production
environment file, Caddy configuration, and systemd service definitions. Source
code remains in Git.

Keep the archive and key in separate places. Copy the key to a password manager
or offline drive. Both `.secrets/` paths are ignored by Git.

## Restore the OCI boot volume

1. In Oracle Cloud, open **Storage → Boot Volume Backups** in the Singapore home
   region.
2. Open `helios-sprint1-2026-08-14` and create an instance from the backup.
3. Select only an **Always Free-eligible** shape and confirm the estimate is
   `$0.00` before creating it.
4. Reapply inbound TCP 80 and 443 in the existing network security group.
5. If the public IP changes, replace the old IP-based `sslip.io` hostname in
   `/etc/caddy/Caddyfile` and `mobile/.env`, then restart Caddy and rebuild the
   mobile app.

## Inspect or restore the encrypted archive

Decrypt into a temporary location:

```sh
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -in .secrets/backups/helios-recovery-2026-08-14.tar.gz.enc \
  -out /tmp/helios-recovery.tar.gz \
  -pass file:.secrets/backup.key
tar -tzf /tmp/helios-recovery.tar.gz
```

On a replacement Oracle Linux VM, securely copy the archive, extract it as root
from `/`, reload systemd, and start `helios` and `caddy`. Delete every plaintext
temporary archive immediately after the restore.

## Verification

```sh
curl --fail https://NEW-IP.sslip.io/api/v1/health
curl -i https://NEW-IP.sslip.io/api/v1/energy/charging-mode
```

The health endpoint must return HTTP 200. The anonymous energy request must
return HTTP 401. An authenticated energy response must include
`"simulation": true`; Tesla must remain simulation-only.

Finally, check **Billing & Cost Management → Cost Analysis**. Expected actual
cost is `$0.00`.
