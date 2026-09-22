# Net-Aggregator

A concurrent multi-interface downloader that splits a file into byte-range chunks and downloads them simultaneously across multiple local network interfaces (Wi-Fi + USB tethering), instead of relying on a single connection.

Chunk sizes are split proportionally to a quick speed probe on each interface rather than evenly, since an even split means the slower interface bottlenecks the whole download.

**Honest finding from testing:** aggregation isn't automatically faster. On a stable-but-slow Wi-Fi network paired with a much faster USB tether, combining both was *slower* than the fast interface alone (2m59s vs 31s for the same 100MB file), because the whole job waits on the slowest chunk. This is what's known as the straggler effect, and it's why the project also includes interface fallback/retry handling — see [Benchmarks](#benchmarks) below.

## Core Mechanics

* **Probe-Based Proportional Splitting:** The downloader dynamically evaluates the real-time capacity of each connected interface. It then allocates chunk sizes proportionally.
* **Concurrent Asynchronous Processing:** Built entirely on `asyncio` and `aiohttp` for lightweight, non-blocking network I/O.
* **Timeout + Fallback Retry:** Each chunk has a request timeout, so a stalled interface doesn't hang the whole download indefinitely (this was a real failure encountered during testing — see Benchmarks). If a chunk fails, it's retried once on whichever interface measured fastest during the initial probe.

## Benchmarks

Tested downloading the same 100MB file (`fsn1-speed.hetzner.com/100MB.bin`) three ways, from the same location at the same time:

| Method              | Time     |
|----------------------|----------|
| USB tether alone     | 0m31s    |
| Wi-Fi alone           | Did not complete (5m15s+ before timeout) |
| Combined (both)       | 2m59s    |

The bottleneck here was one specific unstable hostel Wi-Fi network, not a flaw in the aggregation logic itself — aggregating across two similarly fast, stable interfaces would be expected to show a real speedup. This result is exactly what motivated adding per-chunk timeouts and fallback retry, rather than assuming both interfaces are equally reliable.

## Related Work

Bonding multiple network links together isn't a new problem — a few existing
projects solve it at different layers, worth naming so it's clear this
project sits in a known space rather than inventing something from nothing:

- **MPTCP (Multipath TCP)** — a kernel-level TCP extension (RFC 8684) that
  lets a single connection use multiple interfaces transparently, but both
  client and server need to support it. This project does the same basic
  thing at the application layer instead, using HTTP Range requests and
  manual socket binding, which works against any ordinary server without
  needing MPTCP on the other end.
- **OpenMPTCProuter** — an open-source router project that bonds Wi-Fi and
  cellular using MPTCP, aimed at the same "combine unreliable links into one
  faster connection" problem this project tackles, at the router/OS level
  rather than inside a single script.
- **Speedify** — a commercial VPN-based product that bonds Wi-Fi and
  cellular on a laptop the same way, running as a background service instead
  of a CLI tool.
- **aria2** — a well-known download accelerator that already does the
  segmented, parallel-Range-request part of this project, but over a single
  network connection. This project is closer to extending that idea to the
  case aria2 doesn't handle: multiple interfaces at once, not just multiple
  parallel requests on one.

Worth being precise about scope: this is application-layer aggregation on a
single machine, not a kernel feature and not a distributed system — easy
distinction to blur, so stating it directly here.
## Installation & Setup

This project uses `uv` for deterministic, high-speed dependency management.

```bash
git clone https://github.com/Chakrabortyprasun/net-aggregator.git
cd net-aggregator
uv sync
