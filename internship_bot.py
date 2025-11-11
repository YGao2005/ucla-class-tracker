"""
Discord Internship Tracker Bot - Version 2 with Improved UX
- Compact list views with select menus
- Smart filtering (unapplied jobs only)
- New commands: /today, /recent
"""

import discord
from discord import app_commands
from discord.ext import tasks, commands
import os
from datetime import datetime, timedelta, time
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

    @tasks.loop(time=time(hour=0, minute=30, second=0))  # 4:30 PM PST = 00:30 UTC (30 min after scraper at 00:00 UTC)
    async def check_new_internships(self):
        """Check for new internships once daily at 4:30 PM PST (00:30 UTC) and post them"""
        try:
            if self.announcement_channel_id == 0:
                return

            channel = self.get_channel(self.announcement_channel_id)
            if not channel:
                print(f"⚠ Warning: Could not find channel {self.announcement_channel_id}")
                return

            new_jobs = await self.get_unposted_jobs()

            if not new_jobs:
                print("📭 No new internships posted today")
                return

            print(f"📢 Found {len(new_jobs)} new internships to announce")

            for job in new_jobs:
                try:
                    embed = self.create_job_embed(job)
                    view = JobActionView(self.supabase, job['id'])

                    message = await channel.send(embed=embed, view=view)
                    await self.mark_job_as_posted(job['id'], str(channel.id), str(message.id))
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
        """Get jobs that haven't been posted to Discord yet - ONLY jobs posted today by companies"""
        try:
            # Get jobs posted TODAY by companies (not scraped today)
            today = datetime.now().date().isoformat()

            # Fetch jobs where posted_date is today
            response = self.supabase.table('intern_jobs').select('*').eq(
                'posted_date', today
            ).order('relevance_score', desc=True).limit(limit).execute()

            all_jobs = response.data

            # Filter out jobs already posted to Discord
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
        """Create a concise embed for a job posting (no description)"""
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
            color=color,
            timestamp=datetime.now()
        )

        embed.set_author(name=job['company'])

        if job.get('location'):
            embed.add_field(name="📍 Location", value=job['location'], inline=True)

        if job.get('salary'):
            embed.add_field(name="💰 Salary", value=job['salary'], inline=True)

        if job.get('source'):
            embed.add_field(name="🔗 Source", value=job['source'], inline=True)

        if job.get('posted_date'):
            embed.add_field(name="📅 Posted", value=job['posted_date'], inline=True)

        embed.add_field(name="⭐ Relevance", value=f"{score}/20", inline=True)
        embed.set_footer(text=f"Job ID: {job['id']}")

        return embed

    def _truncate_description(self, description: str, max_length: int = 300) -> str:
        """Truncate description to fit embed limits"""
        if not description:
            return "_No description available_"

        if len(description) <= max_length:
            return description

        return description[:max_length] + "..."

    def create_compact_job_text(self, job: Dict, index: int) -> str:
        """Create compact one-line job description for lists"""
        score = job.get('relevance_score', 0)
        location = job.get('location', 'Not specified')[:20]  # Truncate long locations

        return f"{index}. **{job['title']}** @ {job['company']}\n   📍 {location} • ⭐ {score}/20 • [Apply]({job['url']})"


class JobActionView(discord.ui.View):
    """Interactive buttons for individual job postings (for auto-announcements)"""

    def __init__(self, supabase_client: Client, job_id: str):
        super().__init__(timeout=None)
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


class JobSelectView(discord.ui.View):
    """Select menu for marking multiple jobs as applied"""

    def __init__(self, supabase_client: Client, jobs: List[Dict], user_id: str):
        super().__init__(timeout=300)  # 5 minute timeout
        self.supabase = supabase_client
        self.jobs = jobs
        self.user_id = user_id

        # Create select menu options
        options = []
        for i, job in enumerate(jobs[:25], 1):  # Discord max 25 options
            label = f"{i}. {job['company']}: {job['title']}"[:100]  # Max 100 chars
            description = f"{job.get('location', 'Remote')}"[:100]
            options.append(discord.SelectOption(
                label=label,
                description=description,
                value=job['id']
            ))

        # Add select menu
        select = discord.ui.Select(
            placeholder="Select jobs you've applied to...",
            min_values=1,
            max_values=len(options),
            options=options,
            custom_id="job_select"
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        """Handle job selection"""
        try:
            selected_job_ids = interaction.data['values']

            # Ensure user exists
            self.supabase.table('intern_users').upsert({
                'discord_id': self.user_id,
                'username': interaction.user.name
            }, on_conflict='discord_id').execute()

            # Check which jobs are already applied
            existing_response = self.supabase.table('intern_applications').select('job_id').eq(
                'user_discord_id', self.user_id
            ).in_('job_id', selected_job_ids).execute()

            existing_ids = {app['job_id'] for app in existing_response.data}
            new_ids = [jid for jid in selected_job_ids if jid not in existing_ids]

            # Insert new applications
            if new_ids:
                applications = [{
                    'user_discord_id': self.user_id,
                    'job_id': job_id,
                    'status': 'applied'
                } for job_id in new_ids]

                self.supabase.table('intern_applications').insert(applications).execute()

            # Build response
            response_lines = []
            if new_ids:
                response_lines.append(f"✓ Marked **{len(new_ids)}** new application(s)!")
            if existing_ids:
                response_lines.append(f"ℹ️ {len(existing_ids)} already marked")

            response_lines.append(f"\n📊 Total applications: {len(existing_ids) + len(new_ids)}")
            response_lines.append("Use `/stats` to see your progress!")

            await interaction.response.send_message(
                "\n".join(response_lines),
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(
                f"✗ Error: {e}",
                ephemeral=True
            )


def setup_commands(bot: InternshipBot):
    """Setup slash commands"""

    @bot.tree.command(name="internships", description="View top unapplied internships by relevance")
    @app_commands.describe(limit="Number of internships to show (default: 10, max: 25)")
    async def internships(interaction: discord.Interaction, limit: int = 10):
        """View unapplied internships sorted by relevance"""
        try:
            await interaction.response.defer()

            user_id = str(interaction.user.id)
            limit = min(limit, 25)

            # Get user's applied job IDs
            applied_response = bot.supabase.table('intern_applications').select('job_id').eq(
                'user_discord_id', user_id
            ).execute()

            applied_ids = {app['job_id'] for app in applied_response.data}

            # Fetch all jobs sorted by relevance
            response = bot.supabase.table('intern_jobs').select('*').order(
                'relevance_score', desc=True
            ).limit(100).execute()  # Get more to filter

            # Filter out applied jobs
            unapplied_jobs = [job for job in response.data if job['id'] not in applied_ids][:limit]

            if not unapplied_jobs:
                await interaction.followup.send(
                    "🎉 You've applied to all available internships!\nCheck back later for new postings."
                )
                return

            # Create compact list embed
            embed = discord.Embed(
                title="📋 Top Unapplied Internships",
                description=f"Showing {len(unapplied_jobs)} most relevant internships you haven't applied to yet.",
                color=discord.Color.blue()
            )

            # Add jobs as fields
            job_list = "\n\n".join([
                bot.create_compact_job_text(job, i)
                for i, job in enumerate(unapplied_jobs, 1)
            ])

            # Split into chunks if too long (Discord 4096 char limit)
            if len(job_list) > 4000:
                job_list = "\n\n".join([
                    bot.create_compact_job_text(job, i)
                    for i, job in enumerate(unapplied_jobs[:10], 1)
                ])
                embed.set_footer(text="Showing first 10 results")
                unapplied_jobs = unapplied_jobs[:10]

            embed.description += f"\n\n{job_list}"

            # Add select menu view
            view = JobSelectView(bot.supabase, unapplied_jobs, user_id)

            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            await interaction.followup.send(f"✗ Error: {e}")

    @bot.tree.command(name="today", description="View internships posted today")
    async def today(interaction: discord.Interaction):
        """View internships posted/scraped today"""
        try:
            await interaction.response.defer()

            user_id = str(interaction.user.id)
            today = datetime.now().date().isoformat()

            # Fetch jobs from today
            response = bot.supabase.table('intern_jobs').select('*').eq(
                'scraped_date', today
            ).order('relevance_score', desc=True).execute()

            jobs = response.data

            if not jobs:
                await interaction.followup.send(
                    f"📭 No new internships posted today ({datetime.now().strftime('%B %d, %Y')}).\n"
                    "Check back tomorrow!"
                )
                return

            # Create compact list embed
            embed = discord.Embed(
                title=f"📅 Today's Internships ({datetime.now().strftime('%b %d')})",
                description=f"Found {len(jobs)} new internship(s) today!",
                color=discord.Color.gold()
            )

            job_list = "\n\n".join([
                bot.create_compact_job_text(job, i)
                for i, job in enumerate(jobs[:25], 1)  # Max 25 for select menu
            ])

            if len(job_list) > 4000:
                job_list = "\n\n".join([
                    bot.create_compact_job_text(job, i)
                    for i, job in enumerate(jobs[:10], 1)
                ])
                embed.set_footer(text="Showing first 10 results")
                jobs = jobs[:10]

            embed.description += f"\n\n{job_list}"

            # Add select menu
            view = JobSelectView(bot.supabase, jobs, user_id)

            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            await interaction.followup.send(f"✗ Error: {e}")

    @bot.tree.command(name="recent", description="View most recent internships")
    @app_commands.describe(count="Number of internships to show (default: 10, max: 25)")
    async def recent(interaction: discord.Interaction, count: int = 10):
        """View most recent internships"""
        try:
            await interaction.response.defer()

            user_id = str(interaction.user.id)
            count = min(count, 25)

            # Fetch recent jobs
            response = bot.supabase.table('intern_jobs').select('*').order(
                'scraped_date', desc=True
            ).limit(count).execute()

            jobs = response.data

            if not jobs:
                await interaction.followup.send("No internships found.")
                return

            # Create compact list embed
            embed = discord.Embed(
                title="🕐 Recent Internships",
                description=f"Showing {len(jobs)} most recently posted internship(s).",
                color=discord.Color.purple()
            )

            job_list = "\n\n".join([
                bot.create_compact_job_text(job, i)
                for i, job in enumerate(jobs, 1)
            ])

            embed.description += f"\n\n{job_list}"

            # Add select menu
            view = JobSelectView(bot.supabase, jobs, user_id)

            await interaction.followup.send(embed=embed, view=view)

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
                    "You haven't marked any applications yet!\n"
                    "Use `/internships` to browse jobs and mark them as applied.",
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

            user_id = str(interaction.user.id)

            # Search in title, company, location, description
            response = bot.supabase.table('intern_jobs').select('*').or_(
                f"title.ilike.%{keyword}%,company.ilike.%{keyword}%,location.ilike.%{keyword}%"
            ).order('relevance_score', desc=True).limit(25).execute()

            jobs = response.data

            if not jobs:
                await interaction.followup.send(f"No internships found matching '{keyword}'")
                return

            # Create compact list embed
            embed = discord.Embed(
                title=f"🔍 Search Results: '{keyword}'",
                description=f"Found {len(jobs)} matching internship(s).",
                color=discord.Color.green()
            )

            job_list = "\n\n".join([
                bot.create_compact_job_text(job, i)
                for i, job in enumerate(jobs, 1)
            ])

            if len(job_list) > 4000:
                job_list = "\n\n".join([
                    bot.create_compact_job_text(job, i)
                    for i, job in enumerate(jobs[:10], 1)
                ])
                embed.set_footer(text="Showing first 10 results")
                jobs = jobs[:10]

            embed.description += f"\n\n{job_list}"

            # Add select menu
            view = JobSelectView(bot.supabase, jobs, user_id)

            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            await interaction.followup.send(f"✗ Error: {e}")


def create_bot(supabase_client: Client) -> InternshipBot:
    """Factory function to create and configure the bot"""
    bot = InternshipBot(supabase_client)
    setup_commands(bot)
    return bot
