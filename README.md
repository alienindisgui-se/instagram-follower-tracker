# Instagram Follower Tracker

![AI Assisted](https://img.shields.io/badge/AI%20Assisted-purple?style=for-the-badge)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Repo Size](https://img.shields.io/github/repo-size/alienindisgui-se/instagram-follower-tracker?style=for-the-badge&color=blue)
![License](https://img.shields.io/github/license/alienindisgui-se/instagram-follower-tracker?style=for-the-badge&color=green)

![Daily](https://img.shields.io/github/actions/workflow/status/alienindisgui-se/instagram-follower-tracker/instagram-daily-tracker.yml?branch=main&label=Daily%20Update&logo=instagram&style=for-the-badge&color=0099FF)
![Weekly](https://img.shields.io/github/actions/workflow/status/alienindisgui-se/instagram-follower-tracker/instagram-weekly-tracker.yml?branch=main&label=Weekly%20Update&logo=instagram&style=for-the-badge&color=00FF88)
![Monthly](https://img.shields.io/github/actions/workflow/status/alienindisgui-se/instagram-follower-tracker/instagram-monthly-tracker.yml?branch=main&label=Monthly%20Update&logo=instagram&style=for-the-badge&color=8800FF)

A sophisticated Python-based system for automated Instagram follower tracking with daily, weekly, and monthly comparison reports, Discord webhook notifications, GitHub Actions automation, and intelligent historical data management.

## 🚀 Features

- **📊 Multi-period Tracking**: Daily, weekly, and monthly follower count collection
- **🤖 Automated Execution**: GitHub Actions with scheduled runs and manual triggers
- **💬 Discord Notifications**: Color-coded embed reports with follower changes
- **📈 Historical Data**: JSON-based storage with automatic cleanup and retention policies
- **🔒 Security-First**: Error handling and Cloudflare bypass with cloudscraper
- **🔄 Fallback Logic**: Intelligent data fallback when previous periods are missing
- **📱 Instapeep API**: Reliable data fetching using Instapeep.com API endpoints

## 🏗️ Architecture

```
instagram-follower-tracker/
├── scripts/
│   ├── instagram_collector_base.py     # Shared functionality
│   ├── instagram_daily_collector.py    # Daily tracking
│   ├── instagram_weekly_collector.py   # Weekly tracking
│   └── instagram_monthly_collector.py  # Monthly tracking
├── config/
│   └── instagram_tracker_settings.json # Username configuration
├── data/
│   └── instagram_follower_history.json # Historical storage
├── requirements/
│   └── requirements-instagram.txt      # Python dependencies
└── .github/workflows/                  # GitHub Actions automation
```

## 🛠️ Setup Instructions

### Prerequisites

- Python 3.11+
- GitHub repository (for automation)
- Discord server (for notifications)

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `IG_TRACKER_DISCORD_WEBHOOK` | Yes | Discord webhook URL for notifications |

### Configuration Files

#### `config/instagram_tracker_settings.json`
```json
{
  "usernames": [
    "username1",
    "username3"
  ]
}
```

#### `.env`
```env
IG_TRACKER_DISCORD_WEBHOOK=https://discord.com/api/webhooks/your/webhook/id
```

## 📊 Data Structure

The system stores follower data in `data/instagram_follower_history.json`:

```json
{
  "daily": {
    "2026-03-06": {
      "username1": 1234567,
      "username2": 987654
    }
  },
  "weekly": {
    "2026-03-06": {
      "username1": 1234567,
      "username2": 987654
    }
  },
  "monthly": {
    "2026-03-01": {
      "username1": 1234567,
      "username2": 987654
    }
  }
}
```

### Data Retention Policies

- **Daily data**: Last 40 days
- **Weekly data**: Last 8 weeks  
- **Monthly data**: Last 12 months

## 🤖 GitHub Actions Automation

### Scheduled Workflows

| Workflow | Schedule | Description |
|----------|----------|-------------|
| Daily Tracker | `0 6 * * *` | Runs daily at 06:00 UTC |
| Weekly Tracker | `30 6 * * 0` | Runs Sundays at 06:30 UTC |
| Monthly Tracker | `0 7 1 * *` | Runs 1st of month at 07:00 UTC |

### Required GitHub Secrets

1. **IG_TRACKER_DISCORD_WEBHOOK**: Discord webhook URL
2. **GITHUB_TOKEN**: Automatically provided by GitHub Actions

### Manual Execution

All workflows support manual triggering via the GitHub Actions UI.

## 💬 Discord Integration

### Notification Format

The system sends rich embed notifications with:

- **Title**: Report type and date
- **Color**: 
  - 🔵 Daily: Blue (`0x0099ff`)
  - 🟢 Weekly: Green (`0x00ff88`) 
  - 🟣 Monthly: Purple (`0x8800ff`)
- **Content**: Follower changes with emoji indicators
  - 🟢 Gains: "+X more"
  - 🔴 Losses: "-X less"  
  - 🟠 No change: "no changes"

### Example Notification

```
📊 Instagram Weekly Report 2026-03-06

**username1** has 1,257,547 followers 🟢 **47 more** since last week.
**username2** has 99,727 followers 🔴 **15 less** since last week.
```

## 🔒 Security Considerations

### Rate Limiting

- **Request delays**: 5-15 seconds between username requests
- **Error handling**: Automatic retry with exponential backoff
- **Cloudflare bypass**: Uses cloudscraper for reliable access

### API Security

- **Instapeep API**: Uses Instapeep.com profile API endpoints
- **Cloudflare bypass**: Automatic Cloudflare detection and bypass
- **No authentication**: No Instagram login required

## 📱 API Method

The system uses Instapeep.com API endpoint:

```
https://instapeep.com/api/profile/{username}
```

**Response Format:**
```json
{
  "username": "user_12345",
  "full_name": "John Doe",
  "follower_count": 1234567,
  "following_count": 150,
  "post_count": 42,
  "is_private": false,
  "is_verified": false
}
```

**Key Features:**
- No authentication required
- Automatic Cloudflare bypass via cloudscraper
- Clean JSON response with follower count
- More reliable than Instagram's mobile API

## 🚀 Usage

### Manual Execution

```bash
# Daily collection
python scripts/instagram_daily_collector.py

# Weekly collection  
python scripts/instagram_weekly_collector.py

# Monthly collection
python scripts/instagram_monthly_collector.py
```

## 🔧 Troubleshooting

### Common Issues

#### "Configuration file not found"
- Ensure `config/instagram_tracker_settings.json` exists
- Check file path and permissions

#### "Discord webhook returned non-204 status"
- Verify webhook URL is correct
- Check Discord server permissions
- Ensure webhook hasn't been deleted

#### "Request failed with status 403/404"
- Instapeep.com API temporarily unavailable
- Check username spelling in config
- Verify accounts exist and are public
- System will retry automatically

#### "No data collected"
- Check username spelling in config
- Verify accounts are public
- Check network connectivity

## 📈 Fallback Logic

The system implements intelligent fallback when previous period data is missing:

1. **Weekly**: Falls back to daily data for the same date
2. **Monthly**: Falls back to daily data for the first day of previous month
3. **No previous data**: Shows "~" (no comparison available)

## 🧹 Data Cleanup

Automatic cleanup runs after each collection:

- **Daily**: Keeps last 40 days
- **Weekly**: Keeps last 8 Sundays
- **Monthly**: Keeps last 12 months

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Note**: This tool uses Instapeep.com API for data collection. Ensure compliance with Instagram's Terms of Service and Instapeep.com usage policies when using this system.
