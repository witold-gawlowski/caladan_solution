import sys
import time
import random
import logging
import contextlib
import traceback
import requests
from collections import defaultdict

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


def request_blocking(url: str, api_key: str, request: Request, session: requests.Session, logger: logging.Logger, nonce: int):
    data = {'api_key': api_key, 'nonce': nonce, 'req_id': request.req_id}
    print("id, nonce, timestamp", request.req_id, nonce, timestamp_ms())
    response = requests.get(url, params=data, stream=False)
    json = response.json()
    if json['status'] == 'OK':
        logger.info(f"API response: status {response.status_code}, req_id {json['req_id']}")
    else:
        logger.warning(f"API response: status {response.status_code}, resp {json['error_msg']}", )

# ttl care and timeout

last_request_times = defaultdict(int)
busy_wait_lock = threading.Lock()

def exchange_facing_worker(url: str, queue: ThreadsafeQueue, logger: logging.Logger, session: requests.Session):
    global last_request_times
    while True:
        busy_wait_lock.acquire()
        free_api_key = None
        request = queue.get()
        current_ts = None
        while free_api_key == None:
            current_ts = timestamp_ms()
            for api_key in VALID_API_KEYS:
                if current_ts - last_request_times[api_key] > 50:
                    free_api_key = api_key
                    print("request time delta", current_ts - last_request_times[api_key])
                    last_request_times[api_key] = current_ts
                    busy_wait_lock.release()
                    break
        
        request_blocking(url, free_api_key, request, session, logger, current_ts)

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

    session = requests.Session()
    for _ in range(2):
        threading.Thread(target=exchange_facing_worker, args=(url, threadsafe_queue, logger, session)).start()
        
    loop.run_forever()


if __name__ == '__main__':
    main()
