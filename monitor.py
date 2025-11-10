#!/usr/bin/env python3
"""
UCLA Class Availability Monitor
Checks class availability using Playwright web scraping and sends Discord notifications.
"""

import asyncio
import json
import os
import re
import requests
from datetime import datetime
from typing import Dict, List, Optional
from playwright.async_api import async_playwright, Browser, Page
from database import Database


class UCLAClassMonitor:
    """Monitor UCLA class availability using Playwright web scraping."""

    BASE_URL = "https://sa.ucla.edu/ro/public/soc/Results"

    def __init__(self, config_path: str = "config.json"):
        """Initialize the monitor with config file and Supabase database."""
        self.config = self._load_json(config_path)
        self.db = Database()

    def _load_json(self, path: str, default: dict = None) -> dict:
        """Load JSON file, return default if it doesn't exist."""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return default if default is not None else {}

    def build_class_url(self, subject: str, term: str) -> str:
        """
        Build the UCLA Schedule of Classes URL for a subject.

        Args:
            subject: Subject code (e.g., "PSYCH")
            term: Term code (e.g., "25S" for Spring 2025)

        Returns:
            Full URL to the schedule page
        """
        # Ensure subject has proper spacing (UCLA expects padded format)
        subject_padded = subject.ljust(6)

        params = {
            't': term,
            'sBy': 'subject',
            'subj': subject_padded,
            'catlg': '',
            'cls_no': '',
            's_g_cd': '%'
        }

        param_str = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{self.BASE_URL}?{param_str}"

    async def scrape_class_data(
        self,
        page: Page,
        subject: str,
        catalog_number: str,
        term: str
    ) -> Optional[Dict]:
        """
        Scrape class data from UCLA Schedule of Classes page.

        Args:
            page: Playwright page object
            subject: Subject code (e.g., "PSYCH")
            catalog_number: Course catalog number (e.g., "124G")
            term: Term code

        Returns:
            Dictionary with class enrollment data, or None if not found
        """
        try:
            url = self.build_class_url(subject, term)
            print(f"  Loading {url}")

            # Navigate to the page
            await page.goto(url, wait_until='networkidle', timeout=30000)

            # Wait for the course list to load
            await page.wait_for_timeout(3000)

            # Find the button for this specific course
            # The button text contains the catalog number (e.g., "124G - Course Name")
            button_selector = f'button:has-text("{catalog_number}")'
            print(f"  Looking for course button: {catalog_number}")

            try:
                button = page.locator(button_selector).first
                await button.wait_for(state='visible', timeout=10000)
                print(f"  ✓ Found course button")

                # Click to expand the course details
                await button.click()
                print(f"  ✓ Clicked to expand details")

                # Wait for the enrollment data to load (AJAX call)
                await page.wait_for_timeout(4000)

                # Extract status from statusColumn
                class_data = await self._extract_status_from_page(page, subject, catalog_number)

                return class_data

            except Exception as e:
                print(f"  Course {subject} {catalog_number} not found or couldn't be expanded: {e}")
                return None

        except Exception as e:
            print(f"  Error scraping {subject} {catalog_number}: {e}")
            return None

    async def _extract_status_from_page(self, page: Page, subject: str, catalog_number: str) -> Dict:
        """
        Extract enrollment status from the expanded course section.

        Args:
            page: Playwright page object
            subject: Subject code
            catalog_number: Course catalog number

        Returns:
            Dictionary with enrollment status
        """
        # Find all statusColumn elements
        status_elements = await page.locator('div.statusColumn, .statusColumn').all()

        status = "Unknown"
        enrolled = 0
        capacity = 0

        # Look through status columns for enrollment data
        for elem in status_elements:
            text = await elem.text_content()
            if not text:
                continue

            text = text.strip()

            # Skip header rows
            if text == "Status":
                continue

            # Check for status keywords
            if "Open" in text:
                status = "Open"
            elif "Closed" in text:
                status = "Closed"

            # Extract enrollment numbers from patterns like "Class Full (50)"
            full_match = re.search(r'Class Full\s*\((\d+)\)', text)
            if full_match:
                capacity = int(full_match.group(1))
                enrolled = capacity
                status = "Full"

            # Check for other patterns like "45 of 50 Enrolled"
            enroll_match = re.search(r'(\d+)\s+of\s+(\d+)', text)
            if enroll_match:
                enrolled = int(enroll_match.group(1))
                capacity = int(enroll_match.group(2))

        # Check waitlist status
        waitlist_count = 0
        waitlist_capacity = 0

        waitlist_elements = await page.locator('div.waitlistColumn, .waitlistColumn').all()
        for elem in waitlist_elements:
            text = await elem.text_content()
            if not text:
                continue

            # Extract waitlist numbers
            waitlist_match = re.search(r'(\d+)\s+of\s+(\d+)', text.strip())
            if waitlist_match:
                waitlist_count = int(waitlist_match.group(1))
                waitlist_capacity = int(waitlist_match.group(2))
                break

        return {
            'subject': subject,
            'catalog_number': catalog_number,
            'status': status,
            'enrolled': enrolled,
            'capacity': capacity,
            'waitlist_count': waitlist_count,
            'waitlist_capacity': waitlist_capacity,
            'last_checked': datetime.now().isoformat()
        }

    def send_discord_notification(self, class_data: Dict, previous_status: str):
        """
        Send Discord webhook notification about class status change.
        Note: This is now primarily handled by the Discord bot, but kept for backward compatibility.

        Args:
            class_data: Current class data
            previous_status: Previous status of the class
        """
        webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')

        if not webhook_url:
            print("  Note: DISCORD_WEBHOOK_URL not set, Discord bot will handle notifications")
            return

        subject = class_data['subject']
        catalog = class_data['catalog_number']
        status = class_data['status']
        enrolled = class_data['enrolled']
        capacity = class_data['capacity']

        # Determine color based on status
        color_map = {
            'Open': 0x00ff00,  # Green
            'Waitlist Available': 0xffff00,  # Yellow
            'Full': 0xff0000,  # Red
            'Waitlist Full': 0xff0000,  # Red
            'Closed': 0x808080,  # Gray
            'Over-enrolled': 0xff6600,  # Orange
            'Unknown': 0x808080  # Gray
        }

        embed = {
            'title': f'🔔 Class Status Change: {subject} {catalog}',
            'description': f'Status changed from **{previous_status}** to **{status}**',
            'color': color_map.get(status, 0x808080),
            'fields': [
                {
                    'name': 'Enrollment',
                    'value': f'{enrolled}/{capacity}' if capacity > 0 else 'N/A',
                    'inline': True
                },
                {
                    'name': 'Status',
                    'value': status,
                    'inline': True
                },
                {
                    'name': 'Checked At',
                    'value': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'inline': False
                }
            ],
            'footer': {
                'text': 'UCLA Class Monitor'
            }
        }

        if class_data['waitlist_capacity'] > 0:
            embed['fields'].insert(1, {
                'name': 'Waitlist',
                'value': f"{class_data['waitlist_count']}/{class_data['waitlist_capacity']}",
                'inline': True
            })

        payload = {
            'embeds': [embed]
        }

        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            print(f"  ✓ Discord webhook notification sent for {subject} {catalog}")
        except requests.RequestException as e:
            print(f"  Error sending Discord webhook notification: {e}")

    async def get_browser(self):
        """
        Get a Playwright browser and page instance.
        Use with async context manager for proper cleanup.

        Example:
            async with monitor.get_browser() as (browser, page):
                data = await monitor.scrape_class_data(page, "PSYCH", "124G", "26W")
        """
        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            yield (browser, page)
        finally:
            await browser.close()
            await p.stop()

    async def check_classes(self):
        """Check all subscribed classes for availability changes using Playwright."""
        term = self.config.get('term', '26W')

        # Get classes from database (all classes with at least one subscription)
        classes = self.db.get_subscribed_classes()

        if not classes:
            print("No classes with subscriptions to monitor")
            print("Tip: Use the Discord bot's /subscribe command to add classes")
            return

        print(f"Checking {len(classes)} subscribed class(es) for term {term}...")

        async with async_playwright() as p:
            # Launch browser in headless mode
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            for class_info in classes:
                subject = class_info.get('subject')
                catalog_number = class_info.get('catalog_number')
                class_key = class_info.get('class_key')

                if not subject or not catalog_number:
                    print(f"Skipping invalid class: {class_info}")
                    continue

                print(f"\nChecking {subject} {catalog_number}...")

                # Scrape current class data
                class_data = await self.scrape_class_data(page, subject, catalog_number, term)

                if not class_data:
                    print(f"  ✗ Failed to fetch data")
                    continue

                current_status = class_data['status']
                print(f"  Status: {current_status} ({class_data['enrolled']}/{class_data['capacity']})")

                # Get previous state from Supabase
                previous_data = self.db.get_class_state(class_key)
                previous_status = previous_data.get('status') if previous_data else None

                if previous_status and previous_status != current_status:
                    print(f"  🔔 Status changed: {previous_status} → {current_status}")
                    self.send_discord_notification(class_data, previous_status)
                    print(f"  💾 Status change saved to database - Discord bot will notify subscribers")
                elif not previous_status:
                    print(f"  ℹ First check, establishing baseline in database")
                else:
                    print(f"  No change")

                # Update state in Supabase
                success = self.db.update_class_state(class_key, class_data)
                if success:
                    print(f"  ✓ Updated database")
                else:
                    print(f"  ✗ Failed to update database")

            await browser.close()

        print(f"\n✓ Check complete at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


async def main():
    """Main entry point for the script."""
    print("=" * 60)
    print("UCLA Class Availability Monitor (Playwright)")
    print("=" * 60)

    monitor = UCLAClassMonitor()
    await monitor.check_classes()


if __name__ == "__main__":
    asyncio.run(main())
