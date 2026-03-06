#!/usr/bin/env python3
"""
Instagram Daily Follower Collector
Tracks Instagram follower counts with daily comparison reports.
"""

from datetime import datetime, timezone, timedelta
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

        history = self._load_history()
        current_data = self.collect_current_data()
        
        if not current_data:
            logger.error("No data collected. Exiting.")
            return

        # Get previous day's data for comparison
        previous_day = self.get_previous_day()
        previous_data = history.get("daily", {}).get(previous_day, {})
        
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
