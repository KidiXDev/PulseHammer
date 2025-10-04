"""Reporting and presentation helpers.

Adds console printing and an HTML exporter for modern, shareable reports.
"""
from statistics import mean, median, stdev
from .utils import percentile, format_bytes
import json


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


def save_report_html(agg, duration, filepath):
    """Generate a standalone HTML report with embedded charts and styling.

    The output is a single HTML file (uses Chart.js from CDN). It embeds
    the aggregated metrics and a decimated latency series for plotting.

    Note: This report is still in experimental stage and may evolve.
    """
    try:
        total = agg.get("total", 0)
        oks = agg.get("oks", 0)
        fails = agg.get("fails", 0)
        lat = sorted(agg.get("lat", []))
        total_bytes = agg.get("total_bytes", 0)
        rps = total / duration if duration > 0 else 0.0

        lat_min = lat[0] if lat else 0.0
        lat_max = lat[-1] if lat else 0.0
        lat_avg = mean(lat) if lat else 0.0
        lat_median = median(lat) if lat else 0.0
        lat_stdev = stdev(lat) if len(lat) > 1 else 0.0
        p50 = percentile(lat, 50)
        p90 = percentile(lat, 90)
        p95 = percentile(lat, 95)
        p99 = percentile(lat, 99)

        # Prepare a decimated latency sample for plotting (max 2000 points)
        max_points = 2000
        if len(lat) > max_points:
            step = max(1, len(lat) // max_points)
            lat_sample = lat[::step]
        else:
            lat_sample = lat

        # Calculate histogram data for latency distribution
        histogram_bins = 20
        if lat:
            hist_data = calculate_histogram(lat, histogram_bins)
        else:
            hist_data = {"bins": [], "counts": []}

        payload = {
            "meta": {
                "total": total,
                "oks": oks,
                "fails": fails,
                "duration": duration,
                "rps": rps,
                "total_bytes": total_bytes,
                "throughput_bytes": total_bytes / duration if duration > 0 else 0.0,
                "success_rate": (oks / total * 100) if total else 0,
            },
            "latency": {
                "min": lat_min,
                "max": lat_max,
                "avg": lat_avg,
                "median": lat_median,
                "stdev": lat_stdev,
                "p50": p50,
                "p90": p90,
                "p95": p95,
                "p99": p99,
                "samples": lat_sample,
                "histogram": hist_data,
            },
            "codes": agg.get("codes", {}),
            "error_types": agg.get("error_types", {}),
        }

        data_json = json.dumps(payload)

        # Build status codes table
        codes_rows = ''.join(
            f"<tr><td><span class='status-badge status-{str(k)[0]}xx'>{k}</span></td><td class='count'>{v:,}</td></tr>"
            for k, v in sorted(payload['codes'].items()))

        # Build error types section
        errors_section = ''
        if payload.get('error_types'):
            errors_rows = ''.join(
                f"<tr><td>{k}</td><td class='count'>{v:,}</td></tr>"
                for k, v in sorted(payload['error_types'].items(), key=lambda x: x[1], reverse=True))
            errors_section = '''
                <div class="card">
                    <h3>Error Breakdown</h3>
                    <div class="table-container">
                        <table>
                            <thead><tr><th>Error Type</th><th>Count</th></tr></thead>
                            <tbody>''' + errors_rows + '''</tbody>
                        </table>
                    </div>
                </div>'''

        html_template = """<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>PulseHammer Load Test Report</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            --bg-primary: #0a0e1a;
            --bg-secondary: #0f1629;
            --bg-card: #161d31;
            --bg-card-hover: #1a2238;
            --text-primary: #e8edf4;
            --text-secondary: #9ca8be;
            --text-muted: #6b7a94;
            --accent-primary: #06b6d4;
            --accent-secondary: #0891b2;
            --accent-gradient: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%);
            --success: #10b981;
            --error: #ef4444;
            --warning: #f59e0b;
            --border: rgba(255, 255, 255, 0.06);
            --shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
            --glow: 0 0 20px rgba(6, 182, 212, 0.15);
        }
        
        html, body {
            height: 100%;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
            color: var(--text-primary);
            line-height: 1.6;
            overflow-x: hidden;
        }
        
        body::before {
            content: '';
            position: fixed;
            top: -50%;
            right: -50%;
            width: 100%;
            height: 100%;
            background: radial-gradient(circle, rgba(6, 182, 212, 0.03) 0%, transparent 70%);
            pointer-events: none;
            animation: pulse 15s ease-in-out infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 0.3; }
            50% { opacity: 0.6; }
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 32px 24px;
            position: relative;
            z-index: 1;
        }
        
        .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 32px;
            padding: 24px;
            background: var(--bg-card);
            border-radius: 16px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow);
        }
        
        .header-left h1 {
            font-size: 28px;
            font-weight: 700;
            background: var(--accent-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 4px;
        }
        
        .header-left p {
            color: var(--text-muted);
            font-size: 14px;
        }
        
        .header-right {
            text-align: right;
        }
        
        .duration-label {
            color: var(--text-muted);
            font-size: 13px;
            margin-bottom: 4px;
        }
        
        .duration-value {
            font-size: 32px;
            font-weight: 700;
            color: var(--accent-primary);
        }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 32px;
        }
        
        .metric-card {
            background: var(--bg-card);
            padding: 24px;
            border-radius: 12px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .metric-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: var(--accent-gradient);
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        
        .metric-card:hover {
            transform: translateY(-2px);
            border-color: var(--accent-primary);
            box-shadow: var(--shadow), var(--glow);
        }
        
        .metric-card:hover::before {
            opacity: 1;
        }
        
        .metric-label {
            color: var(--text-secondary);
            font-size: 13px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }
        
        .metric-value {
            font-size: 32px;
            font-weight: 700;
            color: var(--text-primary);
            line-height: 1.2;
        }
        
        .metric-secondary {
            color: var(--text-muted);
            font-size: 13px;
            margin-top: 8px;
        }
        
        .success-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--success);
            margin-right: 6px;
            box-shadow: 0 0 8px var(--success);
        }
        
        .error-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--error);
            margin-right: 6px;
            box-shadow: 0 0 8px var(--error);
        }
        
        .charts-section {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .card {
            background: var(--bg-card);
            padding: 24px;
            border-radius: 12px;
            border: 1px solid var(--border);
            box-shadow: var(--shadow);
        }
        
        .card h3 {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 20px;
            color: var(--text-primary);
        }
        
        .chart-container {
            position: relative;
            height: 300px;
        }
        
        canvas {
            max-height: 100%;
        }
        
        .stats-grid {
            display: grid;
            gap: 16px;
        }
        
        .stat-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            background: var(--bg-secondary);
            border-radius: 8px;
            border: 1px solid var(--border);
        }
        
        .stat-label {
            color: var(--text-secondary);
            font-size: 14px;
            font-weight: 500;
        }
        
        .stat-value {
            color: var(--text-primary);
            font-size: 16px;
            font-weight: 600;
            font-family: 'SF Mono', 'Monaco', 'Courier New', monospace;
        }
        
        .table-container {
            margin-top: 16px;
            overflow-x: auto;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        
        th {
            color: var(--text-secondary);
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        td {
            color: var(--text-primary);
            font-size: 14px;
        }
        
        td.count {
            font-family: 'SF Mono', 'Monaco', 'Courier New', monospace;
            font-weight: 600;
        }
        
        tr:last-child td {
            border-bottom: none;
        }
        
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            font-family: 'SF Mono', 'Monaco', 'Courier New', monospace;
        }
        
        .status-2xx {
            background: rgba(16, 185, 129, 0.15);
            color: var(--success);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }
        
        .status-3xx {
            background: rgba(245, 158, 11, 0.15);
            color: var(--warning);
            border: 1px solid rgba(245, 158, 11, 0.3);
        }
        
        .status-4xx, .status-5xx {
            background: rgba(239, 68, 68, 0.15);
            color: var(--error);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }
        
        .bottom-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .footer {
            text-align: center;
            padding: 24px;
            color: var(--text-muted);
            font-size: 13px;
            background: var(--bg-card);
            border-radius: 12px;
            border: 1px solid var(--border);
        }
        
        .footer a {
            color: var(--accent-primary);
            text-decoration: none;
            transition: color 0.3s ease;
        }
        
        .footer a:hover {
            color: var(--accent-secondary);
        }
        
        @media (max-width: 1024px) {
            .charts-section {
                grid-template-columns: 1fr;
            }
            .bottom-grid {
                grid-template-columns: 1fr;
            }
        }
        
        @media (max-width: 768px) {
            .header {
                flex-direction: column;
                text-align: center;
            }
            .header-right {
                text-align: center;
                margin-top: 16px;
            }
            .metrics-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-left">
                <h1>PulseHammer Bench Test Report</h1>
                <p>Performance analysis and metrics</p>
            </div>
            <div class="header-right">
                <div class="duration-label">Test Duration</div>
                <div class="duration-value">__DURATION__s</div>
            </div>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Total Requests</div>
                <div class="metric-value">__TOTAL__</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Throughput</div>
                <div class="metric-value">__RPS__</div>
                <div class="metric-secondary">requests per second</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Data Transferred</div>
                <div class="metric-value">__TOTAL_BYTES__</div>
                <div class="metric-secondary">__THROUGHPUT__ per second</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Success Rate</div>
                <div class="metric-value">__SUCCESS_RATE__%</div>
                <div class="metric-secondary">
                    <span class="success-indicator"></span>__OKS__ success
                    <span style="margin: 0 8px">|</span>
                    <span class="error-indicator"></span>__FAILS__ failed
                </div>
            </div>
        </div>

        <div class="charts-section">
            <div class="card">
                <h3>📈 Latency Over Time</h3>
                <div class="chart-container">
                    <canvas id="latencyChart"></canvas>
                </div>
            </div>
            <div class="card">
                <h3>📊 Latency Statistics</h3>
                <div class="stats-grid">
                    <div class="stat-row">
                        <span class="stat-label">Minimum</span>
                        <span class="stat-value">__LAT_MIN__s</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Average</span>
                        <span class="stat-value">__LAT_AVG__s</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Median</span>
                        <span class="stat-value">__LAT_MED__s</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Maximum</span>
                        <span class="stat-value">__LAT_MAX__s</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Std Deviation</span>
                        <span class="stat-value">__LAT_STDEV__s</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">P50 (Median)</span>
                        <span class="stat-value">__LAT_P50__s</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">P90</span>
                        <span class="stat-value">__LAT_P90__s</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">P95</span>
                        <span class="stat-value">__LAT_P95__s</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">P99</span>
                        <span class="stat-value">__LAT_P99__s</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="bottom-grid">
            <div class="card">
                <h3>📉 Latency Distribution</h3>
                <div class="chart-container">
                    <canvas id="histogramChart"></canvas>
                </div>
            </div>
            <div class="card">
                <h3>🎯 Status Codes</h3>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Code</th>
                                <th>Count</th>
                            </tr>
                        </thead>
                        <tbody>
                            __CODES_TABLE__
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        __ERRORS_SECTION__

        <div class="footer">
            Generated by <strong>PulseHammer</strong> — High-performance load testing tool
        </div>
    </div>

    <script>
        const data = __DATA_JSON__;

        // Latency over time chart
        const ctxLatency = document.getElementById('latencyChart').getContext('2d');
        const samples = (data && data.latency && data.latency.samples) || [];
        const labels = samples.map((_, i) => i + 1);

        new Chart(ctxLatency, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Latency (s)',
                    data: samples,
                    borderColor: '#06b6d4',
                    backgroundColor: 'rgba(6, 182, 212, 0.1)',
                    pointRadius: 0,
                    borderWidth: 2,
                    tension: 0.2,
                    fill: true,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index',
                },
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Request Sequence',
                            color: '#9ca8be',
                        },
                        ticks: { color: '#6b7a94' },
                        grid: { color: 'rgba(255, 255, 255, 0.03)' }
                    },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Latency (seconds)',
                            color: '#9ca8be',
                        },
                        ticks: { color: '#6b7a94' },
                        grid: { color: 'rgba(255, 255, 255, 0.03)' }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 22, 41, 0.95)',
                        titleColor: '#e8edf4',
                        bodyColor: '#9ca8be',
                        borderColor: '#06b6d4',
                        borderWidth: 1,
                        padding: 12,
                        displayColors: false,
                        callbacks: {
                            label: function(context) {
                                return 'Latency: ' + context.parsed.y.toFixed(4) + 's';
                            }
                        }
                    }
                }
            }
        });

        // Histogram chart
        const ctxHist = document.getElementById('histogramChart').getContext('2d');
        const histogram = (data && data.latency && data.latency.histogram) || { bins: [], counts: [] };

        new Chart(ctxHist, {
            type: 'bar',
            data: {
                labels: histogram.bins.map(b => b.toFixed(3) + 's'),
                datasets: [{
                    label: 'Request Count',
                    data: histogram.counts,
                    backgroundColor: 'rgba(6, 182, 212, 0.6)',
                    borderColor: '#06b6d4',
                    borderWidth: 1,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: 'Latency Range',
                            color: '#9ca8be',
                        },
                        ticks: { color: '#6b7a94' },
                        grid: { color: 'rgba(255, 255, 255, 0.03)' }
                    },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Frequency',
                            color: '#9ca8be',
                        },
                        ticks: { color: '#6b7a94' },
                        grid: { color: 'rgba(255, 255, 255, 0.03)' }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15, 22, 41, 0.95)',
                        titleColor: '#e8edf4',
                        bodyColor: '#9ca8be',
                        borderColor: '#06b6d4',
                        borderWidth: 1,
                        padding: 12,
                        displayColors: false,
                    }
                }
            }
        });
    </script>
</body>
</html>"""

        # Replace tokens with computed values
        html = html_template.replace('__DURATION__', f"{duration:.3f}")
        html = html.replace('__TOTAL__', f"{payload['meta']['total']:,}")
        html = html.replace('__RPS__', f"{payload['meta']['rps']:.2f}")
        html = html.replace('__TOTAL_BYTES__', format_bytes(
            payload['meta']['total_bytes']))
        html = html.replace('__THROUGHPUT__', format_bytes(
            payload['meta']['throughput_bytes']))
        html = html.replace('__SUCCESS_RATE__',
                            f"{payload['meta']['success_rate']:.1f}")
        html = html.replace('__OKS__', f"{payload['meta']['oks']:,}")
        html = html.replace('__FAILS__', f"{payload['meta']['fails']:,}")
        html = html.replace('__LAT_MIN__', f"{payload['latency']['min']:.4f}")
        html = html.replace('__LAT_AVG__', f"{payload['latency']['avg']:.4f}")
        html = html.replace(
            '__LAT_MED__', f"{payload['latency']['median']:.4f}")
        html = html.replace('__LAT_MAX__', f"{payload['latency']['max']:.4f}")
        html = html.replace(
            '__LAT_STDEV__', f"{payload['latency']['stdev']:.4f}")
        html = html.replace('__LAT_P50__', f"{payload['latency']['p50']:.4f}")
        html = html.replace('__LAT_P90__', f"{payload['latency']['p90']:.4f}")
        html = html.replace('__LAT_P95__', f"{payload['latency']['p95']:.4f}")
        html = html.replace('__LAT_P99__', f"{payload['latency']['p99']:.4f}")
        html = html.replace('__CODES_TABLE__', codes_rows)
        html = html.replace('__ERRORS_SECTION__', errors_section)
        html = html.replace('__DATA_JSON__', data_json)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"\n[Export] HTML report saved to: {filepath}")
    except Exception as e:
        print(f"\n[Export] Failed to save HTML report: {e}")


def calculate_histogram(data, bins=20):
    """Calculate histogram bins and counts for latency distribution."""
    if not data:
        return {"bins": [], "counts": []}

    min_val = min(data)
    max_val = max(data)
    bin_width = (max_val - min_val) / bins if max_val > min_val else 1

    bin_edges = [min_val + i * bin_width for i in range(bins + 1)]
    counts = [0] * bins
    bin_centers = []

    for value in data:
        for i in range(bins):
            if i == bins - 1:
                if bin_edges[i] <= value <= bin_edges[i + 1]:
                    counts[i] += 1
                    break
            else:
                if bin_edges[i] <= value < bin_edges[i + 1]:
                    counts[i] += 1
                    break

    for i in range(bins):
        bin_centers.append((bin_edges[i] + bin_edges[i + 1]) / 2)

    return {"bins": bin_centers, "counts": counts}
