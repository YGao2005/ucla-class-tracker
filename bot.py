#!/usr/bin/env python3
"""
UCLA Class Monitor Discord Bot
Provides slash commands for checking class availability and managing subscriptions
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import asyncio
from datetime import datetime
from typing import Optional

from database import Database, make_class_key, parse_class_key
from monitor import UCLAClassMonitor

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.dm_messages = True

bot = commands.Bot(command_prefix='!', intents=intents)
db = Database()

# Term configuration (update this as needed)
CURRENT_TERM = os.environ.get('UCLA_TERM', '26W')


@bot.event
async def on_ready():
    """Called when bot is ready"""
    print(f'✅ Logged in as {bot.user} (ID: {bot.user.id})')
    print(f'📚 Monitoring term: {CURRENT_TERM}')

    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f'✅ Synced {len(synced)} command(s)')
    except Exception as e:
        print(f'❌ Failed to sync commands: {e}')

    # Start background task to check for class changes
    if not check_class_changes.is_running():
        check_class_changes.start()
        print('✅ Started background class monitoring')

    print('🤖 Bot is ready!')


# ==================== Slash Commands ====================

@bot.tree.command(name="check", description="Check current availability of a UCLA class")
@app_commands.describe(
    subject="Subject code (e.g., PSYCH, COM SCI)",
    course="Course number (e.g., 124G, 111)"
)
async def check_class(interaction: discord.Interaction, subject: str, course: str):
    """Check class availability in real-time"""
    await interaction.response.defer(thinking=True)

    subject = subject.upper().strip()
    course = course.upper().strip()
    class_key = make_class_key(subject, course)

    try:
        # Run Playwright scraper to get current status
        monitor = UCLAClassMonitor()

        async with monitor.get_browser() as (browser, page):
            class_data = await monitor.scrape_class_data(page, subject, course, CURRENT_TERM)

        if not class_data:
            await interaction.followup.send(
                f"❌ Could not find {subject} {course} for term {CURRENT_TERM}.\n"
                f"Make sure the class exists and the term code is correct.",
                ephemeral=True
            )
            return

        # Create embed with class info
        status = class_data['status']
        color = {
            'Open': 0x00ff00,      # Green
            'Full': 0xff0000,       # Red
            'Closed': 0x808080,     # Gray
            'Waitlist Available': 0xffff00  # Yellow
        }.get(status, 0x808080)

        embed = discord.Embed(
            title=f"📚 {subject} {course}",
            description=f"**Status:** {status}",
            color=color,
            timestamp=datetime.now()
        )

        # Add enrollment info
        if class_data['capacity'] > 0:
            embed.add_field(
                name="Enrollment",
                value=f"{class_data['enrolled']}/{class_data['capacity']}",
                inline=True
            )

        # Add waitlist info if applicable
        if class_data['waitlist_capacity'] > 0:
            embed.add_field(
                name="Waitlist",
                value=f"{class_data['waitlist_count']}/{class_data['waitlist_capacity']}",
                inline=True
            )

        # Check if user is subscribed
        user_subs = db.get_user_subscriptions(str(interaction.user.id))
        if class_key in user_subs:
            embed.set_footer(text="🔔 You're subscribed to this class")
        else:
            embed.set_footer(text="Use /subscribe to get notified when this class opens")

        await interaction.followup.send(embed=embed)

        # Update database with latest info
        db.update_class_state(class_key, class_data)

    except Exception as e:
        print(f"Error checking class {subject} {course}: {e}")
        await interaction.followup.send(
            f"❌ Error checking class: {str(e)}",
            ephemeral=True
        )


@bot.tree.command(name="subscribe", description="Get notified when a class has open spots")
@app_commands.describe(
    subject="Subject code (e.g., PSYCH, COM SCI)",
    course="Course number (e.g., 124G, 111)"
)
async def subscribe(interaction: discord.Interaction, subject: str, course: str):
    """Subscribe to class availability notifications"""
    subject = subject.upper().strip()
    course = course.upper().strip()
    class_key = make_class_key(subject, course)
    user_id = str(interaction.user.id)

    # Defer response to show "thinking" state while we fetch data
    await interaction.response.defer(ephemeral=True)

    try:
        # Check if already subscribed
        user_subs = db.get_user_subscriptions(user_id)
        if class_key in user_subs:
            await interaction.followup.send(
                f"ℹ️ You're already subscribed to {subject} {course}!",
                ephemeral=True
            )
            return

        # Try to fetch real data immediately
        class_data = None
        try:
            monitor = UCLAClassMonitor()
            async with monitor.get_browser() as (browser, page):
                class_data = await monitor.scrape_class_data(page, subject, course, CURRENT_TERM)
        except Exception as e:
            print(f"Error fetching class data during subscribe: {e}")

        # Create or update class entry in database
        if class_data:
            # We got real data!
            db.update_class_state(class_key, class_data)
            status = class_data['status']
            enrolled = class_data['enrolled']
            capacity = class_data['capacity']
            status_text = f"**{status}**"
            if capacity > 0:
                status_text += f" ({enrolled}/{capacity})"
        else:
            # Couldn't fetch data, create placeholder
            placeholder_data = {
                'subject': subject,
                'catalog_number': course,
                'status': 'Unknown',
                'enrolled': 0,
                'capacity': 0,
                'waitlist_count': 0,
                'waitlist_capacity': 0,
                'last_checked': datetime.now().isoformat()
            }
            db.update_class_state(class_key, placeholder_data)
            status_text = "**Unknown** (will check in next update)"

        # Add subscription
        success = db.add_subscription(user_id, class_key)

        if success:
            # Send confirmation message with current status
            await interaction.followup.send(
                f"✅ Subscribed to **{subject} {course}**!\n"
                f"📊 Current status: {status_text}\n\n"
                f"I'll send you a DM when this class has open spots.\n"
                f"*Use `/unsubscribe {subject} {course}` to stop notifications.*",
                ephemeral=True
            )

            # Try to DM user as well
            try:
                await interaction.user.send(
                    f"✅ You're now subscribed to **{subject} {course}**!\n"
                    f"📊 Current status: {status_text}\n\n"
                    f"I'll send you a DM when this class has open spots."
                )
            except discord.Forbidden:
                # User has DMs disabled, that's okay - we already showed them the message
                pass
        else:
            await interaction.followup.send(
                f"❌ Failed to subscribe to {subject} {course}. Please try again.",
                ephemeral=True
            )

    except Exception as e:
        print(f"Error in subscribe command: {e}")
        await interaction.followup.send(
            f"❌ An error occurred while subscribing. Please try again.",
            ephemeral=True
        )


@bot.tree.command(name="unsubscribe", description="Stop receiving notifications for a class")
@app_commands.describe(
    subject="Subject code (e.g., PSYCH, COM SCI)",
    course="Course number (e.g., 124G, 111)"
)
async def unsubscribe(interaction: discord.Interaction, subject: str, course: str):
    """Unsubscribe from class notifications"""
    subject = subject.upper().strip()
    course = course.upper().strip()
    class_key = make_class_key(subject, course)
    user_id = str(interaction.user.id)

    # Check if subscribed
    user_subs = db.get_user_subscriptions(user_id)
    if class_key not in user_subs:
        await interaction.response.send_message(
            f"ℹ️ You're not subscribed to {subject} {course}.",
            ephemeral=True
        )
        return

    # Remove subscription
    success = db.remove_subscription(user_id, class_key)

    if success:
        await interaction.response.send_message(
            f"✅ Unsubscribed from {subject} {course}.",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"❌ Failed to unsubscribe from {subject} {course}. Please try again.",
            ephemeral=True
        )


@bot.tree.command(name="list", description="Show all classes you're subscribed to")
async def list_subscriptions(interaction: discord.Interaction):
    """List user's subscribed classes"""
    user_id = str(interaction.user.id)
    user_subs = db.get_user_subscriptions(user_id)

    if not user_subs:
        await interaction.response.send_message(
            "📭 You're not subscribed to any classes.\n"
            "Use `/subscribe` to get notified when classes open!",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="📚 Your Subscribed Classes",
        description=f"You're monitoring **{len(user_subs)}** class(es)",
        color=0x2b7de9,
        timestamp=datetime.now()
    )

    for class_key in user_subs:
        subject, course = parse_class_key(class_key)
        class_state = db.get_class_state(class_key)

        if class_state:
            status = class_state['status']
            enrolled = class_state['enrolled']
            capacity = class_state['capacity']

            status_emoji = {
                'Open': '✅',
                'Full': '🔴',
                'Closed': '⛔',
                'Waitlist Available': '⏳'
            }.get(status, 'ℹ️')

            embed.add_field(
                name=f"{status_emoji} {subject} {course}",
                value=f"Status: **{status}**\nEnrollment: {enrolled}/{capacity}",
                inline=False
            )
        else:
            embed.add_field(
                name=f"📌 {subject} {course}",
                value="Status: *Not checked yet*",
                inline=False
            )

    embed.set_footer(text="Use /unsubscribe to remove classes")

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="status", description="Check status of all your subscribed classes")
async def check_all_status(interaction: discord.Interaction):
    """Check current status of all subscribed classes"""
    await interaction.response.defer(thinking=True)

    user_id = str(interaction.user.id)
    user_subs = db.get_user_subscriptions(user_id)

    if not user_subs:
        await interaction.followup.send(
            "📭 You're not subscribed to any classes.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="📊 Current Class Status",
        description=f"Checking {len(user_subs)} class(es)...",
        color=0x2b7de9,
        timestamp=datetime.now()
    )

    for class_key in user_subs:
        subject, course = parse_class_key(class_key)
        class_state = db.get_class_state(class_key)

        if class_state:
            status = class_state['status']
            enrolled = class_state['enrolled']
            capacity = class_state['capacity']
            last_checked = class_state.get('last_checked', 'Unknown')

            status_emoji = {
                'Open': '✅',
                'Full': '🔴',
                'Closed': '⛔',
                'Waitlist Available': '⏳'
            }.get(status, 'ℹ️')

            embed.add_field(
                name=f"{status_emoji} {subject} {course}",
                value=f"**{status}** - {enrolled}/{capacity}\n*Last checked: {last_checked[:16]}*",
                inline=False
            )
        else:
            embed.add_field(
                name=f"📌 {subject} {course}",
                value="*Not monitored yet*",
                inline=False
            )

    embed.set_footer(text="Classes are checked every 5 minutes by GitHub Actions")

    await interaction.followup.send(embed=embed, ephemeral=True)


# ==================== Background Tasks ====================

@tasks.loop(minutes=5)
async def check_class_changes():
    """
    Background task to check for class status changes and notify users.
    Runs every 5 minutes in sync with GitHub Actions.
    """
    try:
        # Get all classes that recently changed status
        all_classes = db.get_all_class_states()

        for class_state in all_classes:
            class_key = class_state['class_key']
            current_status = class_state['status']

            # Check if class recently became available
            if current_status in ['Open', 'Waitlist Available']:
                # Get subscribers
                subscribers = db.get_subscribers_for_class(class_key)

                if subscribers:
                    subject, course = parse_class_key(class_key)

                    # Create notification embed
                    embed = discord.Embed(
                        title=f"🎉 Class Available: {subject} {course}",
                        description=f"**Status:** {current_status}",
                        color=0x00ff00,
                        timestamp=datetime.now()
                    )

                    if class_state['capacity'] > 0:
                        embed.add_field(
                            name="Enrollment",
                            value=f"{class_state['enrolled']}/{class_state['capacity']}",
                            inline=True
                        )

                    embed.set_footer(text="Act fast! Enroll before spots fill up.")

                    # Notify each subscriber
                    for user_id in subscribers:
                        try:
                            user = await bot.fetch_user(int(user_id))
                            await user.send(embed=embed)
                            print(f"✅ Notified user {user_id} about {class_key}")
                        except discord.Forbidden:
                            print(f"⚠️ Cannot DM user {user_id} - DMs disabled")
                        except discord.NotFound:
                            print(f"⚠️ User {user_id} not found")
                        except Exception as e:
                            print(f"❌ Error notifying user {user_id}: {e}")

                        # Rate limit: small delay between DMs
                        await asyncio.sleep(1)

    except Exception as e:
        print(f"❌ Error in background task: {e}")


@check_class_changes.before_loop
async def before_check_class_changes():
    """Wait for bot to be ready before starting background task"""
    await bot.wait_until_ready()


# ==================== Main ====================

if __name__ == "__main__":
    # Get bot token from environment
    token = os.environ.get('DISCORD_TOKEN')

    if not token:
        print("❌ Error: DISCORD_TOKEN environment variable not set")
        exit(1)

    # Run bot
    bot.run(token)
