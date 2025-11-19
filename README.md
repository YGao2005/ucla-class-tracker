# UCLA Class Availability Monitor 🎓

> Automated Discord notifications for UCLA class availability changes

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Discord.py](https://img.shields.io/badge/discord.py-2.3+-blue.svg)](https://discordpy.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Get instant Discord notifications when your desired UCLA classes have available spots. Monitors class enrollment status and alerts you the moment seats open up.

## Features

- ✅ **Real-time Monitoring** - Checks class availability using UCLA's Schedule of Classes
- 📱 **Discord Notifications** - Instant alerts when class status changes
- 🔄 **Multi-Class Support** - Monitor unlimited classes simultaneously
- 🎯 **Smart Filtering** - Only notifies on actual status changes
- 🌐 **Web Scraping** - Uses Playwright for accurate, browser-based scraping
- 💾 **Database Integration** - Supabase for persistent state tracking

## Quick Start

### Prerequisites

- Python 3.11+
- Discord Bot Token ([Create one here](https://discord.com/developers/applications))
- Supabase Account ([Free tier](https://supabase.com))

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/ucla-class-monitor.git
cd ucla-class-monitor

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Configure environment
cp .env.example .env
# Edit .env with your credentials
```

### Configuration

1. **Set up Discord Bot**:
   - Create application at [Discord Developer Portal](https://discord.com/developers/applications)
   - Enable bot with "Message Content Intent"
   - Copy token to `.env`

2. **Configure Classes** (`config.json`):
```json
{
  "term": "26W",
  "classes": [
    {
      "subject": "COM SCI",
      "catalog_number": "111",
      "description": "Operating Systems Principles"
    }
  ]
}
```

3. **Run the Bot**:
```bash
python bot.py
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DISCORD_TOKEN` | Discord bot token | Yes |
| `SUPABASE_URL` | Supabase project URL | Yes |
| `SUPABASE_KEY` | Supabase service role key | Yes |
| `UCLA_TERM` | UCLA term code (e.g., `26W`) | Optional |

## Term Codes

- **Winter 2026**: `26W`
- **Spring 2026**: `26S`
- **Fall 2026**: `26F`

Find current terms at [UCLA Schedule of Classes](https://sa.ucla.edu/ro/public/soc)

## Database Schema

The bot uses Supabase to track class status:

```sql
CREATE TABLE class_status (
  id UUID PRIMARY KEY,
  subject TEXT,
  catalog_number TEXT,
  status TEXT,
  last_checked TIMESTAMP,
  last_notified TIMESTAMP
);
```

## Discord Commands

- **Manual Check**: Trigger immediate class availability check
- **Status**: View current monitoring status
- **Add Class**: Add new class to watchlist
- **Remove Class**: Remove class from monitoring

## Architecture

This bot can run:
- **Standalone**: As an independent Discord bot
- **Multi-Bot Setup**: Via the [discord-bots-launcher](https://github.com/yourusername/discord-bots-launcher) alongside other bots

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## License

MIT License - see [LICENSE](LICENSE) for details

## Disclaimer

This tool is for educational purposes. Use responsibly and in accordance with UCLA's policies.

## Acknowledgments

- UCLA Schedule of Classes public API
- Built with [discord.py](https://github.com/Rapptz/discord.py)
- Web scraping powered by [Playwright](https://playwright.dev/)

---

**Made with ❤️ by UCLA students, for UCLA students**
