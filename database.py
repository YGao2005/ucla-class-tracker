#!/usr/bin/env python3
"""
Supabase Database Integration
Shared by both GitHub Actions monitor and Discord bot
"""

import os
from typing import Dict, List, Optional
from datetime import datetime
from supabase import create_client, Client

# Initialize Supabase client
def get_supabase_client() -> Client:
    """Create and return Supabase client"""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables required")

    return create_client(url, key)


class Database:
    """Database operations for class monitoring"""

    def __init__(self):
        self.client = get_supabase_client()

    # ==================== Class State Operations ====================

    def get_class_state(self, class_key: str) -> Optional[Dict]:
        """
        Get current state of a class.

        Args:
            class_key: Format "SUBJECT_CATALOG" (e.g., "PSYCH_124G")

        Returns:
            Dictionary with class data or None if not found
        """
        try:
            response = self.client.table('class_states')\
                .select('*')\
                .eq('class_key', class_key)\
                .execute()

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
        except Exception as e:
            print(f"Error getting class state for {class_key}: {e}")
            return None

    def update_class_state(self, class_key: str, data: Dict) -> bool:
        """
        Update or insert class state.

        Args:
            class_key: Format "SUBJECT_CATALOG" (e.g., "PSYCH_124G")
            data: Dictionary with class information

        Returns:
            True if successful, False otherwise
        """
        try:
            # Prepare data for upsert
            record = {
                'class_key': class_key,
                'subject': data.get('subject'),
                'catalog_number': data.get('catalog_number'),
                'status': data.get('status'),
                'enrolled': data.get('enrolled', 0),
                'capacity': data.get('capacity', 0),
                'waitlist_count': data.get('waitlist_count', 0),
                'waitlist_capacity': data.get('waitlist_capacity', 0),
                'last_checked': data.get('last_checked', datetime.now().isoformat()),
                'updated_at': datetime.now().isoformat()
            }

            # Upsert (update if exists, insert if not)
            self.client.table('class_states')\
                .upsert(record, on_conflict='class_key')\
                .execute()

            return True
        except Exception as e:
            print(f"Error updating class state for {class_key}: {e}")
            return False

    def get_all_class_states(self) -> List[Dict]:
        """
        Get all monitored classes.

        Returns:
            List of class state dictionaries
        """
        try:
            response = self.client.table('class_states')\
                .select('*')\
                .order('subject', desc=False)\
                .order('catalog_number', desc=False)\
                .execute()

            return response.data if response.data else []
        except Exception as e:
            print(f"Error getting all class states: {e}")
            return []

    def get_subscribed_classes(self) -> List[Dict]:
        """
        Get all classes that have at least one subscription.

        Returns:
            List of dictionaries with 'subject' and 'catalog_number' keys
        """
        try:
            # Get distinct class_keys from user_subscriptions
            response = self.client.table('user_subscriptions')\
                .select('class_key')\
                .execute()

            if not response.data:
                return []

            # Get unique class keys
            class_keys = list(set(sub['class_key'] for sub in response.data))

            # Parse into subject and catalog_number
            classes = []
            for class_key in class_keys:
                subject, catalog_number = parse_class_key(class_key)
                classes.append({
                    'subject': subject,
                    'catalog_number': catalog_number,
                    'class_key': class_key
                })

            return classes
        except Exception as e:
            print(f"Error getting subscribed classes: {e}")
            return []

    def get_classes_by_status(self, status: str) -> List[Dict]:
        """
        Get all classes with a specific status.

        Args:
            status: Status to filter by (e.g., "Open", "Full", "Closed")

        Returns:
            List of matching classes
        """
        try:
            response = self.client.table('class_states')\
                .select('*')\
                .eq('status', status)\
                .execute()

            return response.data if response.data else []
        except Exception as e:
            print(f"Error getting classes by status {status}: {e}")
            return []

    # ==================== User Subscription Operations ====================

    def add_subscription(self, user_id: str, class_key: str) -> bool:
        """
        Subscribe a user to class notifications.

        Args:
            user_id: Discord user ID (as string)
            class_key: Format "SUBJECT_CATALOG"

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if subscription already exists
            existing = self.client.table('user_subscriptions')\
                .select('id')\
                .eq('user_id', user_id)\
                .eq('class_key', class_key)\
                .execute()

            if existing.data and len(existing.data) > 0:
                return True  # Already subscribed

            # Add new subscription
            self.client.table('user_subscriptions')\
                .insert({
                    'user_id': user_id,
                    'class_key': class_key,
                    'created_at': datetime.now().isoformat()
                })\
                .execute()

            return True
        except Exception as e:
            print(f"Error adding subscription for user {user_id} to {class_key}: {e}")
            return False

    def remove_subscription(self, user_id: str, class_key: str) -> bool:
        """
        Unsubscribe a user from class notifications.

        Args:
            user_id: Discord user ID (as string)
            class_key: Format "SUBJECT_CATALOG"

        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.table('user_subscriptions')\
                .delete()\
                .eq('user_id', user_id)\
                .eq('class_key', class_key)\
                .execute()

            return True
        except Exception as e:
            print(f"Error removing subscription for user {user_id} from {class_key}: {e}")
            return False

    def get_user_subscriptions(self, user_id: str) -> List[str]:
        """
        Get all classes a user is subscribed to.

        Args:
            user_id: Discord user ID (as string)

        Returns:
            List of class_keys
        """
        try:
            response = self.client.table('user_subscriptions')\
                .select('class_key')\
                .eq('user_id', user_id)\
                .execute()

            if response.data:
                return [sub['class_key'] for sub in response.data]
            return []
        except Exception as e:
            print(f"Error getting subscriptions for user {user_id}: {e}")
            return []

    def get_subscribers_for_class(self, class_key: str) -> List[str]:
        """
        Get all users subscribed to a specific class.

        Args:
            class_key: Format "SUBJECT_CATALOG"

        Returns:
            List of user IDs
        """
        try:
            response = self.client.table('user_subscriptions')\
                .select('user_id')\
                .eq('class_key', class_key)\
                .execute()

            if response.data:
                return [sub['user_id'] for sub in response.data]
            return []
        except Exception as e:
            print(f"Error getting subscribers for {class_key}: {e}")
            return []

    def get_subscription_count(self, class_key: str) -> int:
        """
        Get number of users subscribed to a class.

        Args:
            class_key: Format "SUBJECT_CATALOG"

        Returns:
            Number of subscribers
        """
        return len(self.get_subscribers_for_class(class_key))

    # ==================== Utility Functions ====================

    def delete_class_state(self, class_key: str) -> bool:
        """
        Delete a class from monitoring (and all its subscriptions).

        Args:
            class_key: Format "SUBJECT_CATALOG"

        Returns:
            True if successful
        """
        try:
            # Delete subscriptions first (foreign key constraint)
            self.client.table('user_subscriptions')\
                .delete()\
                .eq('class_key', class_key)\
                .execute()

            # Delete class state
            self.client.table('class_states')\
                .delete()\
                .eq('class_key', class_key)\
                .execute()

            return True
        except Exception as e:
            print(f"Error deleting class {class_key}: {e}")
            return False


# Helper function for creating class_key
def make_class_key(subject: str, catalog_number: str) -> str:
    """Create standardized class key from subject and catalog number"""
    return f"{subject}_{catalog_number}"


# Helper function for parsing class_key
def parse_class_key(class_key: str) -> tuple:
    """Parse class key into (subject, catalog_number)"""
    parts = class_key.split('_', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return class_key, ""
