#!/usr/bin/env python3
"""
Instagram Follower Collector Base Class
Shared functionality for daily, weekly, and monthly Instagram follower tracking.
"""

import json
import logging
import os
import random
import sys
import time
from typing import Dict, Optional, List
from datetime import datetime, timezone, timedelta

from curl_cffi import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class InstagramCollectorBase:
    def __init__(self, config_file: str = "config/ig_tracker_settings.json", data_file: str = "data/ig_follower_history.json", discord_webhook: Optional[str] = None):
        self.config_file = config_file
        self.data_file = data_file
        self.discord_webhook = discord_webhook or os.getenv("IG_TRACKER_DISCORD_WEBHOOK")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Instagram 123.0.0.1 Android (31/12; 480dpi; 1080x2229; samsung; SM-G973F; beyond2lte; qcom; en_US; 309061856)",
            "x-ig-app-id": "936619743392459"
        })

        # Load config
        self.usernames = self._load_config()

    def _load_config(self) -> list:
        """Load usernames from config file."""
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
                return data.get("usernames", [])
        except FileNotFoundError:
            logger.error(f"Configuration file {self.config_file} not found")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            sys.exit(1)

    def _load_history(self) -> Dict:
        """Load historical follower data."""
        try:
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {"daily": {}, "weekly": {}, "monthly": {}}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in data file: {e}")
            return {"daily": {}, "weekly": {}, "monthly": {}}

    def _save_history(self, data: Dict) -> None:
        """Save historical follower data."""
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=2)

    def get_follower_count(self, username: str) -> Optional[int]:
        """Get follower count for a username using mobile API."""
        url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
        try:
            response = self.session.get(url, timeout=30)
            logger.info(f"Request to {url} returned status {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                user_data = data.get("data", {}).get("user", {})
                follower_count = user_data.get("edge_followed_by", {}).get("count")
                if follower_count is not None:
                    logger.info(f"Extracted follower count: {follower_count}")
                    return int(follower_count)
            elif response.status_code in [403, 429]:
                logger.error("Security Block: Received 403 or 429 status code. Exiting to prevent further requests.")
                sys.exit(1)
            else:
                logger.warning(f"Unexpected status code {response.status_code} for {username}")
        except Exception as e:
            logger.error(f"Error fetching data for {username}: {e}")
        return None

    def calculate_delta(self, current: int, previous: Optional[int]) -> str:
        """Calculate and format delta."""
        if previous is None:
            return "~"  # No previous data
        diff = current - previous
        if diff > 0:
            return f"+{diff}"
        elif diff < 0:
            return f"{diff}"
        else:
            return "~"

    def calculate_percentage_change(self, current: int, previous: Optional[int]) -> str:
        """Calculate and format percentage change."""
        if previous is None or previous == 0:
            return "N/A"
        diff = current - previous
        percentage = (diff / previous) * 100
        if percentage > 0:
            return f"+{percentage:.1f}%"
        elif percentage < 0:
            return f"{percentage:.1f}%"
        else:
            return "0.0%"

    def send_discord_notification(self, reports: List[Dict], report_type: str, period: str) -> None:
        """Send consolidated report to Discord webhook."""
        if not self.discord_webhook:
            logger.warning("No Discord webhook configured")
            return
        if not reports:
            return

        lines = []
        for report in reports:
            delta = report['delta']
            
            if delta.startswith('+'):
                delta_num = int(delta[1:])
                delta_text = f"🟢 **{delta_num} more**"
            elif delta.startswith('-'):
                delta_num = int(delta[1:])
                delta_text = f"🔴 **{delta_num} less**"
            else:
                delta_text = f"🟠 no changes"
            
            lines.append(f"**{report['username']}** has {report['count']} followers {delta_text} since {period}.")

        # Set different colors based on report type
        color_map = {
            "Daily":    0x0099ff,   # Blue
            "Weekly":   0x00ff88,   # Green
            "Monthly":  0x8800ff    # Purple
        }
        embed_color = color_map.get(report_type, 0x0099ff)  # Default to blue if unknown

        embed = {
            "title": f"📊 Instagram {report_type} Report {datetime.now().strftime('%Y-%m-%d')}",
            "description": "\n".join(lines),
            "color": embed_color
        }
        payload = {
            "embeds": [embed]
        }
        try:
            response = requests.post(self.discord_webhook, json=payload, timeout=10)
            if response.status_code != 204:
                logger.warning(f"Discord webhook returned status {response.status_code}")
        except Exception as e:
            logger.error(f"Error sending Discord message: {e}")

    def collect_current_data(self) -> Dict[str, int]:
        """Collect current follower data for all usernames."""
        current_data = {}
        
        for username in self.usernames:
            logger.info(f"Fetching data for {username}")
            count = self.get_follower_count(username)
            if count is not None:
                current_data[username] = count
                logger.info(f"{username}: {count}")
            else:
                logger.warning(f"Failed to fetch data for {username}")

            # Random delay between 45-120 seconds
            if username != self.usernames[-1]:  # No delay after last
                delay = random.uniform(45, 120)
                logger.info(f"Sleeping for {delay:.2f} seconds")
                time.sleep(delay)

        return current_data

    def get_previous_sunday(self) -> str:
        """Get date string for previous Sunday."""
        today = datetime.now(timezone.utc)
        days_since_sunday = (today.weekday() + 1) % 7  # Sunday is 0
        if days_since_sunday == 0:  # Today is Sunday
            previous_sunday = today - timedelta(days=7)
        else:
            previous_sunday = today - timedelta(days=days_since_sunday)
        return previous_sunday.strftime('%Y-%m-%d')

    def get_previous_month_first_day(self) -> str:
        """Get date string for first day of previous month."""
        today = datetime.now(timezone.utc)
        if today.month == 1:
            previous_month = today.replace(year=today.year - 1, month=12, day=1)
        else:
            previous_month = today.replace(month=today.month - 1, day=1)
        return previous_month.strftime('%Y-%m-%d')

    def get_previous_day(self) -> str:
        """Get date string for previous day."""
        today = datetime.now(timezone.utc)
        previous_day = today - timedelta(days=1)
        return previous_day.strftime('%Y-%m-%d')
