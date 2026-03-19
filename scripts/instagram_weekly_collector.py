#!/usr/bin/env python3
"""
Instagram Weekly Follower Collector
Tracks Instagram follower counts with weekly comparison reports.
"""

from datetime import datetime, timezone
try:
    from .instagram_collector_base import InstagramCollectorBase
except ImportError:
    from instagram_collector_base import InstagramCollectorBase
import logging

logger = logging.getLogger(__name__)

class InstagramWeeklyCollector(InstagramCollectorBase):
    def __init__(self, config_file: str = "config/instagram_tracker_settings.json", data_file: str = "data/instagram_follower_history.json", discord_webhook: str = None):
        super().__init__(config_file, data_file, discord_webhook)

    def run(self) -> None:
        """Main execution method for weekly collection."""
        if not self.discord_webhook:
            logger.warning("No Discord webhook configured. Exiting.")
            return

        history = self._load_history()
        current_data = self.collect_current_data()
        
        if not current_data:
            logger.error("No data collected. Exiting.")
            return

        # Get previous Sunday's data for comparison
        previous_sunday = self.get_previous_sunday()
        previous_weekly_data = history.get("weekly", {}).get(previous_sunday, {})
        
        # Fallback to daily data if weekly data doesn't exist
        if not previous_weekly_data:
            previous_weekly_data = history.get("daily", {}).get(previous_sunday, {})
            if previous_weekly_data:
                logger.info(f"Using daily data for {previous_sunday} as weekly data fallback")
        
        reports = []
        
        for username in self.usernames:
            current_count = current_data.get(username)
            previous_count = previous_weekly_data.get(username)
            
            if current_count is not None:
                delta = self.calculate_delta(current_count, previous_count)
                percentage = self.calculate_percentage_change(current_count, previous_count)
                
                reports.append({
                    "username": username,
                    "count": current_count,
                    "delta": delta,
                    "percentage": percentage
                })
                
                logger.info(f"{username}: {current_count} ({delta}, {percentage}) from previous Sunday")

        # Send Discord notification
        self.send_discord_notification(reports, "Weekly", "last week")

        # Update history data
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        # Ensure weekly structure exists
        if "weekly" not in history:
            history["weekly"] = {}
        
        # Store current Sunday's data
        history["weekly"][today] = current_data
        
        # Clean up old weekly data (keep last 8 weeks)
        self._cleanup_old_weekly_data(history)
        
        self._save_history(history)
        logger.info("Weekly collection complete")

    def _cleanup_old_weekly_data(self, history: dict) -> None:
        """Clean up weekly data older than 8 weeks."""
        if "weekly" not in history:
            return
            
        weekly_data = history["weekly"]
        dates = list(weekly_data.keys())
        dates.sort()
        
        # Keep only the last 8 Sundays
        if len(dates) > 8:
            dates_to_keep = dates[-8:]
            cleaned_weekly = {}
            for date in dates_to_keep:
                cleaned_weekly[date] = weekly_data[date]
            history["weekly"] = cleaned_weekly
            logger.info(f"Cleaned up {len(dates) - 8} old weekly records")

if __name__ == "__main__":
    collector = InstagramWeeklyCollector()
    collector.run()
