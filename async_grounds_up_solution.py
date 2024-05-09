import sys
import time
import random
import logging
import contextlib
import traceback


from datetime import datetime
import asyncio
from asyncio import Queue
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

        logger.setLevel(logging.DEBUG)
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



async def request_sender(url: str, api_key: str, requestf: Request, session: aiohttp.ClientSession, logger: logging.Logger):
    request = await requestf
    nonce = timestamp_ms()
    data = {'api_key': api_key, 'nonce': nonce, 'req_id': request.req_id}
    async with session.request('GET', url, data=data) as resp:
        return await resp.json()

async def response_processor(task, logger: logging.Logger):
    response = await task
    if response['status'] == 'OK':
        logger.info(f"API response: status {response['status']}, resp {response}")
    else:
        logger.warning(f"API response: status {response['status']}, resp {response}")

# ttl care i timeout

def every(delay, task):
  next_time = time.time() + delay
  while True:
    time.sleep(max(0, next_time - time.time()))
    try:
      task()
    except Exception:
      traceback.print_exc()
    next_time += (time.time() - next_time) // delay * delay + delay

async def handle_request(url: str, api_key: str, queue: Queue, logger: logging.Logger, session: aiohttp.ClientSession):
        print("handler request ts", timestamp_ms())
        request_f = queue.get()
        task = asyncio.create_task(request_sender(url, api_key, request_f, session, logger))
        asyncio.create_task(response_processor(task, logger))

def main():
    url = "http://127.0.0.1:9999/api/request"
    loop = asyncio.get_event_loop()
    queue = Queue()

    logger = configure_logger()
    loop.create_task(generate_requests(queue=queue))

    for api_key in VALID_API_KEYS:
        session = aiohttp.ClientSession()
        handler = lambda: loop.create_task(handle_request(url=url, api_key=api_key, queue=queue, logger=logger, session=session))
        threading.Thread(target=lambda: every(0.05, handler)).start()

    loop.run_forever()


if __name__ == '__main__':
    main()
