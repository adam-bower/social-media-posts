"""
Import LinkedIn posts to Supabase for clip extraction training.
"""

import json
import os
from dotenv import load_dotenv

load_dotenv()


def main():
    from supabase import create_client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    client = create_client(url, key)

    # Load cleaned posts
    posts_path = "/Users/adambower/dev/windmill-server/data/linkedin_posts_cleaned.json"
    with open(posts_path, "r") as f:
        posts = json.load(f)

    print(f"Loaded {len(posts)} posts")

    # Prepare for insert
    records = []
    for post in posts:
        record = {
            "original_index": post.get("index", 0),
            "content": post.get("content", ""),
            "date_relative": post.get("date", ""),
            "estimated_date": post.get("estimated_date"),
            "likes": post.get("likes", 0),
            "comments": post.get("comments", 0),
            "reposts": post.get("reposts", 0),
            "has_media": post.get("has_media", False),
            "media_type": post.get("media_type", "") or None,
            "topics": post.get("topics", []),
            "tone": post.get("tone", ""),
            "post_type": post.get("post_type", ""),
            "engagement_level": post.get("engagement_level", ""),
            "word_count": post.get("word_count", len(post.get("content", "").split())),
        }
        records.append(record)

    # Insert in batches
    batch_size = 50
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        result = client.table("linkedin_posts").insert(batch).execute()
        print(f"Inserted batch {i // batch_size + 1}: {len(batch)} posts")

    print(f"\nDone! Imported {len(records)} posts to Supabase")

    # Show some stats
    high_engagement = [p for p in posts if p.get("likes", 0) >= 50]
    print(f"\nHigh engagement posts (50+ likes): {len(high_engagement)}")

    # Sample topics
    all_topics = set()
    for p in posts:
        all_topics.update(p.get("topics", []))
    print(f"Unique topics: {sorted(all_topics)}")


if __name__ == "__main__":
    main()
