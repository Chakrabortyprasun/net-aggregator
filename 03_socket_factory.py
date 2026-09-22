import asyncio
import socket

import aiohttp

# Linux kernel constant for SO_BINDTODEVICE


def get_bound_socket_factory(interface_name: str):
    """
    Returns a custom socket factory function exactly as aiohttp expects.
    """
    def socket_factory(addr_info):
        # aiohttp passes a single 5-element tuple. We unpack the first 3.
        family, type_, proto, _, _ = addr_info
        
        # 1. Create the socket
        sock = socket.socket(family=family, type=type_, proto=proto)
        
        # 2. Inject the hardware-level routing flag
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, interface_name.encode('utf-8'))
        return sock
        
    return socket_factory

async def fetch_ip_via_interface(interface_name: str):
    print(f"--- Firing request out of {interface_name} ---")
    
    # Apply the factory per-connector
    factory = get_bound_socket_factory(interface_name)
    connector = aiohttp.TCPConnector(socket_factory=factory)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        try:
            async with session.get("https://api.ipify.org?format=json") as response:
                data = await response.json()
                print(f"Success! Packet exited {interface_name}. IP: {data['ip']}")
        except PermissionError:
            print("ERROR: SO_BINDTODEVICE requires root. Run with sudo.")
        except Exception as e:
            print(f"Request failed: {e}")

async def main():
    await fetch_ip_via_interface("wlp1s0")

if __name__ == "__main__":
    asyncio.run(main())