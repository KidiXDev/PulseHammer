"""Reporting and presentation helpers."""
from statistics import mean, median, stdev
from .utils import percentile, format_bytes


def print_report(agg, duration):
    total = agg["total"]
    oks = agg["oks"]
    fails = agg["fails"]
    lat = sorted(agg["lat"])
    rps = total / duration if duration > 0 else 0.0
    total_bytes = agg.get("total_bytes", 0)
    throughput_bytes = total_bytes / duration if duration > 0 else 0.0

    lat_min = lat[0] if lat else 0.0
    lat_max = lat[-1] if lat else 0.0
    lat_avg = mean(lat) if lat else 0.0
    lat_median = median(lat) if lat else 0.0
    lat_stdev = stdev(lat) if len(lat) > 1 else 0.0
    p50 = percentile(lat, 50)
    p90 = percentile(lat, 90)
    p95 = percentile(lat, 95)
    p99 = percentile(lat, 99)

    print("\n" + "=" * 60)
    print("== Load Test Report ==")
    print("=" * 60)
    print(f"Total requests      : {total:,}")
    print(f"Duration            : {duration:.3f} s")
    print(f"Throughput          : {rps:.2f} req/s")
    print(f"Data transferred    : {format_bytes(total_bytes)}")
    print(f"Transfer rate       : {format_bytes(throughput_bytes)}/s")
    print(
        f"Success             : {oks:,} ({(oks/total*100 if total else 0):.2f}%)")
    print(
        f"Failures            : {fails:,} ({(fails/total*100 if total else 0):.2f}%)")

    print("\nLatency (seconds):")
    print(
        f"  min/avg/median   : {lat_min:.4f} / {lat_avg:.4f} / {lat_median:.4f}")
    print(f"  max/stdev        : {lat_max:.4f} / {lat_stdev:.4f}")
    print(
        f"  p50/p90/p95/p99  : {p50:.4f} / {p90:.4f} / {p95:.4f} / {p99:.4f}")

    print(f"\nStatus codes:")
    for k in sorted(agg["codes"].keys()):
        print(f"  {k}: {agg['codes'][k]:,}")

    if agg.get("error_types"):
        print(f"\nError types:")
        for err_type, count in sorted(agg["error_types"].items(), key=lambda x: x[1], reverse=True):
            print(f"  {err_type}: {count:,}")

    print("=" * 60)


__all__ = ['print_report']
