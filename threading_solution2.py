import sys
import time
import random
import logging
import contextlib
import traceback
import requests

from datetime import datetime
import asyncio
from asyncio import Queue
from queue import Queue as ThreadsafeQueue

import aiohttp
import async_timeout
import threading


# region: DO NOT CHANGE - the code within this region can be assumed to be "correct"

PER_SEC_RATE = 20
DURATION_MS_BETWEEN_REQUESTS = int(1000 / PER_SEC_RATE)
REQUEST_TTL_MS = 1000
VALID_API_KEYS = ['UT4NHL1J796WCHULA1750MXYF9F5JYA6',]
                #   '8TY2F3KIL38T741G1UCBMCAQ75XU9F5O',
                #   '954IXKJN28CBDKHSKHURQIVLQHZIEEM9',
                #   'EUU46ID478HOO7GOXFASKPOZ9P91XGYS',
                #   '46V5EZ5K2DFAGW85J18L50SGO25WJ5JE']


async def generate_requests(queue: Queue):
    """
    co-routine responsible for generating requests

    :param queue:
    :param logger:
    :return:
    """
    curr_req_id = 0
    MAX_SLEEP_MS = 1000 / PER_SEC_RATE / len(VALID_API_KEYS) * 1.05 * 2.0
    while True:
        queue.put_nowait(Request(curr_req_id))
        curr_req_id += 1
        sleep_ms = random.randint(0, int(MAX_SLEEP_MS))
        await asyncio.sleep(sleep_ms / 1000.0)


def timestamp_ms() -> int:
    return int(time.time() * 1000)

# endregion

MAX_LATENCY_MS = 50

def configure_logger(name=None):
    logger = logging.getLogger(name)
    if name is None:
        # only add handlers to root logger
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        logger.addHandler(sh)

        fh = logging.FileHandler(f"async-debug.log", mode="a")
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        logger.setLevel(logging.INFO)
    return logger


class RateLimiterTimeout(Exception):
    pass

class Request:
    def __init__(self, req_id):
        self.req_id = req_id
        self.create_time = timestamp_ms()

class RateLimiter:
    def __init__(self, per_second_rate, min_duration_ms_between_requests):
        self.__per_second_rate = per_second_rate
        self.__min_duration_ms_between_requests = min_duration_ms_between_requests
        self.__last_request_time = 0
        self.__request_times = [0] * per_second_rate
        self.__curr_idx = 0

    @contextlib.asynccontextmanager
    async def acquire(self, timeout_ms=0):
        enter_ms = timestamp_ms()
        while True:
            now = timestamp_ms()
            if now - enter_ms > timeout_ms > 0:
                raise RateLimiterTimeout()

            if now - self.__last_request_time <= self.__min_duration_ms_between_requests:
                await asyncio.sleep(0.001)
                continue

            if now - self.__request_times[self.__curr_idx] <= 1000:
                await asyncio.sleep(0.001)
                continue

            break

        self.__last_request_time = self.__request_times[self.__curr_idx] = now
        self.__curr_idx = (self.__curr_idx + 1) % self.__per_second_rate
        yield self


def request_blocking(url: str, api_key: str, request: Request, session: requests.Session, logger: logging.Logger, nonce: int):
    request = Request(1)
    data = {'api_key': api_key, 'nonce': nonce, 'req_id': request.req_id}
    response = requests.get(url, params=data)
    json = response.json()
    if json['status'] == 'OK':
        logger.info(f"API response: status {response.status_code}, req_id {json['req_id']}")
    else:
        logger.warning(f"API response: status {response.status_code}, resp {json['error_msg']}")

# ttl care and timeout

last_request_time = timestamp_ms()
lock = threading.Lock()

def exchange_facing_worker(url: str, api_key: str, queue: ThreadsafeQueue, logger: logging.Logger, session: requests.Session):
    global last_request_time
    while True:
        lock.acquire()
        request = None
        cd_complete = timestamp_ms() - last_request_time > 50
        if cd_complete and not queue.empty():
            request: Request = queue.get_nowait()
            print("time delta", timestamp_ms() - last_request_time, "req_id", request.req_id)
            last_request_time = timestamp_ms()
        lock.release()

        if request is not None:
            request_blocking(url, api_key, request, session, logger, last_request_time)
        
        time.sleep(0.001)

def exchange_facing_worker2(url: str, api_key: str, queue: ThreadsafeQueue, logger: logging.Logger, session: requests.Session):
    def work():
        global last_request_time
        lock.acquire()
        request = None
        cd_complete = timestamp_ms() - last_request_time > 50
        try_count = try_count + 1
        if cd_complete and not queue.empty():
            print("time delta", timestamp_ms() - last_request_time, "try count", try_count)
            try_count = 0
            request: Request = queue.get_nowait()
            last_request_time = timestamp_ms()
        lock.release()

        if request is not None:
            request_blocking(url, api_key, request, session, logger, last_request_time)

        threading.Timer(0.001, work).start()

    work()

def exchange_facing_worker2(url: str, api_key: str, queue: ThreadsafeQueue, logger: logging.Logger, session: requests.Session):
    def work():
        print("timestamop", timestamp_ms())
        global last_request_time
        lock.acquire()
        request = None
        if not queue.empty() and timestamp_ms() - last_request_time > 25:
            request: Request = queue.get_nowait()
            last_request_time = timestamp_ms()
        lock.release()

        if request is not None:
            request_blocking(url, api_key, request, session, logger, last_request_time)

        desired_wait_time = timestamp_ms() // 50 * 50 + 50 - timestamp_ms()
        print("next deisred time",  timestamp_ms() // 50 * 50 + 50)
        threading.Timer(desired_wait_time / 1000.0, work).start()

    work()

def exchange_facing_worker3(url: str, api_key: str, queue: ThreadsafeQueue, logger: logging.Logger, session: requests.Session):
    while True:
        global last_request_time
        lock.acquire()
        request = None
        if not queue.empty() and timestamp_ms() - last_request_time > 25:
            request: Request = queue.get_nowait()
            last_request_time = timestamp_ms()
        lock.release()

        if request is not None:
            request_blocking(url, api_key, request, session, logger, last_request_time)

async def move_items_async_to_threadsafe(async_queue: Queue, threadsafe_queue: ThreadsafeQueue):
    while True:
        item = await async_queue.get()
        threadsafe_queue.put(item)
        async_queue.task_done()

def main():
    url = "http://127.0.0.1:9999/api/request"
    loop = asyncio.get_event_loop()
    queue = Queue()
    threadsafe_queue = ThreadsafeQueue()

    loop.create_task(move_items_async_to_threadsafe(queue, threadsafe_queue))

    logger = configure_logger()
    loop.create_task(generate_requests(queue=queue))


    for api_key in VALID_API_KEYS:
        session = requests.Session()
        for _ in range(1):
            threading.Thread(target=exchange_facing_worker2, args=(url, api_key, threadsafe_queue, logger, session)).start()
        
    loop.run_forever()


if __name__ == '__main__':
    main()
