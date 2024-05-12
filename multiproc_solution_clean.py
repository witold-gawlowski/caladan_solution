import sys
import time
import random
import logging
import requests
from collections import defaultdict
import multiprocessing

from datetime import datetime
import asyncio
from asyncio import Queue
from multiprocessing import Queue as MPQueue
from multiprocessing import Lock


# region: DO NOT CHANGE - the code within this region can be assumed to be "correct"

PER_SEC_RATE = 20
DURATION_MS_BETWEEN_REQUESTS = int(1000 / PER_SEC_RATE)
REQUEST_TTL_MS = 1000
VALID_API_KEYS = ['UT4NHL1J796WCHULA1750MXYF9F5JYA6',
                  '8TY2F3KIL38T741G1UCBMCAQ75XU9F5O',
                  '954IXKJN28CBDKHSKHURQIVLQHZIEEM9',
                  'EUU46ID478HOO7GOXFASKPOZ9P91XGYS',
                  '46V5EZ5K2DFAGW85J18L50SGO25WJ5JE']


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
    response = session.get(url, params=data)
    json = response.json()
    if json['status'] == 'OK':
        logger.info(f"API response: status {response.status_code}, req_id {json['req_id']}")
    else:
        logger.warning(f"API response: status {response.status_code}, resp {json['error_msg']}", )

# ttl care and timeout

def exchange_facing_worker(url: str, queue: MPQueue, busy_wait_lock: multiprocessing.Lock,
                           last_request_times):
    session = requests.Session()
    logger = configure_logger()
    while True:
        busy_wait_lock.acquire()
        free_api_key = None
        request = queue.get()
        current_ts = None
        while free_api_key == None:
            current_ts = time.time() * 1000
            for api_key in VALID_API_KEYS:
                if current_ts - last_request_times[api_key] >= 52.5:

                    free_api_key = api_key
                    last_request_times[api_key] = current_ts
                    busy_wait_lock.release()
                    break
        request_blocking(url, free_api_key, request, session, logger, int(current_ts))


async def move_items_to_multiproc_queue(async_queue: Queue, mp_queue: MPQueue):
    while True:
        item = await async_queue.get()
        mp_queue.put(item)
        async_queue.task_done()

def main():
    url = "http://127.0.0.1:9999/api/request"
    loop = asyncio.get_event_loop()
    queue = Queue()
    threadsafe_queue = MPQueue()

    loop.create_task(move_items_to_multiproc_queue(queue, threadsafe_queue))

    loop.create_task(generate_requests(queue=queue))

    # makes sure that only one process at a time waits in a busy way
    busy_wait_lock = multiprocessing.Lock()

    manager = multiprocessing.Manager()
    last_request_times = manager.dict()
    for api_key in VALID_API_KEYS:
        last_request_times[api_key] = 0
        
    for _ in range(15):
        multiprocessing.Process(target=exchange_facing_worker, args=(url, threadsafe_queue, busy_wait_lock, last_request_times)).start()
    loop.run_forever()


if __name__ == '__main__':
    main()
