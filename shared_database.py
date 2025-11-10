"""
Shared Database Module
Provides a single Supabase client instance for both bots
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Global Supabase client instance
_supabase_client: Client = None


def get_supabase_client() -> Client:
    """
    Get or create the shared Supabase client instance

    Returns:
        Client: Supabase client instance

    Raises:
        ValueError: If Supabase credentials are not set
    """
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    # Get credentials from environment
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError(
            "Missing Supabase credentials. "
            "Set SUPABASE_URL and SUPABASE_KEY environment variables."
        )

    # Create client
    _supabase_client = create_client(supabase_url, supabase_key)
    print("✓ Shared Supabase client initialized")

    return _supabase_client


def close_supabase_client():
    """Close the Supabase client connection"""
    global _supabase_client

    if _supabase_client is not None:
        # Supabase client doesn't need explicit closing, but we can reset it
        _supabase_client = None
        print("✓ Supabase client connection closed")
