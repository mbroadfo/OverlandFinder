"""
Daily Monitoring and Notification System
Runs periodically to find deals and send SMS updates.
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from dotenv import load_dotenv

from src.evaluator.value_evaluator import ValueEvaluator, VehicleListing
from src.jobs.sms_notifier import SMSNotifier

load_dotenv(override=True)


class DailyMonitor:
    """Monitors for deals and sends daily SMS summary"""
    
    def __init__(self):
        self.database_file = os.getenv("DATABASE_FILE", "overlanding_deals.json")
        self.last_notification_file = "last_notification.txt"
        self.notifier = SMSNotifier()
        self.enable_sms = os.getenv("ENABLE_SMS_NOTIFICATIONS", "false").lower() == "true"
    
    def get_last_notification_time(self) -> Optional[datetime]:
        """Get timestamp of last notification sent"""
        try:
            if os.path.exists(self.last_notification_file):
                with open(self.last_notification_file, 'r') as f:
                    timestamp_str = f.read().strip()
                    return datetime.fromisoformat(timestamp_str)
        except Exception as e:
            print(f"Error reading last notification time: {e}")
        return None
    
    def set_last_notification_time(self):
        """Record current time as last notification sent"""
        try:
            with open(self.last_notification_file, 'w') as f:
                f.write(datetime.now().isoformat())
        except Exception as e:
            print(f"Error saving notification time: {e}")
    
    def should_send_notification(self) -> bool:
        """Check if we should send a notification (once per day)"""
        last_time = self.get_last_notification_time()
        
        if last_time is None:
            return True  # Never sent before
        
        # Check if 24 hours have passed
        time_since_last = datetime.now() - last_time
        return time_since_last >= timedelta(hours=24)
    
    def get_top_deals(self, min_score: float = 65, max_results: int = 3) -> List[Dict]:
        """Get top deals from database"""
        if not os.path.exists(self.database_file):
            return []
        
        try:
            with open(self.database_file, 'r') as f:
                deals = json.load(f)
            
            # Filter by score and sort
            filtered = [d for d in deals if d.get("value_score", 0) >= min_score]
            sorted_deals = sorted(filtered, key=lambda x: x.get("value_score", 0), reverse=True)
            
            return sorted_deals[:max_results]
        except Exception as e:
            print(f"Error loading deals: {e}")
            return []
    
    def generate_daily_summary(self) -> Optional[Tuple[str, str]]:
        """
        Generate daily summary message and URL.
        
        Returns:
            Tuple of (summary_text, url) or None if no deals
        """
        deals = self.get_top_deals()
        
        if not deals:
            # No good deals found
            summary = "No new hot deals today"
            url = "https://facebook.com/marketplace"
            return (summary, url)
        
        # Get best deal
        top_deal = deals[0]
        vehicle = top_deal.get("vehicle", "Unknown")
        price = top_deal.get("price", 0)
        score = top_deal.get("value_score", 0)
        url = top_deal.get("url", "https://example.com")
        
        # Format summary (keep short for SMS)
        num_deals = len(deals)
        if num_deals == 1:
            summary = f"{vehicle} ${price:,} (score {score:.0f})"
        else:
            summary = f"{num_deals} deals! Top: {vehicle} ${price:,}"
        
        return (summary, url)
    
    async def run_daily_check(self) -> bool:
        """
        Run daily check and send notification if needed.
        
        Returns:
            True if notification was sent, False otherwise
        """
        print(f"\n{'='*60}")
        print(f"🔍 Daily Check - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        # Check if we should send notification
        if not self.should_send_notification():
            last_time = self.get_last_notification_time()
            if last_time:
                hours_since = (datetime.now() - last_time).total_seconds() / 3600
                print(f"⏰ Last notification sent {hours_since:.1f} hours ago")
            print("⏭️  Skipping (less than 24 hours)")
            return False
        
        if not self.enable_sms:
            print("📵 SMS notifications disabled in .env (ENABLE_SMS_NOTIFICATIONS=false)")
            print("   Set ENABLE_SMS_NOTIFICATIONS=true to enable")
            
            # Still show what would be sent
            summary_data = self.generate_daily_summary()
            if summary_data:
                summary, url = summary_data
                message = f"Daily update:\n{summary}\n{url}"
                print(f"\n📱 Would send SMS:\n{message}\n")
            return False
        
        # Generate summary
        summary_data = self.generate_daily_summary()
        if not summary_data:
            print("⚠️ Could not generate summary")
            return False
        
        summary, url = summary_data
        
        # Send SMS
        print(f"📱 Sending daily SMS notification...")
        success = self.notifier.send_daily_update(summary, url)
        
        if success:
            self.set_last_notification_time()
            print("✅ Daily notification sent successfully!")
            return True
        else:
            print("❌ Failed to send notification")
            return False
    
    def run_daily_check_sync(self) -> bool:
        """Synchronous wrapper for run_daily_check"""
        return asyncio.run(self.run_daily_check())


async def main():
    """Main entry point for daily monitoring"""
    monitor = DailyMonitor()
    await monitor.run_daily_check()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Daily Deal Monitor")
    parser.add_argument("--force", action="store_true", help="Force send notification (ignore 24hr limit)")
    parser.add_argument("--status", action="store_true", help="Show current status")
    
    args = parser.parse_args()
    
    monitor = DailyMonitor()
    
    if args.status:
        print("\n📊 Daily Monitor Status")
        print("=" * 60)
        print(f"Database: {monitor.database_file}")
        print(f"SMS Enabled: {monitor.enable_sms}")
        print(f"Recipient: {monitor.notifier.recipient}")
        
        last_time = monitor.get_last_notification_time()
        if last_time:
            hours_ago = (datetime.now() - last_time).total_seconds() / 3600
            print(f"Last Notification: {last_time.strftime('%Y-%m-%d %H:%M:%S')} ({hours_ago:.1f}h ago)")
        else:
            print("Last Notification: Never")
        
        print(f"\nShould send now: {monitor.should_send_notification()}")
        
        # Show top deals
        deals = monitor.get_top_deals()
        if deals:
            print(f"\n🔥 Top Deals ({len(deals)}):")
            for i, deal in enumerate(deals, 1):
                print(f"  {i}. {deal['vehicle']} - ${deal['price']:,} (score {deal['value_score']:.0f})")
        else:
            print("\n💤 No deals in database")
    
    elif args.force:
        # Temporarily remove last notification time
        if os.path.exists(monitor.last_notification_file):
            os.remove(monitor.last_notification_file)
        asyncio.run(main())
    
    else:
        asyncio.run(main())
