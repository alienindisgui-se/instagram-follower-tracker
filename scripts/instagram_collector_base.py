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


class ApiUnavailableError(Exception):
    """Exception raised when the API is completely unavailable."""


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
    ):
        self.config_file = config_file
        self.data_file = data_file
        self.discord_webhook = discord_webhook or os.getenv("IG_TRACKER_DISCORD_WEBHOOK")

        # Use cloudscraper with built-in Cloudflare bypass (no proxy needed)
        self.scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True}
        )

        # Load config
        self.usernames = self._load_config()

        # Run-scoped circuit breakers / state.
        # - Instapeep: if we see HTTP 503 at least once during the run, disable Instapeep for the remainder.
        # - Inflact: if it fails at least once (non-200 or exception), disable it for the remainder and use InstaRadar as 3rd fallback.
        self.instapeep_disabled = False
        self.inflact_failed = False

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

        Order:
          1) Instapeep
          2) Inflact
          3) InstaRadar

        InstaRadar must be attempted once Inflact fails (including exceptions like timeouts),
        regardless of whether Instapeep was disabled via HTTP 503.
        """

        url = f"https://instapeep.com/api/profile/{username}"

        inflact_url = "https://inflact.com/profile-analyzer/v1/analytics/?lang=en"
        inflact_payload = {"url": username}

        instaradar_base = "https://www.instaradar.app/api/user"

        instapeep_attempts = 0 if self.instapeep_disabled else 3

        for attempt in range(instapeep_attempts if instapeep_attempts else 1):
            try:
                # -----------------------
                # 1) Instapeep (primary)
                # -----------------------
                if not self.instapeep_disabled:
                    response = self.scraper.get(url, timeout=30)
                    logger.info(f"Request to {url} returned status {response.status_code}")

                    if response.status_code == 200:
                        data = response.json()
                        follower_count = data.get("follower_count")
                        if follower_count is not None:
                            return int(follower_count)
                        logger.warning(f"No follower count found in response for {username}")
                        return None

                    # Never retry on 503: move to next fallback option.
                    if response.status_code == 503:
                        logger.warning(
                            f"HTTP 503 Service Unavailable for {username} (Instapeep). Disabling Instapeep for remainder of run."
                        )
                        self.instapeep_disabled = True

                # -----------------------
                # 2) Inflact (secondary)
                # -----------------------
                inflact_response = None
                try:
                    inflact_response = self.scraper.post(
                        inflact_url,
                        data=inflact_payload,
                        timeout=30,
                    )
                    logger.info(
                        f"Fallback request to {inflact_url} returned status {inflact_response.status_code}"
                    )

                    if inflact_response.status_code == 200:
                        inflact_data = inflact_response.json() or {}
                        profile = (inflact_data.get("data") or {}).get("profile") or {}

                        follower_count = (profile.get("engagement", {}) or {}).get("followers")
                        if follower_count is None:
                            follower_count = profile.get("followers")

                        if follower_count is not None:
                            return int(follower_count)

                        logger.warning(f"Inflact fallback returned 200 but no follower count for {username}")
                        return None

                    logger.warning(
                        f"Inflact fallback HTTP {inflact_response.status_code} for {username}"
                    )
                except Exception as e:
                    logger.error(f"Inflact fallback failed for {username}: {e}")

                # Mark Inflact as failed for the remainder of the run.
                # This includes exceptions (inflact_response stays None).
                if inflact_response is None or inflact_response.status_code != 200:
                    self.inflact_failed = True

                # -----------------------
                # 3) InstaRadar (3rd)
                # -----------------------
                if self.inflact_failed:
                    instaradar_url = f"{instaradar_base}/{username}"
                    try:
                        radar_response = self.scraper.get(instaradar_url, timeout=30)
                        logger.info(
                            f"3rd fallback request to {instaradar_url} returned status {radar_response.status_code}"
                        )

                        if radar_response.status_code == 200:
                            radar_data = radar_response.json() or {}
                            profile = (radar_data.get("data") or {})
                            follower_count = profile.get("follower_count")
                            if follower_count is not None:
                                return int(follower_count)

                            logger.warning(
                                f"InstaRadar returned 200 but no follower count for {username}"
                            )
                            return None

                        logger.warning(
                            f"InstaRadar fallback HTTP {radar_response.status_code} for {username}"
                        )
                    except Exception as e:
                        logger.error(f"InstaRadar fallback failed for {username}: {e}")

                raise ApiUnavailableError(f"API unavailable for {username}")

            except ApiUnavailableError:
                raise
            except Exception as e:
                logger.error(f"Error fetching data for {username}: {e}")
                if attempt < 2:
                    time.sleep(2**attempt)
                    continue

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
                "**Instapeep.com API is currently unavailable (HTTP 503 Service Unavailable)**\n\n"
                "All follower data collection attempts failed. The API may be experiencing temporary downtime.\n\n"
                "**Next steps:**\n"
                "- Check https://instapeep.com status\n"
                "- Retry collection manually when API recovers\n"
                "- Consider implementing backup API endpoint"
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
            logger.info(f"Fetching data for {username}")
            try:
                count = self.get_follower_count(username)
                if count is not None:
                    current_data[username] = count
                    logger.info(f"{username}: {count}")
                else:
                    logger.warning(f"Failed to fetch data for {username}")
            except ApiUnavailableError as e:
                logger.error(str(e))
                logger.error("Stopping data collection for remaining usernames.")
                break

            if username != self.usernames[-1]:
                delay = random.uniform(5, 15)
                logger.info(f"Sleeping for {delay:.2f} seconds")
                time.sleep(delay)

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

