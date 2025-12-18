"""
Set up database tables for Video Clipper.

Runs the SQL migration against Supabase to create required tables.

Usage:
    python scripts/setup_database.py
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def get_supabase_client():
    """Get Supabase client from environment."""
    from supabase import create_client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        raise ValueError(
            "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment"
        )

    return create_client(url, key)


def run_migration():
    """Run the SQL migration to create tables."""
    # Read SQL file
    sql_path = Path(__file__).parent / "create_tables.sql"
    with open(sql_path, "r") as f:
        sql = f.read()

    print("Connecting to Supabase...")
    client = get_supabase_client()

    # Split into individual statements (Supabase REST API doesn't support multi-statement)
    # We need to use the postgres connection directly or run via Supabase dashboard
    print("\nSQL Migration Script:")
    print("=" * 60)
    print("Copy and paste the following SQL into Supabase SQL Editor:")
    print("=" * 60)
    print(sql)
    print("=" * 60)

    # Test connection by checking if tables exist
    print("\nChecking existing tables...")

    try:
        result = client.table("videos").select("id").limit(1).execute()
        print("  - videos table: EXISTS")
    except Exception as e:
        if "does not exist" in str(e).lower() or "42P01" in str(e):
            print("  - videos table: NOT FOUND (needs creation)")
        else:
            print(f"  - videos table: ERROR - {e}")

    try:
        result = client.table("transcripts").select("id").limit(1).execute()
        print("  - transcripts table: EXISTS")
    except Exception as e:
        if "does not exist" in str(e).lower() or "42P01" in str(e):
            print("  - transcripts table: NOT FOUND (needs creation)")
        else:
            print(f"  - transcripts table: ERROR - {e}")

    try:
        result = client.table("clip_suggestions").select("id").limit(1).execute()
        print("  - clip_suggestions table: EXISTS")
    except Exception as e:
        if "does not exist" in str(e).lower() or "42P01" in str(e):
            print("  - clip_suggestions table: NOT FOUND (needs creation)")
        else:
            print(f"  - clip_suggestions table: ERROR - {e}")

    try:
        result = client.table("rendered_clips").select("id").limit(1).execute()
        print("  - rendered_clips table: EXISTS")
    except Exception as e:
        if "does not exist" in str(e).lower() or "42P01" in str(e):
            print("  - rendered_clips table: NOT FOUND (needs creation)")
        else:
            print(f"  - rendered_clips table: ERROR - {e}")

    print("\nTo create missing tables:")
    print("1. Go to your Supabase dashboard (db.ab-civil.com)")
    print("2. Open the SQL Editor")
    print("3. Paste the SQL above and run it")


if __name__ == "__main__":
    run_migration()
