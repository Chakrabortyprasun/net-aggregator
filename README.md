# Net-Aggregator

A high-performance concurrent multi-interface downloader designed to aggregate bandwidth across multiple local network connections (e.g., simultaneously utilizing Wi-Fi and USB tethering). 

Rather than relying on a single connection bottleneck, this tool aggressively chunks file requests and routes them concurrently through available network interfaces to maximize total throughput.

## Core Mechanics

* **Probe-Based Proportional Splitting:** The downloader dynamically evaluates the real-time capacity of each connected interface. It then allocates chunk sizes proportionally, ensuring faster connections take on more load without being bottlenecked by slower ones.
* **Concurrent Asynchronous Processing:** Built entirely on `asyncio` and `aiohttp` for lightweight, non-blocking network I/O.
* **Fallback Retry Resilience:** Network interfaces can be unstable. If a chunk fails due to a dropped connection, the aggregator automatically re-queues and retries the segment without corrupting the final assembly.

## Installation & Setup

This project uses `uv` for deterministic, high-speed dependency management.

```bash
git clone [https://github.com/Chakrabortyprasun/net-aggregator.git](https://github.com/Chakrabortyprasun/net-aggregator.git)
cd net-aggregator
uv sync