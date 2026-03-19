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
import uuid
import re
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
    def __init__(self, config_file: str = "config/instagram_tracker_settings.json", data_file: str = "data/instagram_follower_history.json", discord_webhook: Optional[str] = None):
        self.config_file = config_file
        self.data_file = data_file
        self.discord_webhook = discord_webhook or os.getenv("IG_TRACKER_DISCORD_WEBHOOK")
        self.session = requests.Session()
        
        # Updated User-Agent to current Instagram version (308.0.0.36.109)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Linux; Android 12; SM-A115M Build/SP1A.210812.016; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/100.0.4896.127 Mobile Safari/537.36 Instagram 308.0.0.36.109 Android (31/12; 280dpi; 720x1411; samsung; SM-A115M; a11q; qcom; en_US; 534961943)",
            "x-ig-app-id": "936619743392459",
            "x-ig-device-id": self._generate_device_id(),
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "accept-encoding": "gzip, deflate, br",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "x-requested-with": "XMLHttpRequest"
        })

        # Load config
        self.usernames = self._load_config()
        self._setup_session()

    def _generate_device_id(self) -> str:
        """Generate a random device ID for Instagram API."""
        return str(uuid.uuid4()).replace('-', '')[:16]

    def _setup_session(self):
        """Setup session with cookies and authentication."""
        cookie_file = "config/instagram_session.json"
        
        # Load existing session cookies if available
        if os.path.exists(cookie_file):
            try:
                with open(cookie_file, 'r') as f:
                    cookies = json.load(f)
                    for name, value in cookies.items():
                        self.session.cookies.set(name, value)
                logger.info("Loaded existing session cookies")
            except Exception as e:
                logger.warning(f"Failed to load session cookies: {e}")

    def _save_session(self):
        """Save session cookies to file."""
        cookie_file = "config/instagram_session.json"
        try:
            cookies = {cookie.name: cookie.value for cookie in self.session.cookies}
            os.makedirs(os.path.dirname(cookie_file), exist_ok=True)
            with open(cookie_file, 'w') as f:
                json.dump(cookies, f)
            logger.info("Saved session cookies")
        except Exception as e:
            logger.warning(f"Failed to save session cookies: {e}")

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
                else:
                    logger.warning(f"No follower count found in response for {username}")
            elif response.status_code == 401:
                # Try to refresh session or handle authentication
                logger.warning(f"401 Unauthorized for {username}. Attempting to refresh session...")
                self._refresh_session()
                # Retry once after session refresh
                response = self.session.get(url, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    user_data = data.get("data", {}).get("user", {})
                    follower_count = user_data.get("edge_followed_by", {}).get("count")
                    if follower_count is not None:
                        logger.info(f"Successfully extracted follower count after session refresh: {follower_count}")
                        return int(follower_count)
                else:
                    logger.error(f"Still getting {response.status_code} after session refresh for {username}")
            elif response.status_code in [403, 429]:
                logger.error("Security Block: Received " + str(response.status_code) + " status code. Exiting to prevent further requests.")
                sys.exit(1)
            else:
                logger.warning("Unexpected status code " + str(response.status_code) + " for " + username)
                
        except Exception as e:
            logger.error(f"Error fetching data for {username}: {e}")
            
        return None

    def _refresh_session(self):
        """Attempt to refresh the Instagram session."""
        # Clear existing cookies
        self.session.cookies.clear()
        
        # Generate new device ID
        new_device_id = self._generate_device_id()
        self.session.headers.update({"x-ig-device-id": new_device_id})
        
        # Try to get fresh session by visiting Instagram homepage
        try:
            response = self.session.get("https://www.instagram.com/", timeout=10)
            if response.status_code == 200:
                # Extract CSRF token if available
                csrf_match = re.search(r'"csrf_token":"([^"]+)"', response.text)
                if csrf_match:
                    self.session.headers.update({"x-csrftoken": csrf_match.group(1)})
                logger.info("Session refreshed successfully")
                self._save_session()
        except Exception as e:
            logger.warning(f"Failed to refresh session: {e}")

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
