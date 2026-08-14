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

## Helios cost alarm

The Settings screen can show OCI's current-month actual and forecast spend.
Helios labels the result **Verified Zero** only after OCI returns an actual
spend of `USD 0.00`. The first positive actual spend in each calendar month
creates one critical alert and one Web Push notification for every subscribed
device. Repeated six-hour checks remain silent. A failed or stale check is shown
as unavailable, never as zero.

This uses an OCI Budget and the compute VM's instance principal, so no OCI API
private key is copied into Helios:

1. Create a root-compartment monthly budget named `Helios-Zero-Cost`.
2. Create a dynamic group whose matching rule selects only the Helios instance.
3. Add the policy `Allow dynamic-group HeliosCostMonitor to read usage-budgets in tenancy`.
4. Set `OCI_COST_MONITOR_ENABLED=true` in `/opt/helios/.env` and restart Helios.

Helios checks at startup, every six hours, and whenever **Check Oracle now** is
pressed. OCI budget data is delayed and is not a hard spending cap. Keep an OCI
Actual Spend budget email alert as a second, independent safety layer.

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
- Private Object Storage bucket: `helios-backups`; the VM keeps only the newest
  30 encrypted daily objects. Do not enable object versioning or remove the
  retention limit.

## Independent uptime monitoring

The Always Free APM domain `HeliosAlwaysFree` runs the REST monitor
`HeliosHealth` from Oracle's Singapore vantage point every six minutes. It
requires HTTPS status 200 and the response fragment `"status":"healthy"` from
`/api/v1/health`. One vantage point at this frequency uses 10 monitor runs per
hour.

The enabled critical alarm `Helios application unavailable` fires when the
monitor's mean availability is below 1 for one minute. It publishes to the
`Helios-Uptime-Alerts` Notifications topic. Repeat notifications are disabled;
each email subscription must be confirmed by its recipient before it becomes
active.

## VM security maintenance

Oracle Linux installs security-only updates through the enabled
`dnf-automatic-install.timer`. The production SSH policy is versioned in
`scripts/helios-sshd-hardening.conf`: only the `opc` account may connect,
public-key authentication remains enabled, password and root login are
disabled, authentication attempts are limited to three, and X11 forwarding is
disabled.

The reboot recovery drill on 2026-08-14 confirmed that `helios`, `caddy`, the
cloud-backup timer, and the security-update timer return automatically without
the Mac. Helios can briefly return HTTP 502 while its initial Solis request
finishes; the public health endpoint recovered without intervention.

## Meralco email import

The dedicated mailbox `helios.byerosenterprise@gmail.com` receives only
filtered Meralco bill notifications. Helios connects over Gmail IMAP with a
separate revocable Google app password stored at
`/opt/helios/secrets/gmail-import.env` with mode `600`; the normal Google
password is never stored. The importer accepts only original messages from
`customercare@meralco.com.ph` whose subject contains `Meralco Bill for` and
checks every six hours or on demand.

Email summaries provide the billing period, consumption, amount due, and due
date. They do not provide detailed meter readings, component rates, or
net-metering credits, so imported email history never silently replaces the
active PDF-derived billing baseline.
