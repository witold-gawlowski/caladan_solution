import asyncio
import aiohttp
import random

async def fetch_data(session, url):
    async with session.get(url) as response:
        return await response.text()

async def send_requests(urls):
    async with aiohttp.ClientSession() as session:
        while True:
            random_url = random.choice(urls)
            task = asyncio.create_task(fetch_data(session, random_url))
            await asyncio.sleep(0)  # Yield control to event loop
            # Continue without waiting for the task to finish
            asyncio.create_task(process_response(random_url, await task))
            await asyncio.sleep(0.05)

async def process_response(url, response):
    print(f"Response from {url}: {response[:50]}...")

async def main():
    urls = [
        'https://example.com/page1',
        'https://example.com/page2',
        'https://example.com/page3'
    ]
    await send_requests(urls)

if __name__ == "__main__":
    asyncio.run(main())