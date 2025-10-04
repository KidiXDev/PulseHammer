# PulseHammer

PulseHammer — High-RPS HTTP bench (open-loop, multi-process) with auto-worker sizing.

PulseHammer is a small, fast Python tool to generate sustained HTTP request load (requests/sec) using an open-loop scheduler and multiple worker processes. It focuses on raw throughput and simple, predictable request pacing.

## Features

- Open-loop request scheduling for steady RPS targets
- Multi-process worker model with auto worker sizing
- Per-worker concurrency cap to control in-flight requests
- Minimal dependencies: aiohttp (optional uvloop for faster event loop)
- Simple CLI, prints a concise multi-process report (throughput, success, latency percentiles, status codes)

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

Note: `uvloop` is optional but recommended on supported platforms for better async performance. On Windows, `uvloop` may not be available — PulseHammer will fall back to the built-in event loop.

## Quick usage

Basic example (run for 30s at 15k RPS):

```powershell
python main.py https://api.example.com/health --rps 15000 -D 60 --auto-workers
```

Common example with JSON body and custom header:

```powershell
python main.py https://api.example.com/submit --rps 5000 -D 30 -X POST --json '{"id":123}' -H "Authorization: Bearer TOKEN"
```

If you want to explicitly set the number of worker processes:

```powershell
python main.py https://api.example.com/health --rps 10000 -w 4
```

## CLI options

PulseHammer exposes the following options (shortened):

- url: target URL (positional)
- -X, --method: HTTP method (default: GET)
- -D, --duration: Duration in seconds (default: 30)
- --rps: Target total RPS (required)
- -w, --workers: Number of worker processes (default: auto)
- --auto-workers / --no-auto-workers: Enable/disable auto worker sizing
- -c, --concurrency: Per-worker in-flight cap (default: 256)
- -t, --timeout: Per-request timeout in seconds (default: 10)
- -H, --header: Add header (can be used multiple times)
- --data: Raw body
- --json: JSON body (string)
- --data-file: Read body from file
- --warmup: Warmup request count (excluded from final stats)
- --insecure: Disable TLS verify
- --no-read-body: Do not read full response body (drains minimally)

## Tuning tips

- Per-worker target RPS and concurrency: by default PulseHammer computes a number of workers so that each worker targets ~2500 RPS. You can adjust concurrency (`-c`) to limit in-flight requests per worker if you see connection or resource pressure.
- Use `--no-read-body` if you don't need responses and want less client-side bandwidth/CPU usage. This still attempts to minimally drain the response so connections are reusable.
- If available, install `uvloop` for better event loop performance on non-Windows platforms.
- Start with lower RPS and ramp up while observing the server and network to avoid accidental overload.

## Output

After the run completes, PulseHammer prints a multi-process report with:

- Total requests, duration, throughput (req/s)
- Success/failure counts and percentages
- Latency: min, avg, p50, p90, p95, p99 (seconds)
- Status code distribution

## License

This project includes a `LICENSE` file. The repository is distributed under the terms shown in that file.

## Contributing

Bug reports, small fixes and improvements are welcome. Please open issues or pull requests with a short description and tests where appropriate.
