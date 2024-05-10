import threading
import time
import requests

def child_thread():
    # Perform a blocking example server request
    print("server request", time.time())
    response = requests.get("https://jsonplaceholder.typicode.com/posts/1")
    #print("Server response", time.time())

def main():
    start_time = time.time()
    while True:
        # Check if 50 milliseconds have passed since the last thread creation
        if time.time() - start_time >= 0.05:
            thread = threading.Thread(target=child_thread)
            thread.start()
            start_time = time.time()  # Reset the start time

if __name__ == "__main__":
    main()