import random
import time

# Function to generate 200 random numbers and calculate the mean
def test_mean():
    start_time = time.time()  # Start time

    total = 0
    for _ in range(200):
        total += random.randint(0, 50)
        time.sleep(0.01)  # Adding a small delay of 0.001 ms

    end_time = time.time()  # End time

    mean = total / 200  # Calculate the mean
    elapsed_time = (end_time - start_time) * 1000  # Elapsed time in milliseconds
    return mean

# Run the test
mean = test_mean()

print("Mean of 200 random numbers:", mean)
