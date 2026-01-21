"""
Example alert handlers for the Uptime Checker.

These examples show how to extend the AlertHandler base class
to implement custom alerting mechanisms.
"""

import os
import json
import smtplib
from email.mime.text import MIMEText
from typing import Optional

# Uncomment imports as needed:
# import requests  # For Slack/Discord webhooks
# from twilio.rest import Client  # For SMS alerts

from uptime_checker import AlertHandler, CheckResult


class EmailAlertHandler(AlertHandler):
    """Send email alerts on status changes.
    
    Requires SMTP configuration via environment variables:
    - SMTP_HOST: SMTP server hostname
    - SMTP_PORT: SMTP server port
    - SMTP_USER: SMTP username
    - SMTP_PASSWORD: SMTP password
    - ALERT_EMAIL_FROM: Sender email address
    - ALERT_EMAIL_TO: Recipient email address
    """
    
    def __init__(self):
        self.smtp_host = os.environ.get('SMTP_HOST', 'localhost')
        self.smtp_port = int(os.environ.get('SMTP_PORT', 587))
        self.smtp_user = os.environ.get('SMTP_USER')
        self.smtp_password = os.environ.get('SMTP_PASSWORD')
        self.from_email = os.environ.get('ALERT_EMAIL_FROM')
        self.to_email = os.environ.get('ALERT_EMAIL_TO')
    
    def on_status_change(self, result: CheckResult, previous_status: Optional[str]) -> None:
        if result.status == 'down':
            subject = f"ALERT: {result.url} is DOWN"
            body = f"""
Site: {result.url}
Status: DOWN
Previous Status: {previous_status}
Error: {result.error_message or f'HTTP {result.status_code}'}
Time: {result.timestamp.isoformat()}
"""
        elif result.status == 'up' and previous_status == 'down':
            subject = f"RECOVERED: {result.url} is back UP"
            body = f"""
Site: {result.url}
Status: UP
Response Time: {result.response_time_ms:.2f}ms
Time: {result.timestamp.isoformat()}
"""
        else:
            return  # No email for other state changes
        
        self._send_email(subject, body)
    
    def _send_email(self, subject: str, body: str) -> None:
        if not all([self.smtp_user, self.smtp_password, self.from_email, self.to_email]):
            print("Email alert skipped: Missing SMTP configuration")
            return
        
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = self.from_email
        msg['To'] = self.to_email
        
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
        except Exception as e:
            print(f"Failed to send email alert: {e}")


class SlackAlertHandler(AlertHandler):
    """Send alerts to a Slack channel via webhook.
    
    Requires environment variable:
    - SLACK_WEBHOOK_URL: Slack incoming webhook URL
    """
    
    def __init__(self):
        self.webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
    
    def on_status_change(self, result: CheckResult, previous_status: Optional[str]) -> None:
        if not self.webhook_url:
            print("Slack alert skipped: Missing SLACK_WEBHOOK_URL")
            return
        
        if result.status == 'down':
            color = 'danger'
            text = f":x: *{result.url}* is DOWN"
            fields = [
                {"title": "Error", "value": result.error_message or f"HTTP {result.status_code}", "short": True},
                {"title": "Previous Status", "value": previous_status or "unknown", "short": True}
            ]
        elif result.status == 'up' and previous_status == 'down':
            color = 'good'
            text = f":white_check_mark: *{result.url}* is back UP"
            fields = [
                {"title": "Response Time", "value": f"{result.response_time_ms:.2f}ms", "short": True}
            ]
        else:
            return
        
        payload = {
            "attachments": [{
                "color": color,
                "text": text,
                "fields": fields,
                "ts": result.timestamp.timestamp()
            }]
        }
        
        try:
            import requests
            requests.post(self.webhook_url, json=payload, timeout=10)
        except Exception as e:
            print(f"Failed to send Slack alert: {e}")


class DiscordAlertHandler(AlertHandler):
    """Send alerts to a Discord channel via webhook.
    
    Requires environment variable:
    - DISCORD_WEBHOOK_URL: Discord webhook URL
    """
    
    def __init__(self):
        self.webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    
    def on_status_change(self, result: CheckResult, previous_status: Optional[str]) -> None:
        if not self.webhook_url:
            print("Discord alert skipped: Missing DISCORD_WEBHOOK_URL")
            return
        
        if result.status == 'down':
            color = 15158332  # Red
            title = f"ALERT: {result.url} is DOWN"
            description = f"Error: {result.error_message or f'HTTP {result.status_code}'}"
        elif result.status == 'up' and previous_status == 'down':
            color = 3066993  # Green
            title = f"RECOVERED: {result.url} is back UP"
            description = f"Response time: {result.response_time_ms:.2f}ms"
        else:
            return
        
        payload = {
            "embeds": [{
                "title": title,
                "description": description,
                "color": color,
                "timestamp": result.timestamp.isoformat()
            }]
        }
        
        try:
            import requests
            requests.post(self.webhook_url, json=payload, timeout=10)
        except Exception as e:
            print(f"Failed to send Discord alert: {e}")


class PagerDutyAlertHandler(AlertHandler):
    """Send alerts to PagerDuty.
    
    Requires environment variable:
    - PAGERDUTY_ROUTING_KEY: PagerDuty Events API v2 routing key
    """
    
    def __init__(self):
        self.routing_key = os.environ.get('PAGERDUTY_ROUTING_KEY')
        self.api_url = "https://events.pagerduty.com/v2/enqueue"
    
    def on_status_change(self, result: CheckResult, previous_status: Optional[str]) -> None:
        if not self.routing_key:
            print("PagerDuty alert skipped: Missing PAGERDUTY_ROUTING_KEY")
            return
        
        if result.status == 'down':
            payload = {
                "routing_key": self.routing_key,
                "event_action": "trigger",
                "dedup_key": f"uptime-{result.url}",
                "payload": {
                    "summary": f"{result.url} is DOWN: {result.error_message or f'HTTP {result.status_code}'}",
                    "source": "uptime-checker",
                    "severity": "critical",
                    "custom_details": result.to_dict()
                }
            }
        elif result.status == 'up' and previous_status == 'down':
            payload = {
                "routing_key": self.routing_key,
                "event_action": "resolve",
                "dedup_key": f"uptime-{result.url}"
            }
        else:
            return
        
        try:
            import requests
            requests.post(self.api_url, json=payload, timeout=10)
        except Exception as e:
            print(f"Failed to send PagerDuty alert: {e}")


class FileAlertHandler(AlertHandler):
    """Log all check results to a JSON file for later analysis."""
    
    def __init__(self, filepath: str = "uptime_history.jsonl"):
        self.filepath = filepath
    
    def on_check_complete(self, result: CheckResult) -> None:
        with open(self.filepath, 'a') as f:
            f.write(json.dumps(result.to_dict()) + '\n')
