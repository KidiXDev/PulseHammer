"""Utility helpers for PulseHammer."""
from collections import defaultdict
import json as jsonlib
import csv
import sys
from statistics import mean, median, stdev


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


def format_bytes(bytes_count):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.2f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.2f} TB"


def save_to_csv(agg, duration, filepath):
    """Save detailed results to CSV file."""
    try:
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Metric', 'Value'])
            writer.writerow(['Total Requests', agg['total']])
            writer.writerow(['Duration (s)', f"{duration:.3f}"])
            writer.writerow(
                ['Throughput (req/s)', f"{agg['total']/duration:.2f}"])
            writer.writerow(['Success', agg['oks']])
            writer.writerow(['Failures', agg['fails']])
            writer.writerow(
                ['Success Rate (%)', f"{(agg['oks']/agg['total']*100 if agg['total'] else 0):.2f}"])
            writer.writerow(['Total Bytes', agg.get('total_bytes', 0)])

            lat = sorted(agg['lat'])
            if lat:
                writer.writerow(['Latency Min (s)', f"{lat[0]:.4f}"])
                writer.writerow(['Latency Avg (s)', f"{mean(lat):.4f}"])
                writer.writerow(['Latency Median (s)', f"{median(lat):.4f}"])
                writer.writerow(['Latency Max (s)', f"{lat[-1]:.4f}"])
                writer.writerow(
                    ['Latency StdDev (s)', f"{stdev(lat) if len(lat) > 1 else 0:.4f}"])
                writer.writerow(
                    ['Latency P50 (s)', f"{percentile(lat, 50):.4f}"])
                writer.writerow(
                    ['Latency P90 (s)', f"{percentile(lat, 90):.4f}"])
                writer.writerow(
                    ['Latency P95 (s)', f"{percentile(lat, 95):.4f}"])
                writer.writerow(
                    ['Latency P99 (s)', f"{percentile(lat, 99):.4f}"])

            writer.writerow([])
            writer.writerow(['Status Code', 'Count'])
            for code, count in sorted(agg['codes'].items()):
                writer.writerow([code, count])

            if agg.get('error_types'):
                writer.writerow([])
                writer.writerow(['Error Type', 'Count'])
                for err_type, count in sorted(agg['error_types'].items()):
                    writer.writerow([err_type, count])

        print(f"\n[Export] Results saved to: {filepath}")
    except Exception as e:
        print(f"\n[Export] Failed to save CSV: {e}", file=sys.stderr)


__all__ = [
    'parse_headers', 'percentile', 'format_bytes', 'save_to_csv'
]
