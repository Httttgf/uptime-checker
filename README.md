# Uptime Checker

A Python service for monitoring the availability of multiple websites. Lightweight, configurable, and easily extensible with custom alerting.

## Features

- **Multi-site monitoring**: Check multiple websites from a single configuration file
- **Flexible configuration**: Support for both JSON and YAML config formats
- **Configurable timeouts**: Set default or per-site timeout values
- **Response time tracking**: Measure and log response times in milliseconds
- **Status change detection**: Detect when sites go down or recover
- **Extensible alerting**: Easy-to-implement alert handlers for various notification systems
- **Continuous monitoring**: Run as a daemon with configurable check intervals
- **Structured logging**: Output to both console and log file

## Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/uptime-checker.git
cd uptime-checker

# Install dependencies
pip install -r requirements.txt
```

## Configuration

Create a configuration file (YAML or JSON). See `config.example.yaml` for a template:

```yaml
# config.yaml
default_timeout: 10

sites:
  # Simple format - just URLs
  - https://www.google.com
  - https://www.github.com
  
  # Detailed format with custom settings
  - url: https://api.example.com/health
    name: "Example API"
    timeout: 5
    expected_status: 200
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `default_timeout` | Default timeout for all sites (seconds) | 10 |
| `sites[].url` | URL to monitor (required) | - |
| `sites[].name` | Display name for the site | URL hostname |
| `sites[].timeout` | Timeout for this site (seconds) | `default_timeout` |
| `sites[].expected_status` | Expected HTTP status code | 200 |

## Usage

### Run once (check all sites and exit)

```bash
python uptime_checker.py --config config.yaml --once
```

Output:
```json
[
  {
    "url": "https://www.google.com",
    "status": "up",
    "status_code": 200,
    "response_time_ms": 156.23,
    "error_message": null,
    "timestamp": "2024-01-15T10:30:00.123456"
  }
]
```

### Continuous monitoring

```bash
# Default interval: 60 seconds
python uptime_checker.py --config config.yaml

# Custom interval: 30 seconds
python uptime_checker.py --config config.yaml --interval 30
```

### Command-line options

| Option | Description | Default |
|--------|-------------|---------|
| `-c`, `--config` | Path to configuration file | `config.yaml` |
| `-i`, `--interval` | Check interval in seconds | 60 |
| `--once` | Run once and exit | False |

## Adding Custom Alerts

The service is designed to be easily extended with custom alert handlers. See `alert_handlers.py` for examples.

### Creating a custom handler

```python
from uptime_checker import AlertHandler, CheckResult, UptimeChecker

class MyCustomAlertHandler(AlertHandler):
    def on_status_change(self, result: CheckResult, previous_status: str | None) -> None:
        if result.status == 'down':
            # Send alert: site is down
            print(f"ALERT: {result.url} is down!")
        elif result.status == 'up' and previous_status == 'down':
            # Send recovery notification
            print(f"RECOVERED: {result.url} is back up!")
    
    def on_check_complete(self, result: CheckResult) -> None:
        # Called after every check (optional)
        pass

# Use it
checker = UptimeChecker('config.yaml')
checker.add_alert_handler(MyCustomAlertHandler())
checker.run_continuous()
```

### Built-in alert handlers (in alert_handlers.py)

- **EmailAlertHandler**: Send emails via SMTP
- **SlackAlertHandler**: Post to Slack via webhook
- **DiscordAlertHandler**: Post to Discord via webhook
- **PagerDutyAlertHandler**: Create/resolve PagerDuty incidents
- **FileAlertHandler**: Log results to a JSONL file

## Programmatic Usage

```python
from uptime_checker import UptimeChecker, SiteConfig

# From config file
checker = UptimeChecker('config.yaml')

# Check all sites
results = checker.check_all()
for result in results:
    print(f"{result.url}: {result.status} ({result.response_time_ms}ms)")

# Check a single site
from uptime_checker import SiteConfig
site = SiteConfig(url="https://example.com", timeout=5)
result = checker.check_site(site)
```

## Log Output

Logs are written to both stdout and `uptime.log`:

```
2024-01-15 10:30:00,123 - INFO - Checking google.com (https://www.google.com)...
2024-01-15 10:30:00,280 - INFO -   ✓ google.com: UP - HTTP 200 in 156.23ms
2024-01-15 10:30:00,281 - INFO - Checking api.example.com (https://api.example.com/health)...
2024-01-15 10:30:05,285 - WARNING -   ✗ api.example.com: DOWN - Timeout after 5s
2024-01-15 10:30:05,286 - WARNING - ALERT: https://api.example.com/health is DOWN!
```

## Running as a Service

### Using systemd (Linux)

Create `/etc/systemd/system/uptime-checker.service`:

```ini
[Unit]
Description=Uptime Checker Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/uptime-checker
ExecStart=/usr/bin/python3 /opt/uptime-checker/uptime_checker.py -c /opt/uptime-checker/config.yaml -i 60
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable uptime-checker
sudo systemctl start uptime-checker
```

### Using Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "uptime_checker.py", "-c", "config.yaml"]
```

## License

MIT License
