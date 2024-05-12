import multiprocessing
import time

# Function to be executed by each process
def increment_counter(shared_counter):
    for _ in range(5):
        # Incrementing the shared counter by 1
        with shared_counter.get_lock():
            shared_counter.value = shared_counter.value + 1
        time.sleep(1)

if __name__ == "__main__":
    # Creating a shared counter using multiprocessing.Value
    shared_counter = multiprocessing.Value('i', 0)

    # Creating processes
    processes = []
    for _ in range(3):
        p = multiprocessing.Process(target=increment_counter, args=(shared_counter,))
        processes.append(p)
        p.start()

    # Wait for all processes to finish
    for p in processes:
        p.join()

    # Printing the final value of the shared counter
    print("Final value of the shared counter:", shared_counter.value)