#!/usr/bin/env python3
"""Instagram Follower Collector Base Class

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

import cloudscraper
from dotenv import load_dotenv



# Load environment variables
load_dotenv()


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class InstagramCollectorBase:
    def __init__(
        self,
        config_file: str = "config/instagram_tracker_settings.json",
        data_file: str = "data/instagram_follower_history.json",
        discord_webhook: Optional[str] = None,
        scraper=None,
    ):
        self.config_file = config_file
        self.data_file = data_file
        self.discord_webhook = discord_webhook or os.getenv("IG_TRACKER_DISCORD_WEBHOOK")

        # Use cloudscraper with built-in Cloudflare bypass (no proxy needed)
        self.scraper = scraper or cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True}
        )

        # Load config
        self.usernames = self._load_config()

        self.instapeep_disabled = False

    def _load_config(self) -> list:
        """Load usernames from config file."""
        try:
            with open(self.config_file, "r") as f:
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
            with open(self.data_file, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {"daily": {}, "weekly": {}, "monthly": {}}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in data file: {e}")
            return {"daily": {}, "weekly": {}, "monthly": {}}

    def _save_history(self, data: Dict) -> None:
        """Save historical follower data."""
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        with open(self.data_file, "w") as f:
            json.dump(data, f, indent=2)

    def get_follower_count(self, username: str) -> Optional[int]:
        """Get follower count for a username.

        Order: Instapeep -> Inflact.
        """

        url = f"https://instapeep.com/api/profile/{username}"

        inflact_url = "https://inflact.com/profile-analyzer/v1/analytics/?lang=en"
        inflact_payload = {"url": username}

        def _get_error_message(response):
            try:
                data = response.json()
                if isinstance(data, dict):
                    return data.get("message") or data.get("error") or ""
            except Exception:
                pass
            return ""

        response = None
        if not self.instapeep_disabled:
            try:
                response = self.scraper.get(url, timeout=30)
            except Exception as e:
                logger.error(f"[instapeep] {username} error: {e}")

        if response and response.status_code == 200:
            data = response.json()
            follower_count = data.get("follower_count")
            if follower_count is not None:
                logger.info(f"[instapeep] [{username}] [{int(follower_count)}]")
                return int(follower_count)
            logger.warning(f"[instapeep] {username} no count in response")
            return None

        if response and response.status_code == 503:
            err_msg = _get_error_message(response)
            logger.warning(
                f"[instapeep] {username} 503 service unavailable{f' - {err_msg}' if err_msg else ''}"
            )

        if response and response.status_code == 503:
            self.instapeep_disabled = True

        try:
            inflact_response = self.scraper.post(
                inflact_url,
                data=inflact_payload,
                timeout=30,
            )
        except Exception as e:
            logger.error(f"[inflact] {username} error: {e}")
            return None

        if inflact_response.status_code == 200:
            inflact_data = inflact_response.json() or {}
            profile = (inflact_data.get("data") or {}).get("profile") or {}

            follower_count = (profile.get("engagement", {}) or {}).get("followers")
            if follower_count is None:
                follower_count = profile.get("followers")

            if follower_count is not None:
                logger.info(f"[inflact] [{username}] [{int(follower_count)}]")
                return int(follower_count)

            logger.warning(f"[inflact] {username} 200 but no count")
            return None

        err_msg = _get_error_message(inflact_response)
        if inflact_response.status_code == 429:
            logger.warning(f"[inflact] {username} 429, trying next tier")
        elif inflact_response.status_code == 503:
            logger.warning(f"[inflact] {username} 503 provider overloaded{f' - {err_msg}' if err_msg else ''}")
        else:
            logger.warning(f"[inflact] {username} HTTP {inflact_response.status_code}{f' - {err_msg}' if err_msg else ''}")

        return None

    def calculate_delta(self, current: int, previous: Optional[int]) -> str:
        """Calculate and format delta."""
        if previous is None:
            return "~"  # No previous data
        diff = current - previous
        if diff > 0:
            return f"+{diff}"
        if diff < 0:
            return f"{diff}"
        return "~"

    def calculate_percentage_change(self, current: int, previous: Optional[int]) -> str:
        """Calculate and format percentage change."""
        if previous is None or previous == 0:
            return "N/A"
        diff = current - previous
        percentage = (diff / previous) * 100
        if percentage > 0:
            return f"+{percentage:.1f}%"
        if percentage < 0:
            return f"{percentage:.1f}%"
        return "0.0%"

    def send_api_failure_notification(self, report_type: str) -> None:
        """Send Discord notification when the API is completely unavailable."""
        if not self.discord_webhook:
            logger.warning("No Discord webhook configured")
            return

        embed = {
            "title": f"🚨 Instagram {report_type} Collection Failed",
            "description": (
                "**Instagram follower data collection failed for one or more users.**\n\n"
                "All available API endpoints were rate-limited or unavailable. "
                "Some follower counts may be missing.\n\n"
                "**Recommendations:**\n"
                "- Retry collection in a few minutes\n"
                "- Consider increasing delay between requests\n"
                "- Monitor API rate limits"
            ),
            "color": 0xFF0000,
        }
        payload = {"embeds": [embed]}

        try:
            import requests as http_requests

            response = http_requests.post(self.discord_webhook, json=payload, timeout=10)
            if response.status_code != 204:
                logger.warning(f"Discord webhook returned status {response.status_code}")
        except Exception as e:
            logger.error(f"Error sending Discord API failure notification: {e}")

    def send_discord_notification(self, reports: List[Dict], report_type: str, period: str) -> None:
        """Send consolidated report to Discord webhook."""
        if not self.discord_webhook:
            logger.warning("No Discord webhook configured")
            return
        if not reports:
            return

        sorted_reports = sorted(reports, key=lambda x: x["count"], reverse=True)

        lines = []
        for report in sorted_reports:
            delta = report["delta"]

            if delta.startswith("+"):
                delta_num = int(delta[1:])
                delta_text = f"🟢 **{delta_num:,} more**"
            elif delta.startswith("-"):
                delta_num = int(delta[1:])
                delta_text = f"🔴 **{delta_num:,} less**"
            else:
                delta_text = "🟠 no changes"

            lines.append(
                f"**{report['username']}** has {report['count']:,} followers {delta_text} since {period}."
            )

        if report_type in ("Weekly", "Monthly"):
            reports_with_percentage = [r for r in reports if r["percentage"] != "N/A"]
            if reports_with_percentage:
                def parse_percentage(pct_str: str) -> float:
                    return float(pct_str.replace("%", "").replace("+", ""))

                parsed_reports = [(r, parse_percentage(r["percentage"])) for r in reports_with_percentage]

                most_increase = max(parsed_reports, key=lambda x: x[1])
                most_decrease = min(parsed_reports, key=lambda x: x[1])

                lines.append(
                    "\n" + "\n".join(
                        [
                            f"🟢 **{most_increase[0]['username']}** gained the most: {most_increase[0]['percentage']}",
                            f"🔴 **{most_decrease[0]['username']}** lost the most: {most_decrease[0]['percentage']}",
                        ]
                    )
                )

        color_map = {"Daily": 0x0099FF, "Weekly": 0x00FF88, "Monthly": 0x8800FF}
        embed_color = color_map.get(report_type, 0x0099FF)

        embed = {
            "title": f"📊 Instagram {report_type} Report {datetime.now().strftime('%Y-%m-%d')}",
            "description": "\n".join(lines),
            "color": embed_color,
        }
        payload = {"embeds": [embed]}

        try:
            import requests as http_requests

            response = http_requests.post(self.discord_webhook, json=payload, timeout=10)
            if response.status_code != 204:
                logger.warning(f"Discord webhook returned status {response.status_code}")
        except Exception as e:
            logger.error(f"Error sending Discord message: {e}")

    def collect_current_data(self) -> Dict[str, int]:
        """Collect current follower data for all usernames."""
        current_data: Dict[str, int] = {}

        for username in self.usernames:
            count = self.get_follower_count(username)
            if count is not None:
                current_data[username] = count

            if username != self.usernames[-1]:
                time.sleep(random.uniform(5, 15))

        return current_data

    def get_previous_sunday(self) -> str:
        """Get date string for previous Sunday."""
        today = datetime.now(timezone.utc)
        days_since_sunday = (today.weekday() + 1) % 7
        if days_since_sunday == 0:
            previous_sunday = today - timedelta(days=7)
        else:
            previous_sunday = today - timedelta(days=days_since_sunday)
        return previous_sunday.strftime("%Y-%m-%d")

    def get_previous_month_first_day(self) -> str:
        """Get date string for first day of previous month."""
        today = datetime.now(timezone.utc)
        if today.month == 1:
            previous_month = today.replace(year=today.year - 1, month=12, day=1)
        else:
            previous_month = today.replace(month=today.month - 1, day=1)
        return previous_month.strftime("%Y-%m-%d")

    def get_previous_day(self) -> str:
        """Get date string for previous day."""
        today = datetime.now(timezone.utc)
        previous_day = today - timedelta(days=1)
        return previous_day.strftime("%Y-%m-%d")

    def get_previous_data_with_fallback(
        self,
        history: Dict,
        data_type: str,
        target_date: str,
        max_lookback: int = 7,
    ) -> Dict[str, int]:
        """Get previous data with fallback to earlier dates and averaging."""

        data_section = history.get(data_type, {})

        if target_date in data_section:
            return data_section[target_date]

        available_data = []
        current_date = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        if data_type in ("daily", "weekly"):
            delta_days = timedelta(days=1) if data_type == "daily" else timedelta(days=7)

        for i in range(1, max_lookback + 1):
            if data_type == "monthly":
                lookback_date = current_date
                for _ in range(i):
                    if lookback_date.month == 1:
                        lookback_date = lookback_date.replace(
                            year=lookback_date.year - 1, month=12
                        )
                    else:
                        lookback_date = lookback_date.replace(month=lookback_date.month - 1)
            else:
                lookback_date = current_date - (delta_days * i)

            date_str = lookback_date.strftime("%Y-%m-%d")
            if date_str in data_section:
                available_data.append(data_section[date_str])

        if not available_data:
            return {}

        averaged_data: Dict[str, int] = {}
        all_usernames = set()
        for data_point in available_data:
            all_usernames.update(data_point.keys())

        for username in all_usernames:
            counts = [
                data_point.get(username)
                for data_point in available_data
                if username in data_point
            ]
            if counts:
                averaged_data[username] = int(sum(counts) / len(counts))

        logger.info(
            f"Using averaged data from {len(available_data)} {data_type} periods for {target_date}"
        )
        return averaged_data

