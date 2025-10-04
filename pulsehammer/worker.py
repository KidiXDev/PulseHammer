"""Worker implementation for open-loop request generation."""
from dataclasses import dataclass
import asyncio
import time
from collections import defaultdict
import aiohttp
from . import UVLOOP_AVAILABLE, uvloop
from .utils import parse_headers


@dataclass
class Result:
    ok: bool
    status: int | None
    start: float
    end: float
    response_bytes: int
    error: str | None
    error_type: str | None


async def do_request(session, method, url, timeout, payload, verify_ssl):
    start = time.perf_counter()
    try:
        async with session.request(method, url, data=payload, timeout=timeout, ssl=verify_ssl) as resp:
            body = await resp.read()
            end = time.perf_counter()
            body_size = len(body) if body else 0
            return Result(
                ok=200 <= resp.status < 400,
                status=resp.status,
                start=start,
                end=end,
                response_bytes=body_size,
                error=None,
                error_type=None
            )
    except asyncio.TimeoutError:
        end = time.perf_counter()
        return Result(False, None, start, end, 0, "Timeout", "Timeout")
    except aiohttp.ClientConnectorError as e:
        end = time.perf_counter()
        return Result(False, None, start, end, 0, str(e), "ConnectionError")
    except aiohttp.ClientError as e:
        end = time.perf_counter()
        return Result(False, None, start, end, 0, str(e), "ClientError")
    except Exception as e:
        end = time.perf_counter()
        return Result(False, None, start, end, 0, str(e), "UnknownError")


async def worker_open_loop(args, rps_per_worker, out_q):
    if UVLOOP_AVAILABLE:
        # uvloop installed in process bootstrap
        pass

    timeout = aiohttp.ClientTimeout(total=args.timeout)
    headers = parse_headers(args.header)
    payload = None
    if args.data is not None:
        payload = args.data.encode()
    if args.json is not None:
        headers.setdefault("Content-Type", "application/json")
        payload = __import__('json').loads(args.json).encode(
        ) if isinstance(args.json, str) else args.json

    connector = aiohttp.TCPConnector(limit=0, enable_cleanup_closed=True)
    sem = asyncio.Semaphore(args.concurrency)

    results = []
    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        # warmup
        for _ in range(args.warmup):
            _ = await do_request(session, args.method, args.url, timeout, payload, not args.insecure)
        results.clear()

        interval = 1.0 / max(1.0, rps_per_worker)
        deadline = time.perf_counter() + args.duration
        next_fire = time.perf_counter()
        pending = set()

        async def spawn():
            async with sem:
                res = await do_request(session, args.method, args.url, timeout, payload, not args.insecure)
                results.append(res)

        # scheduler loop
        while True:
            now = time.perf_counter()
            if now >= deadline:
                break
            if now >= next_fire:
                task = asyncio.create_task(spawn())
                pending.add(task)
                task.add_done_callback(pending.discard)
                next_fire += interval
            else:
                # small sleep to avoid busy spin
                await asyncio.sleep(min(0.001, next_fire - now))

        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    # aggregate compact stats for IPC
    oks = sum(1 for r in results if r.ok)
    total = len(results)
    lat = sorted([(r.end - r.start) for r in results if r.status is not None])
    codes = {}
    fails = total - oks
    error_types = defaultdict(int)
    total_bytes = sum(r.response_bytes for r in results)

    for r in results:
        code = str(r.status) if r.status is not None else "ERR"
        codes[code] = codes.get(code, 0) + 1
        if r.error_type:
            error_types[r.error_type] += 1

    out_q.put({
        "total": total,
        "oks": oks,
        "fails": fails,
        "lat": lat,
        "codes": codes,
        "error_types": dict(error_types),
        "total_bytes": total_bytes,
    })


def bootstrap_worker(args, rps_per_worker, out_q):
    # Ensure the uvloop module object is present before calling install()
    if UVLOOP_AVAILABLE and uvloop is not None:
        uvloop.install()
    asyncio.run(worker_open_loop(args, rps_per_worker, out_q))


__all__ = [
    'Result', 'worker_open_loop', 'bootstrap_worker'
]
