#!/usr/bin/env python3
"""
Instagram Monthly Follower Collector
Tracks Instagram follower counts with monthly comparison reports.
"""

from datetime import datetime, timezone, timedelta
from instagram_collector_base import InstagramCollectorBase
import logging

logger = logging.getLogger(__name__)

class InstagramMonthlyCollector(InstagramCollectorBase):
    def __init__(self, config_file: str = "config/instagram_tracker_settings.json", data_file: str = "data/instagram_follower_history.json", discord_webhook: str = None):
        super().__init__(config_file, data_file, discord_webhook)

    def run(self) -> None:
        """Main execution method for monthly collection."""
        if not self.discord_webhook:
            logger.warning("No Discord webhook configured. Exiting.")
            return

        history = self._load_history()
        current_data = self.collect_current_data()
        
        if not current_data:
            logger.error("No data collected. Exiting.")
            return

        # Get previous month's data for comparison
        previous_month_date = self.get_previous_month_first_day()
        previous_month_data = history.get("monthly", {}).get(previous_month_date, {})
        
        # Fallback to daily data if monthly data doesn't exist
        if not previous_month_data:
            previous_month_data = history.get("daily", {}).get(previous_month_date, {})
            if previous_month_data:
                logger.info(f"Using daily data for {previous_month_date} as monthly data fallback")
        
        reports = []
        
        for username in self.usernames:
            current_count = current_data.get(username)
            previous_count = previous_month_data.get(username)
            
            if current_count is not None:
                delta = self.calculate_delta(current_count, previous_count)
                percentage = self.calculate_percentage_change(current_count, previous_count)
                
                reports.append({
                    "username": username,
                    "count": current_count,
                    "delta": delta,
                    "percentage": percentage
                })
                
                logger.info(f"{username}: {current_count} ({delta}, {percentage}) from previous month")

        # Send Discord notification
        self.send_discord_notification(reports, "Monthly", "last month")

        # Update history data
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        # Ensure monthly structure exists
        if "monthly" not in history:
            history["monthly"] = {}
        
        # Store current month's data (use first day of current month as key)
        current_month_first_day = datetime.now(timezone.utc).replace(day=1).strftime('%Y-%m-%d')
        history["monthly"][current_month_first_day] = current_data
        
        # Clean up old monthly data (keep last 12 months)
        self._cleanup_old_monthly_data(history)
        
        self._save_history(history)
        logger.info("Monthly collection complete")

    def _cleanup_old_monthly_data(self, history: dict) -> None:
        """Clean up monthly data older than 12 months."""
        if "monthly" not in history:
            return
            
        monthly_data = history["monthly"]
        dates = list(monthly_data.keys())
        dates.sort()
        
        # Keep only the last 12 months
        if len(dates) > 12:
            dates_to_keep = dates[-12:]
            cleaned_monthly = {}
            for date in dates_to_keep:
                cleaned_monthly[date] = monthly_data[date]
            history["monthly"] = cleaned_monthly
            logger.info(f"Cleaned up {len(dates) - 12} old monthly records")

if __name__ == "__main__":
    collector = InstagramMonthlyCollector()
    collector.run()
