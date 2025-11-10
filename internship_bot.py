"""
Discord Internship Tracker Bot
- Posts daily internship announcements
- Tracks user applications
- Provides statistics and search functionality
"""

import discord
from discord import app_commands
from discord.ext import tasks, commands
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import asyncio
from supabase import Client

class InternshipBot(commands.Bot):
    def __init__(self, supabase_client: Client):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(command_prefix='!intern ', intents=intents)
        self.supabase = supabase_client
        self.announcement_channel_id = int(os.getenv('INTERNSHIP_CHANNEL_ID', '0'))

    async def setup_hook(self):
        """Setup hook called when bot is ready"""
        # Start background tasks
        self.check_new_internships.start()

        # Sync slash commands
        try:
            synced = await self.tree.sync()
            print(f"✓ Internship Bot: Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"✗ Internship Bot: Failed to sync commands: {e}")

    async def on_ready(self):
        """Called when bot is ready"""
        print(f'✓ Internship Bot logged in as {self.user} (ID: {self.user.id})')
        print(f'  Announcement channel: {self.announcement_channel_id}')
        print('  Ready to track internships!')

    @tasks.loop(hours=1)
    async def check_new_internships(self):
        """Check for new internships every hour and post them"""
        try:
            # Skip if no channel configured
            if self.announcement_channel_id == 0:
                return

            # Get channel
            channel = self.get_channel(self.announcement_channel_id)
            if not channel:
                print(f"⚠ Warning: Could not find channel {self.announcement_channel_id}")
                return

            # Find new internships (not yet posted)
            new_jobs = await self.get_unposted_jobs()

            if not new_jobs:
                return

            print(f"📢 Found {len(new_jobs)} new internships to announce")

            # Post each job with buttons
            for job in new_jobs:
                try:
                    embed = self.create_job_embed(job)
                    view = JobActionView(self.supabase, job['id'])

                    message = await channel.send(embed=embed, view=view)

                    # Mark as posted
                    await self.mark_job_as_posted(job['id'], str(channel.id), str(message.id))

                    # Rate limiting: wait between posts
                    await asyncio.sleep(2)

                except Exception as e:
                    print(f"✗ Error posting job {job.get('id')}: {e}")

            print(f"✓ Posted {len(new_jobs)} new internships")

        except Exception as e:
            print(f"✗ Error in check_new_internships: {e}")

    @check_new_internships.before_loop
    async def before_check_new_internships(self):
        """Wait until bot is ready"""
        await self.wait_until_ready()

    async def get_unposted_jobs(self, limit: int = 30) -> List[Dict]:
        """Get jobs that haven't been posted to Discord yet"""
        try:
            # Get jobs from last 7 days
            week_ago = (datetime.now() - timedelta(days=7)).date().isoformat()

            # Query for unposted jobs
            response = self.supabase.table('intern_jobs').select('*').gte(
                'scraped_date', week_ago
            ).order('scraped_date', desc=True).limit(limit).execute()

            all_jobs = response.data

            # Filter out already posted jobs
            unposted_jobs = []
            for job in all_jobs:
                posted_response = self.supabase.table('intern_posted_jobs').select(
                    'id'
                ).eq('job_id', job['id']).execute()

                if not posted_response.data:
                    unposted_jobs.append(job)

            return unposted_jobs

        except Exception as e:
            print(f"✗ Error fetching unposted jobs: {e}")
            return []

    async def mark_job_as_posted(self, job_id: str, channel_id: str, message_id: str):
        """Mark a job as posted to Discord"""
        try:
            self.supabase.table('intern_posted_jobs').insert({
                'job_id': job_id,
                'discord_channel_id': channel_id,
                'discord_message_id': message_id
            }).execute()
        except Exception as e:
            print(f"✗ Error marking job as posted: {e}")

    def create_job_embed(self, job: Dict) -> discord.Embed:
        """Create a rich embed for a job posting"""
        # Color based on relevance score
        score = job.get('relevance_score', 0)
        if score >= 15:
            color = discord.Color.green()
        elif score >= 10:
            color = discord.Color.blue()
        else:
            color = discord.Color.light_grey()

        embed = discord.Embed(
            title=job['title'],
            url=job['url'],
            description=self._truncate_description(job.get('description', '')),
            color=color,
            timestamp=datetime.now()
        )

        embed.set_author(name=job['company'])

        # Add fields
        if job.get('location'):
            embed.add_field(name="📍 Location", value=job['location'], inline=True)

        if job.get('salary'):
            embed.add_field(name="💰 Salary", value=job['salary'], inline=True)

        if job.get('source'):
            embed.add_field(name="🔗 Source", value=job['source'], inline=True)

        if job.get('posted_date'):
            embed.add_field(name="📅 Posted", value=job['posted_date'], inline=True)

        # Relevance score
        embed.add_field(
            name="⭐ Relevance",
            value=f"{score}/20",
            inline=True
        )

        embed.set_footer(text=f"Job ID: {job['id']}")

        return embed

    def _truncate_description(self, description: str, max_length: int = 300) -> str:
        """Truncate description to fit embed limits"""
        if not description:
            return "_No description available_"

        if len(description) <= max_length:
            return description

        return description[:max_length] + "..."


class JobActionView(discord.ui.View):
    """Interactive buttons for job postings"""

    def __init__(self, supabase_client: Client, job_id: str):
        super().__init__(timeout=None)  # Persistent view
        self.supabase = supabase_client
        self.job_id = job_id

    @discord.ui.button(label="✅ Mark Applied", style=discord.ButtonStyle.green, custom_id="mark_applied")
    async def mark_applied(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Mark job as applied"""
        try:
            user_id = str(interaction.user.id)

            # Ensure user exists
            await self.ensure_user_exists(user_id, interaction.user.name)

            # Check if already applied
            existing = self.supabase.table('intern_applications').select('id').eq(
                'user_discord_id', user_id
            ).eq('job_id', self.job_id).execute()

            if existing.data:
                await interaction.response.send_message(
                    "✓ You've already marked this as applied!",
                    ephemeral=True
                )
                return

            # Insert application
            self.supabase.table('intern_applications').insert({
                'user_discord_id': user_id,
                'job_id': self.job_id,
                'status': 'applied'
            }).execute()

            await interaction.response.send_message(
                "✓ Marked as applied! Use `/stats` to see your progress.",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(
                f"✗ Error: {e}",
                ephemeral=True
            )

    async def ensure_user_exists(self, discord_id: str, username: str):
        """Ensure user exists in database"""
        try:
            self.supabase.table('intern_users').upsert({
                'discord_id': discord_id,
                'username': username
            }, on_conflict='discord_id').execute()
        except Exception as e:
            print(f"✗ Error ensuring user exists: {e}")


def setup_commands(bot: InternshipBot):
    """Setup slash commands"""

    @bot.tree.command(name="internships", description="View recent internship postings")
    @app_commands.describe(limit="Number of internships to show (default: 10)")
    async def internships(interaction: discord.Interaction, limit: int = 10):
        """View recent internships"""
        try:
            await interaction.response.defer()

            # Fetch recent jobs
            response = bot.supabase.table('intern_jobs').select('*').order(
                'scraped_date', desc=True
            ).limit(min(limit, 25)).execute()

            jobs = response.data

            if not jobs:
                await interaction.followup.send("No internships found.")
                return

            # Create embeds (max 10 per message)
            embeds = [bot.create_job_embed(job) for job in jobs[:10]]

            await interaction.followup.send(
                f"**Latest {len(embeds)} Internships:**",
                embeds=embeds
            )

        except Exception as e:
            await interaction.followup.send(f"✗ Error: {e}")

    @bot.tree.command(name="applied", description="View your application history")
    async def applied(interaction: discord.Interaction):
        """View user's applications"""
        try:
            await interaction.response.defer(ephemeral=True)

            user_id = str(interaction.user.id)

            # Fetch applications with job details
            response = bot.supabase.table('intern_applications').select(
                '*, intern_jobs(*)'
            ).eq('user_discord_id', user_id).order('applied_at', desc=True).execute()

            applications = response.data

            if not applications:
                await interaction.followup.send(
                    "You haven't marked any applications yet!\nUse the ✅ button on job postings to track your applications.",
                    ephemeral=True
                )
                return

            # Create embed
            embed = discord.Embed(
                title="📋 Your Applications",
                description=f"Total: {len(applications)} applications",
                color=discord.Color.blue()
            )

            for app in applications[:15]:  # Show last 15
                job = app.get('intern_jobs', {})
                if job:
                    status_emoji = {
                        'applied': '📤',
                        'interviewing': '💼',
                        'offer': '🎉',
                        'rejected': '❌',
                        'withdrawn': '🚫'
                    }.get(app['status'], '📤')

                    embed.add_field(
                        name=f"{status_emoji} {job.get('company', 'Unknown')}",
                        value=f"{job.get('title', 'Unknown')}\nApplied: {app['applied_at'][:10]}",
                        inline=True
                    )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"✗ Error: {e}", ephemeral=True)

    @bot.tree.command(name="stats", description="View your application statistics")
    async def stats(interaction: discord.Interaction):
        """View user statistics"""
        try:
            await interaction.response.defer(ephemeral=True)

            user_id = str(interaction.user.id)

            # Fetch from view
            response = bot.supabase.table('intern_user_stats').select('*').eq(
                'discord_id', user_id
            ).execute()

            if not response.data:
                await interaction.followup.send(
                    "You haven't tracked any applications yet!",
                    ephemeral=True
                )
                return

            stats = response.data[0]

            # Create embed
            embed = discord.Embed(
                title=f"📊 Statistics for {interaction.user.name}",
                color=discord.Color.gold()
            )

            embed.add_field(
                name="📈 Total Applications",
                value=str(stats['total_applications']),
                inline=True
            )
            embed.add_field(
                name="🏢 Unique Companies",
                value=str(stats['unique_companies']),
                inline=True
            )
            embed.add_field(
                name="📅 This Week",
                value=str(stats['applications_this_week']),
                inline=True
            )
            embed.add_field(
                name="📆 This Month",
                value=str(stats['applications_this_month']),
                inline=True
            )

            # Status breakdown
            embed.add_field(
                name="📤 Applied",
                value=str(stats['applied_count']),
                inline=True
            )
            embed.add_field(
                name="💼 Interviewing",
                value=str(stats['interviewing_count']),
                inline=True
            )
            embed.add_field(
                name="🎉 Offers",
                value=str(stats['offer_count']),
                inline=True
            )
            embed.add_field(
                name="❌ Rejected",
                value=str(stats['rejected_count']),
                inline=True
            )

            # Timeline
            if stats.get('first_application'):
                embed.add_field(
                    name="📅 First Application",
                    value=stats['first_application'][:10],
                    inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"✗ Error: {e}", ephemeral=True)

    @bot.tree.command(name="search", description="Search for internships by keyword")
    @app_commands.describe(keyword="Search term (company, role, location)")
    async def search(interaction: discord.Interaction, keyword: str):
        """Search internships"""
        try:
            await interaction.response.defer()

            # Search in title, company, location, description
            response = bot.supabase.table('intern_jobs').select('*').or_(
                f"title.ilike.%{keyword}%,company.ilike.%{keyword}%,location.ilike.%{keyword}%"
            ).order('relevance_score', desc=True).limit(10).execute()

            jobs = response.data

            if not jobs:
                await interaction.followup.send(f"No internships found matching '{keyword}'")
                return

            embeds = [bot.create_job_embed(job) for job in jobs[:10]]

            await interaction.followup.send(
                f"**Search results for '{keyword}':** ({len(jobs)} found)",
                embeds=embeds
            )

        except Exception as e:
            await interaction.followup.send(f"✗ Error: {e}")


def create_bot(supabase_client: Client) -> InternshipBot:
    """Factory function to create and configure the bot"""
    bot = InternshipBot(supabase_client)
    setup_commands(bot)
    return bot
