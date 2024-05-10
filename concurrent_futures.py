import threading
import time
import requests
import queue
from concurrent.futures import ThreadPoolExecutor

# Create a queue to hold responses
response_queue = queue.Queue()

def child_thread():
    print("Current time:", time.time())
    # Perform a non-blocking example server request
    response = requests.get("https://jsonplaceholder.typicode.com/posts/1")
    response_text = response.text
    response_queue.put(response_text)

def main():
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=30) as executor:  # Adjust max_workers as needed
        while True:
            # Check if 50 milliseconds have passed since the last thread creation
            if time.time() - start_time >= 0.05:
                executor.submit(child_thread)
                start_time = time.time()  # Reset the start time

if __name__ == "__main__":
    main()