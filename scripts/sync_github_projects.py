#!/usr/bin/env python3
"""
CLI Tool: Sync Recent GitHub Projects into Local Project Catalog

Usage:
    python scripts/sync_github_projects.py
    python scripts/sync_github_projects.py --limit 5
    python scripts/sync_github_projects.py --username SidhuManbirSingh --limit 10
    python scripts/sync_github_projects.py --force
"""
import argparse
import logging
import sys
from pathlib import Path

# Ensure backend modules can be imported
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.core.config import settings
from backend.services.github_sync import sync_github_projects


def main():
    parser = argparse.ArgumentParser(
        description="Check user's GitHub profile for newly added or updated projects and sync them to data/projects/."
    )
    parser.add_argument(
        "--username",
        type=str,
        default=settings.GITHUB_USERNAME,
        help=f"GitHub username to inspect (default: {settings.GITHUB_USERNAME})"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=settings.GITHUB_SYNC_LIMIT,
        help="Number of most recently pushed/updated repos to check (default: 5)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-scrape and overwrite existing project files even if already present"
    )
    parser.add_argument(
        "--token",
        type=str,
        default=settings.GITHUB_TOKEN,
        help="Optional GitHub personal access token to avoid rate limits"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    print(f"\n=== GitHub Project Catalog Sync ===")
    print(f"Target GitHub User: {args.username}")
    print(f"Checking Last {args.limit} Recently Pushed Repositories...")
    print(f"Output Directory:   {settings.PROJECTS_DIR}\n")

    new_projects = sync_github_projects(
        username=args.username,
        limit=args.limit,
        projects_dir=settings.PROJECTS_DIR,
        token=args.token,
        force=args.force
    )

    if new_projects:
        print(f"\n[SUCCESS] Synced {len(new_projects)} new project(s) into catalog:")
        for p in new_projects:
            print(f"  + Title:    {p['title']}")
            print(f"    File:     data/projects/{p['filename']}")
            print(f"    Domain:   {p['domain']}")
            print(f"    Pushed:   {p['pushed_at']}")
            print(f"    Stack:    {', '.join(p['technologies'][:5])}\n")
    else:
        print("\n[OK] All recent projects from GitHub are already represented in data/projects/.")
        print("     No new project files were needed.")


if __name__ == "__main__":
    main()

