import asyncio
import aiohttp

async def send_request(url, session):
    async with session.get(url) as response:
        return await response.text()

async def request_worker(url, queue):
    async with aiohttp.ClientSession() as session:
        while True:
            future = asyncio.ensure_future(send_request(url, session))
            await queue.put(future)
            await asyncio.sleep(0.05)  # Wait for 50 ms before sending the next request

async def print_worker(queue):
    while True:
        future = await queue.get()
        response = await future
        print("Response:", response)

async def main():
    url = "http://example.com"  # Replace with your server URL
    queue = asyncio.Queue()

    request_task = asyncio.create_task(request_worker(url, queue))
    print_task = asyncio.create_task(print_worker(queue))

    await asyncio.gather(request_task, print_task)

if __name__ == "__main__":
    asyncio.run(main())