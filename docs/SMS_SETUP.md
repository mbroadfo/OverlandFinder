# 📱 SMS Notification Setup Guide

## Quick Start

### 1. Get Gmail App Password

**Why?** Gmail requires an "App Password" for third-party apps (not your regular password).

1. Go to your Google Account: https://myaccount.google.com/
2. Navigate to **Security** → **2-Step Verification** (enable if not already)
3. Scroll to **App passwords**: https://myaccount.google.com/apppasswords
4. Generate a new app password:
   - App: **Mail**
   - Device: **Windows Computer**
5. Copy the 16-character password (e.g., `abcd efgh ijkl mnop`)

### 2. Update `.env` File

Open `.env` and add your SMTP credentials:

```env
# Enable SMS
ENABLE_SMS_NOTIFICATIONS=true
SMS_RECIPIENT=7208399656@vtext.com

# SMTP (Gmail)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=abcdefghijklmnop
```

**IMPORTANT:** Remove spaces from the app password!

### 3. Test SMS

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Test sending SMS
python sms_notifier.py --test
```

You should receive:
```
Daily update:
Test from Overland Finder
https://example.com
```

### 4. Run Daily Monitor

**Manual check:**
```powershell
python daily_monitor.py
```

**Check status:**
```powershell
python daily_monitor.py --status
```

**Force send (ignore 24hr limit):**
```powershell
python daily_monitor.py --force
```

## Message Format

```
Daily update:
{summary}
{url}
```

**Example 1 (deals found):**
```
Daily update:
3 deals! Top: 2014 Wrangler $8,500
https://facebook.com/marketplace/item/123
```

**Example 2 (no deals):**
```
Daily update:
No new hot deals today
https://facebook.com/marketplace
```

## Automation (Optional)

### Windows Task Scheduler

1. Open Task Scheduler
2. Create Basic Task
3. **Trigger:** Daily at 8:00 AM
4. **Action:** Start a program
   - Program: `C:\Users\Mike\Documents\Code\OverlandFinder\.venv\Scripts\python.exe`
   - Arguments: `daily_monitor.py`
   - Start in: `C:\Users\Mike\Documents\Code\OverlandFinder`

### Or use Python scheduler (runs continuously):

```python
# schedule_monitor.py
import schedule
import time
from daily_monitor import DailyMonitor

monitor = DailyMonitor()

# Run daily at 8 AM
schedule.every().day.at("08:00").do(monitor.run_daily_check_sync)

print("📅 Scheduler running... (Ctrl+C to stop)")
while True:
    schedule.run_pending()
    time.sleep(60)  # Check every minute
```

## Troubleshooting

### "SMTP Authentication failed"
- Double-check SMTP_USERNAME is your full email
- Verify SMTP_PASSWORD is the App Password (no spaces!)
- Make sure 2-Step Verification is enabled
- Try regenerating the App Password

### "No module named 'smtplib'"
- This is a built-in Python module, should always be available
- Try reinstalling Python if issue persists

### "SMS not sending"
- Check your internet connection
- Verify Gmail isn't blocking the app password
- Check Gmail's "Less secure app access" settings
- Try a different SMTP server (Outlook.com, Yahoo, etc.)

### "Notification sent but not received"
- Verify phone number in SMS_RECIPIENT is correct
- Verizon gateway: `number@vtext.com`
- AT&T gateway: `number@txt.att.net`
- T-Mobile gateway: `number@tmomail.net`
- Sprint gateway: `number@messaging.sprintpcs.com`

## Advanced: Using Different Email Providers

### Outlook/Hotmail
```env
SMTP_SERVER=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USERNAME=your-email@outlook.com
SMTP_PASSWORD=your-password
```

### Yahoo
```env
SMTP_SERVER=smtp.mail.yahoo.com
SMTP_PORT=587
SMTP_USERNAME=your-email@yahoo.com
SMTP_PASSWORD=your-app-password
```

## Security Notes

- ⚠️ Never commit `.env` to Git (it's in `.gitignore`)
- 🔒 App Passwords are safer than your main password
- 🚫 Don't share your SMTP credentials
- ✅ App Passwords can be revoked anytime from Google

## Daily Flow

1. **8:00 AM:** Scheduled check runs
2. **Agent scans** saved deals database
3. **If 24+ hours** since last SMS:
   - Get top 3 deals (score ≥65)
   - Format message (<140 chars)
   - Send via email → SMS gateway
   - Record timestamp
4. **If <24 hours:** Skip (only 1 SMS per day)

---

**Ready?** Run `python sms_notifier.py --test` to send your first text! 📱
