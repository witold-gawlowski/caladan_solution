import sys
import time
import random
import logging
import contextlib

import asyncio
from asyncio import Queue
import aiohttp
import async_timeout


# region: DO NOT CHANGE - the code within this region can be assumed to be "correct"

PER_SEC_RATE = 20
DURATION_MS_BETWEEN_REQUESTS = int(1000 / PER_SEC_RATE)
REQUEST_TTL_MS = 1000
WORKERS_PER_KEY = 1
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

        logger.setLevel(logging.DEBUG)
    return logger


class RateLimiterTimeout(Exception):
    pass

class ResponseCounter:
    def __init__(self):
        self.count = 0
        self.start_time = asyncio.get_event_loop().time()

class RateLimiter:
    def __init__(self, per_second_rate, min_duration_ms_between_requests):
        self.__per_second_rate = per_second_rate
        self.__min_duration_ms_between_requests = min_duration_ms_between_requests
        self.__last_request_time = 0
        self.__request_times = [0] * per_second_rate
        self.__curr_idx = 0

    def register(self, send_ts = 0):
        latest_possible_server_register_time = min(send_ts + 50, timestamp_ms()) 
        self.__last_request_time = self.__request_times[self.__curr_idx] = latest_possible_server_register_time
        self.__curr_idx = (self.__curr_idx + 1) % self.__per_second_rate

    @contextlib.asynccontextmanager
    async def acquire(self, timeout_ms=0):
        enter_ms = timestamp_ms()
        while True:
            now = timestamp_ms()
            if now - enter_ms > timeout_ms > 0:
                raise RateLimiterTimeout()

            # if now - self.__last_request_time <= self.__min_duration_ms_between_requests:
            #     await asyncio.sleep(0.001)
            #     continue

            if now - self.__request_times[self.__curr_idx] <= 1000:
                await asyncio.sleep(0.001)
                continue

            break

        yield self

class RateLimiter2:
    def __init__(self, per_second_rate, min_duration_ms_between_requests):
        self.__min_duration_ms_between_requests = min_duration_ms_between_requests
        self.__last_request_time = 0

    def register(self, send_ts):
        latest_possible_server_register_time = min(send_ts + 50, timestamp_ms()) 
        self.__last_request_time =  latest_possible_server_register_time

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

            break
        yield self



async def exchange_facing_worker(url: str, api_key: str, queue: Queue, logger: logging.Logger, limiter: RateLimiter,
                                 lock: asyncio.Lock, counter: ResponseCounter, limiter2: RateLimiter2):
    async with aiohttp.ClientSession() as session:
        while True:
            request: Request = await queue.get()
            remaining_ttl = REQUEST_TTL_MS - (timestamp_ms() - request.create_time)
            if remaining_ttl <= 0:
                logger.warning(f"ignoring request {request.req_id} from queue due to TTL")
                continue
            try:
                # async with limiter2.acquire(timeout_ms=remaining_ttl): # or lock:
                    async with limiter.acquire(timeout_ms=remaining_ttl):
                        async with async_timeout.timeout(1.0):
                                nonce = timestamp_ms()
                                data = {'api_key': api_key, 'nonce': nonce, 'req_id': request.req_id}
                                async with session.request('GET',
                                                        url,
                                                        data=data) as resp:  # type: aiohttp.ClientResponse
                                    json = await resp.json()
                                    limiter.register(nonce)
                                    # limiter2.register(nonce)
                                    if json['status'] == 'OK':
                                        logger.info(f"API response: status {resp.status}, resp {json}")
                                        counter.count = counter.count + 1
                                        print("average counter", counter.count / (asyncio.get_event_loop().time()-counter.start_time))
                                    else:
                                        logger.warning(f"API response: status {resp.status}, resp {json}")
            except RateLimiterTimeout:
                logger.warning(f"ignoring request {request.req_id} in limiter due to TTL")


class Request:
    def __init__(self, req_id):
        self.req_id = req_id
        self.create_time = timestamp_ms()


def main():
    url = "http://127.0.0.1:9999/api/request"
    loop = asyncio.get_event_loop()
    queue = Queue()

    logger = configure_logger()
    loop.create_task(generate_requests(queue=queue))
    counter = ResponseCounter()

    for api_key in VALID_API_KEYS:
        rate_limiter = RateLimiter(PER_SEC_RATE, DURATION_MS_BETWEEN_REQUESTS)
        rate_limiter2 = RateLimiter2(PER_SEC_RATE, DURATION_MS_BETWEEN_REQUESTS)
        lock = asyncio.Lock()
        for _ in range(WORKERS_PER_KEY):
            loop.create_task(exchange_facing_worker(url=url, api_key=api_key, queue=queue, logger=logger, 
                                                    limiter=rate_limiter, lock=lock, counter=counter, limiter2=rate_limiter2))

    loop.run_forever()


if __name__ == '__main__':
    main()
