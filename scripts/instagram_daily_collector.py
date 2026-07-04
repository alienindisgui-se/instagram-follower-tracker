#!/usr/bin/env python3
"""
Instagram Daily Follower Collector
Tracks Instagram follower counts with daily comparison reports.
"""

from datetime import datetime, timezone
try:
    from instagram_collector_base import InstagramCollectorBase
except ImportError:
    from instagram_collector_base import InstagramCollectorBase
import logging

logger = logging.getLogger(__name__)

class InstagramDailyCollector(InstagramCollectorBase):
    def __init__(self, config_file: str = "config/instagram_tracker_settings.json", data_file: str = "data/instagram_follower_history.json", discord_webhook: str = None):
        super().__init__(config_file, data_file, discord_webhook)

    def run(self) -> None:
        """Main execution method for daily collection."""
        if not self.discord_webhook:
            logger.warning("No Discord webhook configured. Exiting.")
            return

        # Check if today's data already exists to skip the 2nd run
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        history = self._load_history()
        if history.get("daily", {}).get(today):
            logger.info(f"Data for today ({today}) already exists. Skipping second run.")
            return

        current_data = self.collect_current_data()
        
        if not current_data:
            logger.error("No data collected. Sending API failure notification.")
            self.send_api_failure_notification("Daily")
            return
        
        # Require all usernames -- partial data is not accepted
        if len(current_data) < len(self.usernames):
            missing = len(self.usernames) - len(current_data)
            logger.error(f"Only {len(current_data)}/{len(self.usernames)} usernames fetched ({missing} failed). Aborting.")
            self.send_api_failure_notification("Daily")
            return

        # Get previous day's data for comparison
        previous_day = self.get_previous_day()
        previous_data = self.get_previous_data_with_fallback(history, "daily", previous_day, max_lookback=7)
        
        reports = []
        
        for username in self.usernames:
            current_count = current_data.get(username)
            previous_count = previous_data.get(username)
            
            if current_count is not None:
                delta = self.calculate_delta(current_count, previous_count)
                percentage = self.calculate_percentage_change(current_count, previous_count)
                
                reports.append({
                    "username": username,
                    "count": current_count,
                    "delta": delta,
                    "percentage": percentage
                })
                
                logger.info(f"{username}: {current_count} ({delta}, {percentage}) from yesterday")

        # Send Discord notification
        self.send_discord_notification(reports, "Daily", "yesterday")

        # Update history data
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        # Ensure daily structure exists
        if "daily" not in history:
            history["daily"] = {}
        
        # Store current day's data
        history["daily"][today] = current_data
        
        # Clean up old daily data (keep last 40 days)
        self._cleanup_old_daily_data(history)
        
        self._save_history(history)
        logger.info("Daily collection complete")

    def _cleanup_old_daily_data(self, history: dict) -> None:
        """Clean up daily data older than 40 days."""
        if "daily" not in history:
            return
            
        daily_data = history["daily"]
        dates = list(daily_data.keys())
        dates.sort()
        
        # Keep only the last 40 days
        if len(dates) > 40:
            dates_to_keep = dates[-40:]
            cleaned_daily = {}
            for date in dates_to_keep:
                cleaned_daily[date] = daily_data[date]
            history["daily"] = cleaned_daily
            logger.info(f"Cleaned up {len(dates) - 40} old daily records")

if __name__ == "__main__":
    collector = InstagramDailyCollector()
    collector.run()
