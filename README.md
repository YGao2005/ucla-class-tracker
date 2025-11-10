# UCLA Class Availability Monitor

Automated monitoring of UCLA class availability with Discord notifications. Runs on GitHub Actions every 5 minutes to check if your desired classes have open spots.

## Features

- **Automated Web Scraping**: Uses Playwright to scrape UCLA's Schedule of Classes
- **Discord Notifications**: Get instant alerts when class status changes
- **Multiple Classes**: Monitor as many classes as you want
- **Free Hosting**: Runs on GitHub Actions (completely free)
- **Status Tracking**: Only notifies on actual status changes
- **Reliable**: Headless browser renders pages exactly like a real browser
 
## Setup Instructions

### 1. Fork/Clone This Repository

```bash
git clone <your-repo-url>
cd class-monitoring-script
```

### 2. Configure Your Classes

Edit `config.json` to add the classes you want to monitor:

```json
{
  "term": "25W",
  "classes": [
    {
      "subject": "PSYCH",
      "catalog_number": "100A",
      "description": "Psychology 100A - Research Methods"
    },
    {
      "subject": "COM SCI",
      "catalog_number": "111",
      "description": "Computer Science 111 - Operating Systems"
    }
  ]
}
```

**Term Codes:**
- Spring 2025: `25S`
- Summer 2025: `251` (for Summer Session A, adjust as needed)
- Fall 2025: `25F`
- Winter 2026: `26W`

You can find these by looking at the `t=` parameter in the UCLA Schedule of Classes URL.

### 3. Set Up Discord Webhook

1. **Create a Discord Server** (or use an existing one)
2. **Create a Webhook:**
   - Right-click on a text channel → Edit Channel
   - Go to Integrations → Webhooks → New Webhook
   - Copy the Webhook URL
3. **Add to GitHub Secrets:**
   - Go to your GitHub repository
   - Click Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `DISCORD_WEBHOOK_URL`
   - Value: Paste your webhook URL
   - Click "Add secret"

### 4. Enable GitHub Actions

1. Go to the **Actions** tab in your repository
2. Click "I understand my workflows, go ahead and enable them"
3. The workflow will run automatically every 5 minutes
4. You can also manually trigger it using "Run workflow"

### 5. Push to GitHub

```bash
git add .
git commit -m "Initial setup"
git push origin main
```

## How It Works

1. **GitHub Actions** runs the script every 5 minutes (configurable in `.github/workflows/monitor.yml`)
2. The script launches a headless Chromium browser using Playwright
3. It navigates to UCLA's Schedule of Classes page for each subject
4. Waits for JavaScript to load and renders the course data
5. Extracts enrollment status from the rendered page
6. Compares with the previous check (stored in `state.json`)
7. If status changes (e.g., from "Full" to "Open"), it sends a Discord notification
8. State is automatically committed back to the repository

## Testing Locally

Before deploying, you can test the script locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Set your Discord webhook
export DISCORD_WEBHOOK_URL="your-webhook-url-here"

# Run the script
python monitor.py
```

## Customization

### Change Check Frequency

Edit `.github/workflows/monitor.yml`:

```yaml
schedule:
  - cron: '*/5 * * * *'  # Every 5 minutes
  # - cron: '*/15 * * * *'  # Every 15 minutes
  # - cron: '0 * * * *'    # Every hour
```

**Note:** GitHub Actions may have slight delays during high-usage periods.

### Modify Notification Format

Edit the `send_discord_notification()` function in `monitor.py` to customize:
- Embed colors
- Message format
- Additional fields
- @mentions (add to payload)

## Troubleshooting

### No notifications are being sent

1. Check that `DISCORD_WEBHOOK_URL` is set in GitHub Secrets
2. Verify the webhook URL is correct in Discord
3. Check the Actions tab for error logs

### Script fails with 404 error

Make sure the `X-Requested-With: XMLHttpRequest` header is included in requests (already implemented).

### Classes not being detected

1. Verify the term code is correct in `config.json`
2. Check that subject and catalog number match exactly what's on the UCLA Schedule of Classes
3. The class might use a different subject code (e.g., "COM SCI" vs "COMSCI")

### State file conflicts

If you're getting merge conflicts on `state.json`:
- Pull the latest changes before the action runs
- Or reset `state.json` to `{}`

## Files Overview

- **`monitor.py`**: Main Python script
- **`config.json`**: Your class watchlist
- **`state.json`**: Tracks previous status (auto-updated)
- **`requirements.txt`**: Python dependencies
- **`.github/workflows/monitor.yml`**: GitHub Actions configuration
- **`README.md`**: This file

## UCLA Term Information

Find current term codes at: https://sa.ucla.edu/ro/public/soc

The term code appears in the URL parameter `t=XXX`.

## Credits

Built using UCLA's public Schedule of Classes API. Inspired by similar projects from UCLA students.

## Disclaimer

This tool is for educational purposes. Use responsibly and in accordance with UCLA's policies. The author is not responsible for any misuse or violations of university policies.

## License

MIT License - Feel free to modify and share!
