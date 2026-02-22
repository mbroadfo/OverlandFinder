"""
SMS Notification via Verizon Email-to-SMS Gateway
Sends daily deal updates via text message.
"""

import smtplib
import os
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from dotenv import load_dotenv

load_dotenv(override=True)


class SMSNotifier:
    """Send SMS notifications via Verizon email-to-SMS gateway"""
    
    def __init__(self):
        self.recipient = os.getenv("SMS_RECIPIENT", "7208399656@vtext.com")
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.max_retries = 3
        self.retry_delay = 5  # seconds
    
    def send_daily_update(self, summary: str, url: str) -> bool:
        """
        Send daily update SMS.
        
        Args:
            summary: One short sentence summary (max ~100 chars)
            url: Clickable URL to include
            
        Returns:
            True if sent successfully, False otherwise
        """
        # Format message exactly as specified
        message_body = f"Daily update:\n{summary}\n{url}"
        
        # Validate length (140 char limit for SMS)
        if len(message_body) > 140:
            # Truncate summary to fit
            max_summary_len = 140 - len("Daily update:\n\n") - len(url)
            summary = summary[:max_summary_len-3] + "..."
            message_body = f"Daily update:\n{summary}\n{url}"
        
        return self._send_sms(message_body)
    
    def _send_sms(self, message: str) -> bool:
        """
        Send SMS via email gateway with retry logic.
        
        Args:
            message: Plain text message to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                # Create plain text email
                msg = MIMEMultipart()
                msg['From'] = self.smtp_username
                msg['To'] = self.recipient
                msg['Subject'] = ""  # Empty subject for cleaner SMS
                
                # Attach plain text body
                msg.attach(MIMEText(message, 'plain'))
                
                # Connect and send
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
                
                print(f"✅ SMS sent successfully to {self.recipient}")
                print(f"Message: {message}")
                return True
                
            except smtplib.SMTPAuthenticationError:
                print(f"❌ SMTP Authentication failed. Check SMTP_USERNAME and SMTP_PASSWORD in .env")
                return False  # Don't retry auth errors
                
            except Exception as e:
                print(f"⚠️ Attempt {attempt}/{self.max_retries} failed: {e}")
                
                if attempt < self.max_retries:
                    print(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                else:
                    print(f"❌ Failed to send SMS after {self.max_retries} attempts")
                    return False
        
        return False
    
    def test_notification(self) -> bool:
        """Send a test notification"""
        return self.send_daily_update(
            summary="Test message from Jeep Finder",
            url="https://example.com"
        )


def validate_config() -> bool:
    """Validate SMS configuration"""
    load_dotenv(override=True)
    
    required_vars = ["SMTP_USERNAME", "SMTP_PASSWORD"]
    missing = [var for var in required_vars if not os.getenv(var) or "<" in os.getenv(var, "")]
    
    if missing:
        print("❌ Missing required environment variables:")
        for var in missing:
            print(f"  - {var}")
        print("\nPlease update your .env file with valid SMTP credentials.")
        return False
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="SMS Notification System")
    parser.add_argument("--test", action="store_true", help="Send a test SMS")
    args = parser.parse_args()
    
    if not validate_config():
        exit(1)
    
    notifier = SMSNotifier()
    
    if args.test:
        print("📱 Sending test SMS...")
        success = notifier.test_notification()
        exit(0 if success else 1)
    else:
        print("Usage: python sms_notifier.py --test")
