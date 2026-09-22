import asyncio

import aiohttp


def write_chunk_to_disk(filename: str, data: bytes) -> None:
    """Blocking file write — must be run off the event loop thread."""
    with open(filename, "wb") as f:
        f.write(data)

async def main():
    url = "https://httpbin.org/range/1024"
    # Get the current event loop so we can hand off blocking tasks
    loop = asyncio.get_running_loop()
    
    async with aiohttp.ClientSession() as session:
        
        # --- PHASE 1: RECONNAISSANCE ---
        print("--- 1. Sending HEAD request ---")
        async with session.head(url) as head_response:
            print(f"Server accepts ranges: {head_response.headers.get('Accept-Ranges')}")
            print(f"Total file size: {head_response.headers.get('Content-Length')} bytes\n")

        # --- PHASE 2: THE PAYLOAD ---
        headers = {"Range": "bytes=0-99"}
        print(f"--- 2. Sending GET request with {headers} ---")
        
        async with session.get(url, headers=headers) as get_response:
            
            # --- PHASE 3: VERIFICATION ---
            print(f"Status Code: {get_response.status}")
            print(f"Content-Range header received: {get_response.headers.get('Content-Range')}")
            
            if get_response.status != 206:
                print("FATAL ERROR: Server did not return 206 Partial Content. It ignored the Range header.")
                return

            chunk_data = await get_response.read()
            print(f"\nDownloaded exactly {len(chunk_data)} bytes.")
            
            # --- PHASE 4: DISK ASSEMBLY (Now Non-Blocking) ---
            # We specifically changed this to .bin as real files will be raw binary, not text.
            filename = "chunk_output.bin"
            
            # Run the blocking write in a thread pool so it doesn't stall the event loop
            await loop.run_in_executor(None, write_chunk_to_disk, filename, chunk_data)
            
            print(f"Success: Wrote raw bytes to {filename}.")

if __name__ == "__main__":
    asyncio.run(main())