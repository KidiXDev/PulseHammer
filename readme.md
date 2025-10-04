<p align="center">
    <img src="logo.png" alt="PulseHammer" width="220" style="background-color:#ffffff;padding:8px;border-radius:6px;box-shadow:0 1px 3px rgba(0,0,0,0.08);" />
</p>

<p align="center">
	<img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="License" />
	<img src="https://img.shields.io/badge/python-3.8%20|%203.9%20|%203.10-blue.svg" alt="Python" />
	<img src="https://img.shields.io/badge/status-Experimental-yellow.svg" alt="Status" />
</p>

PulseHammer — High-RPS HTTP bench (open-loop, multi-process) with auto-worker sizing.

PulseHammer is a small, fast Python tool to generate sustained HTTP request load (requests/sec) using an open-loop scheduler and multiple worker processes. It focuses on raw throughput, real data tracking, and provides detailed performance metrics.

## Features

- Open-loop request scheduling for steady RPS targets
- Multi-process worker model with auto worker sizing
- **Real data tracking**: Actual response size, data transfer rates
- **Enhanced error reporting**: Categorized error types (Timeout, Connection, etc.)
- **Advanced statistics**: Median, standard deviation, comprehensive latency percentiles
- **CSV export**: Export detailed results for analysis
- **Real-time progress**: Live progress display during test execution
- Per-worker concurrency cap to control in-flight requests
- Minimal dependencies: aiohttp (optional uvloop for faster event loop)
- Simple CLI, prints comprehensive multi-process reports

## Install

Create a virtualenv and install dependencies (recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Or install only the runtime requirements directly:

```powershell
pip install aiohttp uvloop
```

> Note: `uvloop` is optional but recommended on supported platforms for better async performance. On Windows, `uvloop` may not be available — PulseHammer will fall back to the built-in event loop.

## Quick usage

Basic example (run for 60s at 15k RPS):

```powershell
python pulsehammer.py https://api.example.com/health --rps 15000 -D 60 --auto-workers
```

With real-time progress display:

```powershell
python pulsehammer.py https://api.example.com/health --rps 10000 -D 30 --progress
```

Export results to CSV for analysis:

```powershell
python pulsehammer.py https://api.example.com/api --rps 5000 -D 60 --csv results.csv
```

Common example with JSON body and custom header:

```powershell
python pulsehammer.py https://api.example.com/submit --rps 5000 -D 30 -X POST --json '{"id":123}' -H "Authorization: Bearer TOKEN"
```

Full featured test with progress and CSV export:

```powershell
python pulsehammer.py https://api.example.com/api --rps 10000 -D 120 --progress --csv results.csv -H "Authorization: Bearer TOKEN"
```

If you want to explicitly set the number of worker processes:

```powershell
python pulsehammer.py https://api.example.com/health --rps 10000 -w 4
```

## CLI options

PulseHammer exposes the following options:

- `url`: target URL (positional, required)
- `-X, --method`: HTTP method (default: GET)
- `-D, --duration`: Duration in seconds (default: 30)
- `--rps`: Target total RPS (required)
- `-w, --workers`: Number of worker processes (default: auto)
- `--auto-workers / --no-auto-workers`: Enable/disable auto worker sizing
- `-c, --concurrency`: Per-worker in-flight cap (default: 256)
- `-t, --timeout`: Per-request timeout in seconds (default: 10)
- `-H, --header`: Add header (can be used multiple times)
- `--data`: Raw body
- `--json`: JSON body (string)
- `--warmup`: Warmup request count (excluded from final stats)
- `--insecure`: Disable TLS verify
- `--csv`: Export results to CSV file
- `--progress`: Show real-time progress during test

## Tuning tips

- **Per-worker target RPS and concurrency**: By default PulseHammer computes a number of workers so that each worker targets ~2500 RPS. You can adjust concurrency (`-c`) to limit in-flight requests per worker if you see connection or resource pressure.
- **uvloop**: If available, install `uvloop` for better event loop performance on non-Windows platforms.
- **Gradual ramp-up**: Start with lower RPS and ramp up while observing the server and network to avoid accidental overload.
- **CSV export**: Use `--csv` to export detailed metrics for further analysis in Excel, Google Sheets, or data visualization tools.
- **Progress monitoring**: Use `--progress` to see real-time progress and estimate completion time during long tests.

## Output

After the run completes, PulseHammer prints a comprehensive multi-process report with:

- Total requests, duration, throughput (req/s)
- **Data transferred** and transfer rate (MB/s, GB/s, etc.)
- Success/failure counts and percentages
- **Latency statistics**: min, avg, median, max, standard deviation
- **Latency percentiles**: p50, p90, p95, p99 (seconds)
- Status code distribution
- **Error type breakdown**: Categorized errors (Timeout, ConnectionError, ClientError, etc.)

## License

PulseHammer is licensed under the Apache License 2.0 — see the [LICENSE](LICENSE) file for details.

## Contributing

Bug reports, small fixes and improvements are welcome. Please open issues or pull requests with a short description and tests where appropriate.
