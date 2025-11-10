# Discord Bot Setup Guide

Complete guide to deploying the UCLA Class Monitor Discord Bot on Heroku with Supabase database.

## Overview

The system has two components:
1. **GitHub Actions** - Monitors classes every 5 minutes
2. **Discord Bot (Heroku)** - Responds to slash commands and sends DM notifications

Both use **Supabase** (free PostgreSQL database) for shared state.

---

## Part 1: Set Up Supabase Database

### 1. Create Supabase Account

1. Go to [supabase.com](https://supabase.com)
2. Click "Start your project"
3. Sign up with GitHub (easiest)

### 2. Create New Project

1. Click "New Project"
2. Fill in:
   - **Name**: ucla-class-monitor
   - **Database Password**: (generate a strong password - save it!)
   - **Region**: West US (closest to UCLA)
   - **Plan**: Free tier
3. Click "Create new project"
4. Wait ~2 minutes for setup

### 3. Create Database Tables

1. In your project, click **SQL Editor** (left sidebar)
2. Click **"+ New query"**
3. Paste this SQL and click **RUN**:

```sql
-- Table for storing class states
CREATE TABLE class_states (
    class_key TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    catalog_number TEXT NOT NULL,
    status TEXT NOT NULL,
    enrolled INTEGER DEFAULT 0,
    capacity INTEGER DEFAULT 0,
    waitlist_count INTEGER DEFAULT 0,
    waitlist_capacity INTEGER DEFAULT 0,
    last_checked TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Table for user subscriptions
CREATE TABLE user_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    class_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (class_key) REFERENCES class_states(class_key) ON DELETE CASCADE
);

-- Index for faster queries
CREATE INDEX idx_user_subscriptions_user ON user_subscriptions(user_id);
CREATE INDEX idx_user_subscriptions_class ON user_subscriptions(class_key);
CREATE INDEX idx_class_states_status ON class_states(status);

-- Enable Row Level Security (optional, for security)
ALTER TABLE class_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_subscriptions ENABLE ROW LEVEL SECURITY;

-- Create policies to allow all operations (since we're using service key)
CREATE POLICY "Enable all for service role" ON class_states FOR ALL USING (true);
CREATE POLICY "Enable all for service role" ON user_subscriptions FOR ALL USING (true);
```

### 4. Get Your Supabase Credentials

1. Click **Settings** (gear icon, left sidebar)
2. Click **API**
3. Copy these values (you'll need them later):
   - **Project URL** (looks like `https://xxxxx.supabase.co`)
   - **anon public** key (under "Project API keys")

---

## Part 2: Create Discord Bot

### 1. Create Discord Application

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **"New Application"**
3. Name it "UCLA Class Monitor" (or whatever you want)
4. Click **"Create"**

### 2. Create Bot User

1. Click **"Bot"** in left sidebar
2. Click **"Add Bot"** → **"Yes, do it!"**
3. Under **"TOKEN"**, click **"Reset Token"** → **"Copy"**
   - **Save this token** - you'll need it for Heroku!
4. Scroll down to **"Privileged Gateway Intents"**:
   - ✅ Enable **"MESSAGE CONTENT INTENT"**
   - ✅ Enable **"SERVER MEMBERS INTENT"**
5. Click **"Save Changes"**

### 3. Invite Bot to Your Server

1. Click **"OAuth2"** → **"URL Generator"** (left sidebar)
2. Under **SCOPES**, check:
   - ✅ `bot`
   - ✅ `applications.commands`
3. Under **BOT PERMISSIONS**, check:
   - ✅ Send Messages
   - ✅ Send Messages in Threads
   - ✅ Embed Links
   - ✅ Use Slash Commands
4. Copy the **Generated URL** at the bottom
5. Paste it in your browser → Select your server → **Authorize**

---

## Part 3: Deploy to Heroku

### 1. Install Heroku CLI

```bash
# macOS
brew tap heroku/brew && brew install heroku

# Or download from: https://devcenter.heroku.com/articles/heroku-cli
```

### 2. Login to Heroku

```bash
heroku login
```

### 3. Create Heroku App

```bash
cd "/Users/yang/class monitoring script"

# Create app (Heroku will generate a name, or specify your own)
heroku create your-ucla-bot

# Or let Heroku generate a name:
heroku create
```

### 4. Set Environment Variables

```bash
# Set Discord bot token
heroku config:set DISCORD_TOKEN="your_discord_bot_token_here"

# Set Supabase credentials
heroku config:set SUPABASE_URL="https://xxxxx.supabase.co"
heroku config:set SUPABASE_KEY="your_supabase_anon_key_here"

# Set UCLA term code
heroku config:set UCLA_TERM="26W"
```

### 5. Add Buildpacks

The bot needs Python and Playwright (which requires system dependencies):

```bash
# Add Python buildpack
heroku buildpacks:add heroku/python

# Add Playwright buildpack
heroku buildpacks:add https://github.com/mxschmitt/heroku-playwright-buildpack.git
```

### 6. Deploy

```bash
# Make sure requirements-bot.txt is named requirements.txt for Heroku
cp requirements-bot.txt requirements.txt

# Add and commit Heroku files
git add Procfile runtime.txt requirements.txt bot.py database.py
git commit -m "Add Discord bot for Heroku deployment"

# Push to Heroku
git push heroku main

# View logs to confirm it's running
heroku logs --tail
```

You should see:
```
✅ Logged in as YourBot#1234
📚 Monitoring term: 26W
✅ Synced X command(s)
✅ Started background class monitoring
🤖 Bot is ready!
```

### 7. Scale to Basic Dyno (for 24/7 uptime)

```bash
# Check current dynos
heroku ps

# Scale worker to 1 (using your credits)
heroku ps:scale worker=1:basic

# Verify it's running
heroku ps
```

Output should show:
```
=== worker (Basic): python bot.py (1)
worker.1: up 2025/01/09 ...
```

---

## Part 4: Update GitHub Actions

The monitor needs to use Supabase too. Update your GitHub repository secrets:

### 1. Add Supabase Secrets to GitHub

1. Go to your repo: https://github.com/YGao2005/ucla-class-tracker
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Add these secrets:
   - `SUPABASE_URL`: Your Supabase project URL (e.g., `https://xxxxx.supabase.co`)
   - `SUPABASE_KEY`: Your Supabase anon key

### 2. Push Updated Code to GitHub

The monitor.py has been updated to use Supabase. Push the changes:

```bash
cd "/Users/yang/class monitoring script"

# Add all updated files
git add monitor.py requirements.txt .github/workflows/monitor.yml database.py

# Commit the changes
git commit -m "Integrate Supabase database for shared state between GitHub Actions and Discord bot"

# Push to GitHub
git push origin main
```

### 3. Verify GitHub Actions

After pushing, GitHub Actions will automatically run:

1. Go to your repo → **Actions** tab
2. You should see the workflow running
3. Click on it to see logs
4. Verify it successfully:
   - Installs dependencies including supabase
   - Connects to Supabase database
   - Updates class states in the database

The workflow now uses Supabase instead of state.json, so the Discord bot and GitHub Actions share the same data!

---

## Part 5: Test the Bot!

### Test Slash Commands

In your Discord server:

1. Type `/check PSYCH 124G` - Should show current class status
2. Type `/subscribe PSYCH 124G` - Should subscribe you
3. Check your DMs - Bot should confirm subscription
4. Type `/list` - Should show your subscribed classes
5. Type `/status` - Should check all your classes

### Test Notifications

Wait for GitHub Actions to run (every 5 minutes). When a class status changes, you'll get a DM!

---

## Troubleshooting

### Bot not responding to commands

```bash
# Check logs
heroku logs --tail

# Restart bot
heroku restart

# Make sure worker is running
heroku ps
```

### Commands not appearing in Discord

1. Wait up to 1 hour (global slash commands take time to sync)
2. Or sync to your server instantly (add this to bot.py temporarily):

```python
@bot.event
async def on_ready():
    guild = discord.Object(id=YOUR_GUILD_ID)  # Your server ID
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
```

### Database errors

Check Supabase:
1. Go to your Supabase project
2. Click **Table Editor**
3. Verify tables exist: `class_states`, `user_subscriptions`

### Heroku costs

Check your usage:
```bash
heroku ps:type
heroku billing
```

---

## Managing Your Bot

### View Logs
```bash
heroku logs --tail
```

### Restart Bot
```bash
heroku restart
```

### Update Bot Code
```bash
git add .
git commit -m "Update bot"
git push heroku main
```

### Stop Bot (to save credits)
```bash
heroku ps:scale worker=0
```

### Start Bot Again
```bash
heroku ps:scale worker=1:basic
```

---

## Cost Estimate

With your $220 Heroku credits:

- **Basic dyno**: $7/month
- **Runtime**: ~31 months until credits run out
- **Supabase**: FREE (500MB database, unlimited API calls)
- **GitHub Actions**: FREE (2,000 minutes/month)

**Total**: Covered by your credits! 🎉

---

## Next Steps

1. ✅ Complete this setup
2. Update `monitor.py` to use Supabase (instructions coming)
3. Test the system end-to-end
4. Invite your friends to use the bot!

---

## Support

If you run into issues:
- Check Heroku logs: `heroku logs --tail`
- Check Supabase logs: Project → Logs
- Check GitHub Actions: Actions tab in your repo

Happy monitoring! 🎓
