import asyncio

import aiohttp


def write_chunk_to_disk(filename: str, offset: int, data: bytes) -> None:
    """Best practice: Open in read/write binary mode, seek to the offset, and write."""
    with open(filename, "r+b") as f:
        f.seek(offset)
        f.write(data)

async def download_chunk(session: aiohttp.ClientSession, url: str, start: int, end: int, filename: str):
    headers = {"Range": f"bytes={start}-{end}"}
    print(f"[*] Requesting bytes {start}-{end}...")
    
    async with session.get(url, headers=headers) as response:
        if response.status != 206:
            print(f"[!] FATAL: Chunk {start}-{end} failed (Status {response.status})")
            return
        
        chunk_data = await response.read()
        loop = asyncio.get_running_loop()
        # Offload the blocking disk I/O to a background thread
        await loop.run_in_executor(None, write_chunk_to_disk, filename, start, chunk_data)
        print(f"[+] Successfully wrote bytes {start}-{end}")

async def main():
    url = "https://httpbin.org/range/1024"
    filename = "02_output.bin"
    
    # Pre-allocate a 300-byte file (we are downloading 3 chunks of 100 bytes)
    with open(filename, "wb") as f:
        f.truncate(300)
        
    async with aiohttp.ClientSession() as session:
        print("--- Launching Concurrent Requests ---")
        # Pack our tasks into a list
        tasks = [
            download_chunk(session, url, 0, 99, filename),
            download_chunk(session, url, 100, 199, filename),
            download_chunk(session, url, 200, 299, filename)
        ]
        
        # Execute all tasks simultaneously 
        await asyncio.gather(*tasks)
        print("--- All chunks assembled ---")

if __name__ == "__main__":
    asyncio.run(main())