import argparse
import asyncio
import os
import socket
import time

import aiohttp


def get_bound_socket_factory(interface_name: str):
    def socket_factory(addr_info):
        family, type_, proto, _, _ = addr_info
        sock = socket.socket(family=family, type=type_, proto=proto)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, interface_name.encode('utf-8'))
        return sock
    return socket_factory

async def measure_probe_speed(interface_name: str, url: str, probe_bytes: int) -> float:
    factory = get_bound_socket_factory(interface_name)
    connector = aiohttp.TCPConnector(socket_factory=factory, family=socket.AF_INET)
    headers = {
        'Range': f'bytes=0-{probe_bytes - 1}',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    }
    start_time = time.monotonic()
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                data = await response.read()
        elapsed = time.monotonic() - start_time
        speed = len(data) / elapsed if elapsed > 0 else 0.0
        print(f"[Probe] {interface_name}: {len(data)} bytes in {elapsed:.2f}s -> {speed / (1024*1024):.2f} MB/s")
        return speed
    except Exception as e:
        print(f"[Probe] {interface_name} FAILED: {type(e).__name__}: {e!r} -> treated as 0 speed")
        return 0.0

async def download_chunk(interface_name: str, url: str, start_byte: int, end_byte: int, filename: str, chunk_id: int):
    if start_byte > end_byte:
        return (True, interface_name, start_byte, end_byte, chunk_id)

    print(f"[Chunk {chunk_id}] Starting on {interface_name} (Bytes {start_byte}-{end_byte})...")
    
    factory = get_bound_socket_factory(interface_name)
    connector = aiohttp.TCPConnector(socket_factory=factory, family=socket.AF_INET)
    headers = {
        'Range': f'bytes={start_byte}-{end_byte}',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }
    
    timeout = aiohttp.ClientTimeout(total=60)
    current_byte = start_byte # TRACKER: Keep track of exactly where we are
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        try:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                with open(filename, 'r+b') as f:
                    f.seek(start_byte)
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        f.write(chunk)
                        current_byte += len(chunk) # Update tracker after every successful megabyte
            print(f"[Chunk {chunk_id}] Finished on {interface_name}!")
            return (True, interface_name, current_byte, end_byte, chunk_id)
        except Exception as e:
            print(f"[Chunk {chunk_id}] FAILED on {interface_name}: {type(e).__name__}")
            # Return exactly where it died so the fallback knows where to resume
            return (False, interface_name, current_byte, end_byte, chunk_id)

async def main():
    parser = argparse.ArgumentParser(description="Concurrent Multi-Interface Network Aggregator")
    parser.add_argument("url", help="The URL of the file to download")
    parser.add_argument("-o", "--output", required=True, help="The output filename (e.g., movie.mp4)")
    parser.add_argument("-i", "--interfaces", nargs="+", required=True, help="List of network interfaces")
    parser.add_argument("--probe-size", type=int, default=2, help="Probe size in MB (default: 2)")
    
    args = parser.parse_args()
    
    url = args.url
    filename = args.output
    interfaces = args.interfaces
    probe_bytes = args.probe_size * 1024 * 1024

    factory = get_bound_socket_factory(interfaces[0])
    connector = aiohttp.TCPConnector(socket_factory=factory, family=socket.AF_INET)
    headers = {'User-Agent': 'Mozilla/5.0', 'Range': 'bytes=0-0'}
    
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.get(url, headers=headers, allow_redirects=True) as resp:
            resp.raise_for_status()
            content_range = resp.headers.get('Content-Range', '')
            if '/' in content_range:
                total_size = int(content_range.split('/')[-1])
            else:
                raise ValueError("Server does not support Range requests. Cannot aggregate.")
    
    print(f"Target file size: {total_size / (1024*1024):.2f} MB")

    with open(filename, 'wb') as f:
        f.truncate(total_size)
        
    print(f"--- Running Speed Probes ({args.probe_size} MB) ---")
    probe_tasks = [measure_probe_speed(iface, url, probe_bytes) for iface in interfaces]
    speeds = await asyncio.gather(*probe_tasks)

    total_speed = sum(speeds)
    if total_speed == 0:
        raise RuntimeError("All interfaces failed the speed probe — check connectivity.")

    print("--- Calculating Proportional Split ---")
    tasks = []
    current_byte = 0
    for i, (iface, speed) in enumerate(zip(interfaces, speeds)):
        if i == len(interfaces) - 1:
            end = total_size - 1 
        else:
            proportion = speed / total_speed
            length = int(total_size * proportion)
            end = current_byte + length - 1
            
        print(f"Assigning {(end - current_byte + 1) / (1024*1024):.2f} MB to {iface}")
        tasks.append(download_chunk(iface, url, current_byte, end, filename, i))
        current_byte = end + 1
        
    # First Pass
    results = await asyncio.gather(*tasks)
    
    # THE FAILSAFE: Reroute broken chunks to the primary interface
    retry_tasks = []
    for res in results:
        success, iface, resume_byte, end_byte, chunk_id = res
        if not success and resume_byte <= end_byte:
            primary_iface = interfaces[0]
            remaining_mb = (end_byte - resume_byte + 1) / (1024 * 1024)
            print(f"--- FAILSAFE: Reassigning {remaining_mb:.2f} MB from {iface} to {primary_iface} ---")
            retry_tasks.append(download_chunk(primary_iface, url, resume_byte, end_byte, filename, chunk_id))
            
    if retry_tasks:
        retry_results = await asyncio.gather(*retry_tasks)
        final_success = all(r[0] for r in retry_results)
    else:
        final_success = all(r[0] for r in results)

    print("--- Download Complete! ---")
    
    if final_success:
        actual_size = os.path.getsize(filename)
        if actual_size == total_size:
            print("Integrity Check: PASSED. No bytes lost.")
        else:
            print("Integrity Check: FAILED. Size mismatch.")
    else:
        print("Integrity Check: ABORTED. One or more chunks failed recovery.")
        if os.path.exists(filename):
            os.remove(filename)

if __name__ == "__main__":
    asyncio.run(main())