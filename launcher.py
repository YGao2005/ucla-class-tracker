#!/usr/bin/env python3
"""
Simple Multi-Bot Launcher
Runs both Discord bots in a single Python process using asyncio
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def check_environment():
    """Verify required environment variables"""
    required = ['DISCORD_TOKEN', 'INTERNSHIP_BOT_TOKEN', 'SUPABASE_URL', 'SUPABASE_KEY']
    missing = [var for var in required if not os.getenv(var)]

    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        sys.exit(1)


async def main():
    """Run both bots concurrently"""
    print("="*60)
    print("🚀 MULTI-BOT LAUNCHER")
    print("="*60)
    print()

    check_environment()

    # Import both bot modules
    from shared_database import get_supabase_client
    from internship_bot import create_bot
    import bot as class_monitor_bot

    print("⏳ Initializing bots...")
    print()

    # Create internship bot
    supabase = get_supabase_client()
    internship_bot = create_bot(supabase)

    # Get tokens
    class_token = os.getenv('DISCORD_TOKEN')
    intern_token = os.getenv('INTERNSHIP_BOT_TOKEN')

    # Run both bots concurrently
    try:
        await asyncio.gather(
            class_monitor_bot.bot.start(class_token),
            internship_bot.start(intern_token)
        )
    except KeyboardInterrupt:
        print("\n⚠ Shutting down...")
        await class_monitor_bot.bot.close()
        await internship_bot.close()
        print("✓ Bots stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✓ Shutdown complete")
        sys.exit(0)
