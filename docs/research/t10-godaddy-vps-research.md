# GB-T10.R1 GoDaddy Linux VPS research

This decision record summarizes the public documentation reviewed on 2026-10-26 UTC and prior local Nginx experiments recorded in draft #497 at `839eec6f4d21dfdbf68c35cedc1d7888772e59d7`. The source observations are dated. The plan catalogue, provider account and local experiments were not checked again for this record.

## Provisional decision

Keep GoDaddy Linux VPS as the deployment target. Evaluate a self-managed Linux VPS with Nginx at the public edge, Node services behind it, a private SQL listener and persistent private asset storage. Prefer Ubuntu 24.04 LTS if the authorized account and region offer that exact image. Evaluate Debian 12 or a supported AlmaLinux image if necessary. GoDaddy's published OS families and end-of-life list do not establish the exact available release, kernel or architecture. [VPS offering](https://www.godaddy.com/hosting/vps-hosting) · [Unsupported VPS operating systems](https://www.godaddy.com/en-ph/help/unsupported-operating-systems-for-vps-hosting-41852)

The historical VPS observation identifies 2 vCPU, 4 GB RAM and 100 GB NVMe as a staging benchmark candidate and 4 vCPU, 8 GB RAM and 200 GB NVMe as a production benchmark candidate. The staging disk envelope is 54 GiB for OS/images, SQL, assets, bounded logs and backup staging. The production hypothesis is 120 GiB. A synthetic workload of 50 editors at two 512-byte operations per second and mean fanout of 10 yields about 4.096 Mbps of operation payload before TLS, framing, retransmission, snapshots and downloads. Validate CPU, memory, storage growth, backup I/O and latency with representative data before selecting a tier. Vendor storage and traffic descriptions do not establish throughput, IOPS, packet-rate limits, IPv6 availability, storage expansion, recovery time or application capacity. [VPS offering](https://www.godaddy.com/hosting/vps-hosting)

Evaluate Compose first if the selected image and operations team support it. Compose makes release artifacts and network boundaries easier to reproduce and depends on pinned versions, measured resource limits and external checks for published ports. Same-host systemd can simplify host-level service management and requires explicit package pins, service isolation and restart policies. A managed GoDaddy VPS merits review if its support agreement covers the required operating responsibilities. Managed Node hosting remains optional and unverified. [Docker Ubuntu compatibility](https://docs.docker.com/engine/install/ubuntu/) · [Docker packet filtering](https://docs.docker.com/engine/network/packet-filtering-firewalls/) · [Node release schedule](https://nodejs.org/en/about/previous-releases)

Use reviewed public HTTPS and WebSocket routing through Nginx. Confirm the account's SSH/admin and provider recovery requirements before finalizing restrictions. Keep SQL and private assets off the public network and verify IPv4 and IPv6 exposure separately. Keep secrets outside source and artifacts. Measure a coherent SQL and asset restore before assigning recovery targets. Verify Discord mappings and client behavior with an authorized app and environment. [GoDaddy SSH](https://www.godaddy.com/en-uk/help/connect-to-my-server-with-ssh-secure-shell-4943) · [GoDaddy admin access](https://www.godaddy.com/en/help/enable-root-or-admin-access-to-my-vps-hosting-24737) · [GoDaddy recovery console](https://www.godaddy.com/en/help/use-the-recovery-console-for-vps-hosting-32064) · [Discord Activity networking](https://docs.discord.com/developers/activities/development-guides/networking) · [MySQL 8.4 backup policy](https://dev.mysql.com/doc/refman/8.4/en/backup-policy.html)

The original source capture recorded HTTP 403 from several public provider documents and MySQL. The draft records that the reviewers could read the official pages through a browser research tool. The documentation is mutable and is not an account entitlement check.

## Historical loopback proxy evidence

The repository draft records a 2026-11-13 UTC run using Nginx 1.28.0 and Python 3.14.8 at revision `7979aeec1f4e5970e20e42db62b827f9989f2ac6`. Nginx and a synthetic backend bound only to loopback. The record reports 12 passing baseline checks and detection of all three deliberate misconfigurations (extended inactivity timeout, stripped Upgrade, exposed private route). The October idle result was superseded because the backend could independently close. The corrected fixture kept the backend silent for up to 10 seconds, beyond the client's 4.5-second deadline. A two-second Nginx read timeout closed the tunnel as expected, while the 60-second control hit the client deadline. These versions and parameters describe that experiment. [Nginx WebSocket proxying](https://nginx.org/en/docs/http/websocket.html) · [Nginx proxy module](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)

A later receipt dated 2026-11-14 UTC records a local Nginx baseline with 12 passing checks and six detected unsafe controls at revision `9a35817037d5983c7b7faccd5da89cd77f3e7072`. That receipt is evidence for its recorded revision and environment.

The historical runner commands below refer to the original draft tree and require an existing local binary. They were not run for this documentation change.

```sh
python3 scripts/research/t10-nginx-probe.py --nginx-binary /path/to/nginx
python3 scripts/research/t10-nginx-probe.py --nginx-binary /path/to/nginx --negative-control long-read-timeout
```

A loopback upgrade and frame test covers the fixture's HTTP/WebSocket path. Acceptance for public DNS and TLS, provider networking and capacity, Discord clients, SQL isolation and asset recovery requires separately reviewed real-environment evidence.

## Open acceptance

- #324 needs Platform Engineering review, the provider account and region's actual tier and image catalogue, documented network and storage limits, and applicable real-environment evidence.
- #325 remains downstream of #324. Deployment contracts and production verification remain tracked separately.
- Historical receipts, runner and tests remain in draft history. This digest preserves their revision references and omits raw diagnostic and environment data.
