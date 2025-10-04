"""CLI parsing and orchestration for PulseHammer."""
import argparse
import math
import os
import time
from multiprocessing import Process, Queue
from . import TOOL_NAME, VERSION, UVLOOP_AVAILABLE
from .worker import bootstrap_worker
from .report import print_report
from .utils import save_to_csv


def build_parser():
    p = argparse.ArgumentParser(
        description=f"{TOOL_NAME} — High-RPS HTTP bench")
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
    p.add_argument("--warmup", type=int, default=0,
                   help="Warmup request count (excluded)")
    p.add_argument("--insecure", action="store_true",
                   help="Disable TLS verify")
    p.add_argument("--csv", help="Export results to CSV file")
    p.add_argument(
        "--html", help="Export results to a self-contained HTML report file")
    p.add_argument("--progress", action="store_true",
                   help="Show real-time progress")
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


def run(args):
    if args.rps <= 0 or args.duration <= 0:
        raise SystemExit("--rps and --duration must be > 0")

    chosen_workers, reason = choose_workers(
        args.auto_workers, args.workers, args.rps, per_worker_target=2500)
    chosen_workers = max(1, int(chosen_workers))

    rps_per_worker = float(args.rps) / float(chosen_workers)
    print(f"{TOOL_NAME} v{VERSION} — High-RPS HTTP bench")
    print("-" * 48)

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

    # Progress display
    stop_progress = None
    if args.progress:
        import threading
        stop_progress = threading.Event()

        def show_progress():
            start = time.perf_counter()
            while not stop_progress.is_set():
                elapsed = time.perf_counter() - start
                remaining = max(0, args.duration - elapsed)
                progress = min(100, (elapsed / args.duration) * 100)
                print(
                    f"\r[Progress] {progress:.1f}% | Elapsed: {elapsed:.1f}s | Remaining: {remaining:.1f}s", end='', flush=True)
                time.sleep(0.5)

        progress_thread = threading.Thread(target=show_progress, daemon=True)
        progress_thread.start()

    agg = {"total": 0, "oks": 0, "fails": 0, "lat": [],
           "codes": {}, "error_types": {}, "total_bytes": 0}
    for _ in range(chosen_workers):
        part = q.get()  # block until worker done
        agg["total"] += part["total"]
        agg["oks"] += part["oks"]
        agg["fails"] += part["fails"]
        agg["lat"].extend(part["lat"])
        agg["total_bytes"] += part.get("total_bytes", 0)
        for k, v in part["codes"].items():
            agg["codes"][k] = agg["codes"].get(k, 0) + v
        for k, v in part.get("error_types", {}).items():
            agg["error_types"][k] = agg["error_types"].get(k, 0) + v

    if stop_progress:
        stop_progress.set()
        print()  # New line after progress

    for p in procs:
        p.join()

    t1 = time.perf_counter()
    actual_duration = args.duration if args.duration > 0 else (t1 - t0)

    print_report(agg, actual_duration)

    if args.csv:
        save_to_csv(agg, actual_duration, args.csv)

    if getattr(args, 'html', None):
        try:
            from .report import save_report_html
            save_report_html(agg, actual_duration, args.html)
        except Exception as e:
            print(f"[Export] Failed to generate HTML report: {e}")


__all__ = ['build_parser', 'choose_workers', 'run']
