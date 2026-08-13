# Helios Oracle Free Tier guardrails

Helios is deliberately sized to remain within Oracle Cloud Always Free limits.

## Current deployment

- Account type: Free Tier (do not upgrade to Pay As You Go)
- Region: Singapore home region
- Compute: one `VM.Standard.E2.1.Micro` instance labelled Always Free
- Storage: one default 46.6 GB boot volume
- Network: one VCN, public IPv4, and standard ingress rules for SSH/HTTP/HTTPS
- HTTPS: Caddy and Let's Encrypt, both free
- Tesla: `TESLA_SIMULATION_ONLY=true`

## Rules that prevent future charges

1. Do not click **Upgrade** or add a payment-based subscription.
2. Create no resource unless the Oracle review page explicitly labels it
   **Always Free-eligible**.
3. Keep total block/boot volume storage below the Always Free 200 GB allowance.
4. Keep A1 usage, if capacity becomes available, at or below the allowance shown
   by the Console (currently 2 OCPUs and 12 GB total for this tenancy).
5. Keep at most five Always Free volume backups in the home region. Do not
   enable cross-region replication or add paid load balancers, databases, or
   marketplace images.
6. Review **Billing & Cost Management → Cost Analysis** after any infrastructure
   change. Expected actual cost is `$0.00`.
7. Keep this account as Free Tier. A Free Tier account cannot incur card charges
   unless it is explicitly upgraded.

## Availability caveat

Oracle may reclaim Always Free compute that it classifies as idle. This is an
availability risk, not a billing risk. Do not create artificial paid traffic or
extra resources to avoid reclamation; keep an exported backup of Helios data and
redeploy to another Always Free instance if necessary.

Current recovery protection:

- OCI manual boot-volume backup: `helios-sprint1-2026-08-14`
- Encrypted off-VM recovery archive: `.secrets/backups/helios-recovery-2026-08-14.tar.gz.enc`
- Local recovery key: `.secrets/backup.key` (copy this separately to a password
  manager or offline drive; never commit it)
