"""
PulseHammer — High-RPS HTTP bench (open-loop, multi-process) with auto-worker sizing.

Usage example:
    python main.py https://api.example.com/health --rps 15000 -D 60 --auto-workers

Dependencies:
    pip install aiohttp uvloop
"""
import aiohttp
import argparse
import asyncio
import json as jsonlib
import math
import os
import sys
import time
from dataclasses import dataclass
from multiprocessing import Process, Queue
from statistics import mean

uvloop = None
try:
    import uvloop as _uvloop  # type: ignore
    uvloop = _uvloop
    UVLOOP_AVAILABLE = True
except Exception:
    UVLOOP_AVAILABLE = False

    # Tool identity
    TOOL_NAME = "PulseHammer"
    VERSION = "0.1.0"

    def print_banner() -> None:
        """Print a short startup banner with name and version."""
        print(f"{TOOL_NAME} v{VERSION} — High-RPS HTTP bench")
        print("-" * 48)


# ---------------------------
# Data & helpers
# ---------------------------


@dataclass
class Result:
    ok: bool
    status: int | None
    start: float
    end: float
    bytes: int
    error: str | None


def parse_headers(hlist):
    headers = {}
    for item in hlist or []:
        if ":" not in item:
            raise ValueError(f"Invalid header '{item}', expected 'Key: Value'")
        k, v = item.split(":", 1)
        headers[k.strip()] = v.strip()
    return headers


def percentile(sorted_values, p):
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    d0 = sorted_values[f] * (c - k)
    d1 = sorted_values[c] * (k - f)
    return d0 + d1

# ---------------------------
# HTTP request worker (open-loop)
# ---------------------------


async def do_request(session, method, url, timeout, payload, verify_ssl, read_body):
    start = time.perf_counter()
    try:
        async with session.request(method, url, data=payload, timeout=timeout, ssl=verify_ssl) as resp:
            if read_body:
                await resp.read()
            else:
                # Try to minimally drain the response to free the connection
                try:
                    if resp.content_length and resp.content_length > 0:
                        await resp.content.readexactly(min(resp.content_length, 1))
                except Exception:
                    # ignore partial read errors - we don't need body in no-read mode
                    pass
            end = time.perf_counter()
            return Result(True if 200 <= resp.status < 400 else False, resp.status, start, end, 0, None)
    except Exception as e:
        end = time.perf_counter()
        return Result(False, None, start, end, 0, str(e))


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
        payload = jsonlib.dumps(jsonlib.loads(args.json)).encode()
    if args.data_file is not None:
        payload = open(args.data_file, "rb").read()

    connector = aiohttp.TCPConnector(limit=0, enable_cleanup_closed=True)
    sem = asyncio.Semaphore(args.concurrency)

    results = []
    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        # warmup
        for _ in range(args.warmup):
            _ = await do_request(session, args.method, args.url, timeout, payload, not args.insecure, not args.no_read_body)
        results.clear()

        interval = 1.0 / max(1.0, rps_per_worker)
        deadline = time.perf_counter() + args.duration
        next_fire = time.perf_counter()
        pending = set()

        async def spawn():
            async with sem:
                res = await do_request(session, args.method, args.url, timeout, payload, not args.insecure, not args.no_read_body)
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
    for r in results:
        code = str(r.status) if r.status is not None else "ERR"
        codes[code] = codes.get(code, 0) + 1
    out_q.put({
        "total": total,
        "oks": oks,
        "fails": fails,
        "lat": lat,
        "codes": codes,
    })


def bootstrap_worker(args, rps_per_worker, out_q):
    # Ensure the uvloop module object is present before calling install()
    if UVLOOP_AVAILABLE and uvloop is not None:
        uvloop.install()
    asyncio.run(worker_open_loop(args, rps_per_worker, out_q))

# ---------------------------
# Reporting
# ---------------------------


def print_report(agg, duration):
    total = agg["total"]
    oks = agg["oks"]
    fails = agg["fails"]
    lat = sorted(agg["lat"])
    rps = total / duration if duration > 0 else 0.0

    lat_min = lat[0] if lat else 0.0
    lat_max = lat[-1] if lat else 0.0
    lat_avg = mean(lat) if lat else 0.0
    p50 = percentile(lat, 50)
    p90 = percentile(lat, 90)
    p95 = percentile(lat, 95)
    p99 = percentile(lat, 99)

    print("\n== Load Test Report ==")
    print(f"Total requests : {total}")
    print(f"Duration       : {duration:.3f} s")
    print(f"Throughput     : {rps:.2f} req/s")
    print(f"Success        : {oks} ({(oks/total*100 if total else 0):.2f}%)")
    print(
        f"Failures       : {fails} ({(fails/total*100 if total else 0):.2f}%)")
    print("\nLatency (s):")
    print(f"  min/avg/p50  : {lat_min:.4f} / {lat_avg:.4f} / {p50:.4f}")
    print(f"  p90/p95/p99  : {p90:.4f} / {p95:.4f} / {p99:.4f}")
    print(f"\nStatus codes:")
    for k in sorted(agg["codes"].keys()):
        print(f"  {k}: {agg['codes'][k]}")

# ---------------------------
# CLI & auto-workers logic
# ---------------------------


def build_parser():
    p = argparse.ArgumentParser(
        description="PulseHammer — High-RPS HTTP bench")
    p.add_argument("url")
    p.add_argument("-X", "--method", default="GET")
    p.add_argument("-D", "--duration", type=float, default=30.0,
                   help="Duration seconds (default: 30)")
    p.add_argument("--rps", type=int, required=True,
                   help="Target total RPS (open-loop)")
    p.add_argument("-w", "--workers", type=int, default=0,
                   help="Processes (default: auto)")
    p.add_argument("--auto-workers", dest="auto_workers",
                   action="store_true", help="Enable auto worker sizing (default)")
    p.add_argument("--no-auto-workers", dest="auto_workers",
                   action="store_false", help="Disable auto worker sizing")
    p.set_defaults(auto_workers=True)
    p.add_argument("-c", "--concurrency", type=int, default=256,
                   help="Per-worker in-flight cap (default: 256)")
    p.add_argument("-t", "--timeout", type=float,
                   default=10.0, help="Per-request timeout")
    p.add_argument("-H", "--header", action="append",
                   default=[], help='-H "Key: Value"')
    p.add_argument("--data", help="Raw body")
    p.add_argument("--json", help="JSON body (string)")
    p.add_argument("--data-file", help="Read body from file")
    p.add_argument("--warmup", type=int, default=0,
                   help="Warmup request count (excluded)")
    p.add_argument("--insecure", action="store_true",
                   help="Disable TLS verify")
    p.add_argument("--no-read-body", action="store_true",
                   help="Do not read full response body")
    return p


def choose_workers(auto_enabled: bool, requested_workers: int, rps: int, per_worker_target: int = 2500):
    """
    Heuristic:
      - base = ceil(rps / per_worker_target)
      - cap to cpu_count * 2 (avoid extreme spawn)
      - if user passed --workers (>0), respect it
    """
    if requested_workers and requested_workers > 0:
        return requested_workers, "manual"

    cpu_count = os.cpu_count() or 1
    base = max(1, math.ceil(rps / float(per_worker_target)))
    cap = max(1, cpu_count * 2)
    chosen = min(base, cap) if auto_enabled else max(1, cpu_count)
    reason = f"auto (rps/{per_worker_target} -> base={base}, cap={cap}, cpu={cpu_count})" if auto_enabled else "fallback cpu_count"
    return chosen, reason


def main():
    args = build_parser().parse_args()
    if args.rps <= 0 or args.duration <= 0:
        print("--rps and --duration must be > 0", file=sys.stderr)
        sys.exit(2)

    # auto-workers decision
    chosen_workers, reason = choose_workers(
        args.auto_workers, args.workers, args.rps, per_worker_target=2500)
    # sanity floor
    chosen_workers = max(1, int(chosen_workers))

    rps_per_worker = float(args.rps) / float(chosen_workers)
    # print a concise banner
    print_banner()

    print(f"[PulseHammer] target RPS={args.rps}, duration={args.duration}s")
    print(
        f"[PulseHammer] workers chosen={chosen_workers} ({reason}), per-worker target RPS≈{rps_per_worker:.1f}")
    print(
        f"[PulseHammer] per-worker concurrency cap={args.concurrency}, uvloop={'yes' if UVLOOP_AVAILABLE else 'no'}")
    print("[PulseHammer] starting... (Ctrl+C to stop)")

    procs = []
    q = Queue()

    t0 = time.perf_counter()
    for _ in range(chosen_workers):
        p = Process(target=bootstrap_worker, args=(
            args, rps_per_worker, q), daemon=True)
        p.start()
        procs.append(p)

    agg = {"total": 0, "oks": 0, "fails": 0, "lat": [], "codes": {}}
    for _ in range(chosen_workers):
        part = q.get()  # block until worker done
        agg["total"] += part["total"]
        agg["oks"] += part["oks"]
        agg["fails"] += part["fails"]
        agg["lat"].extend(part["lat"])
        for k, v in part["codes"].items():
            agg["codes"][k] = agg["codes"].get(k, 0) + v

    for p in procs:
        p.join()

    t1 = time.perf_counter()
    print_report(agg, args.duration if args.duration > 0 else (t1 - t0))


if __name__ == "__main__":
    main()
