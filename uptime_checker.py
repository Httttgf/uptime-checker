#!/usr/bin/env python3
"""
Uptime Checker - Web availability monitoring service
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

import requests
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('uptime.log')
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """Result of a site availability check."""
    url: str
    status: str  # 'up', 'down', 'error'
    status_code: Optional[int]
    response_time_ms: Optional[float]
    error_message: Optional[str]
    timestamp: datetime

    def to_dict(self) -> dict:
        return {
            'url': self.url,
            'status': self.status,
            'status_code': self.status_code,
            'response_time_ms': self.response_time_ms,
            'error_message': self.error_message,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class SiteConfig:
    """Configuration for a site to monitor."""
    url: str
    name: Optional[str] = None
    timeout: Optional[float] = None
    expected_status: int = 200
    
    @property
    def display_name(self) -> str:
        return self.name or urlparse(self.url).netloc


class AlertHandler:
    """Base class for alert handlers. Extend this to add custom alerting."""
    
    def on_status_change(self, result: CheckResult, previous_status: Optional[str]) -> None:
        """Called when a site's status changes (up -> down or down -> up)."""
        pass
    
    def on_check_complete(self, result: CheckResult) -> None:
        """Called after every check, regardless of status."""
        pass


class LoggingAlertHandler(AlertHandler):
    """Default alert handler that logs status changes."""
    
    def on_status_change(self, result: CheckResult, previous_status: Optional[str]) -> None:
        if result.status == 'down':
            logger.warning(
                f"ALERT: {result.url} is DOWN! "
                f"Previous status: {previous_status}, "
                f"Error: {result.error_message or f'HTTP {result.status_code}'}"
            )
        elif result.status == 'up' and previous_status == 'down':
            logger.info(
                f"RECOVERED: {result.url} is back UP! "
                f"Response time: {result.response_time_ms:.2f}ms"
            )


class UptimeChecker:
    """Main uptime monitoring service."""
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.sites = self._parse_sites()
        self.alert_handlers: list[AlertHandler] = [LoggingAlertHandler()]
        self._previous_status: dict[str, str] = {}
    
    def _load_config(self) -> dict:
        """Load configuration from JSON or YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        content = self.config_path.read_text()
        
        if self.config_path.suffix in ['.yaml', '.yml']:
            return yaml.safe_load(content)
        elif self.config_path.suffix == '.json':
            return json.loads(content)
        else:
            # Try YAML first, then JSON
            try:
                return yaml.safe_load(content)
            except yaml.YAMLError:
                return json.loads(content)
    
    def _parse_sites(self) -> list[SiteConfig]:
        """Parse site configurations from loaded config."""
        sites = []
        default_timeout = self.config.get('default_timeout', 10)
        
        for site_data in self.config.get('sites', []):
            if isinstance(site_data, str):
                sites.append(SiteConfig(url=site_data, timeout=default_timeout))
            else:
                sites.append(SiteConfig(
                    url=site_data['url'],
                    name=site_data.get('name'),
                    timeout=site_data.get('timeout', default_timeout),
                    expected_status=site_data.get('expected_status', 200)
                ))
        
        return sites
    
    def add_alert_handler(self, handler: AlertHandler) -> None:
        """Add a custom alert handler."""
        self.alert_handlers.append(handler)
    
    def check_site(self, site: SiteConfig) -> CheckResult:
        """Check availability of a single site."""
        start_time = time.time()
        
        try:
            response = requests.get(
                site.url,
                timeout=site.timeout,
                headers={'User-Agent': 'UptimeChecker/1.0'},
                allow_redirects=True
            )
            
            response_time_ms = (time.time() - start_time) * 1000
            
            if response.status_code == site.expected_status:
                status = 'up'
                error_message = None
            else:
                status = 'down'
                error_message = f"Unexpected status code: {response.status_code}"
            
            result = CheckResult(
                url=site.url,
                status=status,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                error_message=error_message,
                timestamp=datetime.now()
            )
            
        except requests.exceptions.Timeout:
            result = CheckResult(
                url=site.url,
                status='down',
                status_code=None,
                response_time_ms=None,
                error_message=f"Timeout after {site.timeout}s",
                timestamp=datetime.now()
            )
        except requests.exceptions.ConnectionError as e:
            result = CheckResult(
                url=site.url,
                status='down',
                status_code=None,
                response_time_ms=None,
                error_message=f"Connection error: {str(e)[:100]}",
                timestamp=datetime.now()
            )
        except requests.exceptions.RequestException as e:
            result = CheckResult(
                url=site.url,
                status='error',
                status_code=None,
                response_time_ms=None,
                error_message=f"Request error: {str(e)[:100]}",
                timestamp=datetime.now()
            )
        
        return result
    
    def _trigger_alerts(self, result: CheckResult) -> None:
        """Trigger alert handlers for a check result."""
        previous_status = self._previous_status.get(result.url)
        
        for handler in self.alert_handlers:
            handler.on_check_complete(result)
            
            if previous_status != result.status:
                handler.on_status_change(result, previous_status)
        
        self._previous_status[result.url] = result.status
    
    def check_all(self) -> list[CheckResult]:
        """Check all configured sites."""
        results = []
        
        for site in self.sites:
            logger.info(f"Checking {site.display_name} ({site.url})...")
            result = self.check_site(site)
            
            # Log result
            if result.status == 'up':
                logger.info(
                    f"  ✓ {site.display_name}: UP - "
                    f"HTTP {result.status_code} in {result.response_time_ms:.2f}ms"
                )
            else:
                logger.warning(
                    f"  ✗ {site.display_name}: {result.status.upper()} - "
                    f"{result.error_message}"
                )
            
            self._trigger_alerts(result)
            results.append(result)
        
        return results
    
    def run_continuous(self, interval_seconds: int = 60) -> None:
        """Run monitoring continuously with specified interval."""
        logger.info(f"Starting continuous monitoring with {interval_seconds}s interval")
        logger.info(f"Monitoring {len(self.sites)} sites")
        
        try:
            while True:
                self.check_all()
                logger.info(f"Next check in {interval_seconds} seconds...")
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Web Uptime Checker')
    parser.add_argument(
        '-c', '--config',
        default='config.yaml',
        help='Path to configuration file (JSON or YAML)'
    )
    parser.add_argument(
        '-i', '--interval',
        type=int,
        default=60,
        help='Check interval in seconds (default: 60)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run check once and exit'
    )
    
    args = parser.parse_args()
    
    try:
        checker = UptimeChecker(args.config)
        
        if args.once:
            results = checker.check_all()
            print(json.dumps([r.to_dict() for r in results], indent=2))
        else:
            checker.run_continuous(args.interval)
            
    except FileNotFoundError as e:
        logger.error(f"Configuration error: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        exit(1)


if __name__ == '__main__':
    main()
