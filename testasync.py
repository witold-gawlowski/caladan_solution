import asyncio

# Simulating fetching data asynchronously
async def fetch_data():
    print("Fetching data...")
    # Simulate fetching data asynchronously (e.g., making an HTTP request)
    await asyncio.sleep(2)  # Simulate a delay of 2 seconds
    data = "Fetched data"
    print("Data fetched")
    return data

# Simulating processing data
async def process_data(data):
    print("Processing data...")
    # Simulate processing data asynchronously
    await asyncio.sleep(1)  # Simulate a delay of 1 second
    processed_data = data.upper()  # Example processing
    print("Data processed")
    return processed_data

async def main():
    # Fetch data asynchronously
    fetched_data = await fetch_data()

    # Process the fetched data asynchronously
    processed_data = await process_data(fetched_data)

    # Print the processed data
    print("Processed data:", processed_data)

# Run the main coroutine
asyncio.run(main())