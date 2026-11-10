# Server-only VPN whitelist

The production VPN whitelist is runtime server configuration. It is excluded
from Git; deployment must not replace the allowed addresses with repository data.

The authoritative file is
`/home/akasimov/pagepilot-server/whitelist_vpn.conf` (overridable with
`PAGEPILOT_VPN_WHITELIST`). Keep it readable by the deployment account and preserve
its existing permissions. Address changes belong in this server file.

Deployment checks that the file exists before checkout, then restores its exact
bytes to `infra/nginx/whitelists/whitelist_vpn.conf`, the existing nginx mount.
An exit trap also restores the file if checkout fails. No services are rebuilt
or reloaded before restoration succeeds. Health checks include nginx validation.

For the initial migration, preserve the active file outside Git and verify its
checksum before reconciling the tracked path. Keep a restoration trap during
the transition, do not reload nginx with the old repository rules, and confirm
the original checksum both after checkout and after nginx reload. New addresses
must not be committed as part of this migration.
