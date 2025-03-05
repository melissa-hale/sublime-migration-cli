#!/usr/bin/env python
"""Test script for feeds presentation layer."""
import os
from src.sublime_migration_cli.presentation.factory import create_formatter
from src.sublime_migration_cli.commands.get.refactored.feeds import fetch_all_feeds, get_feed_details

if __name__ == "__main__":
    # Make sure environment variables are set
    if not os.environ.get("SUBLIME_API_KEY"):
        print("Please set SUBLIME_API_KEY environment variable")
        exit(1)
        
    if not os.environ.get("SUBLIME_REGION"):
        print("Please set SUBLIME_REGION environment variable")
        exit(1)
    
    # Test the all feeds command
    print("\nTesting table format for all feeds:")
    fetch_all_feeds(formatter=create_formatter("table"))
    
    print("\nTesting JSON format for all feeds:")
    fetch_all_feeds(formatter=create_formatter("json"))
    
    # Get a valid feed ID from the first test
    feed_id = input("\nEnter a feed ID to test (or press Enter to skip): ")
    if feed_id:
        print(f"\nTesting table format for feed {feed_id}:")
        get_feed_details(feed_id, formatter=create_formatter("table"))
        
        print(f"\nTesting JSON format for feed {feed_id}:")
        get_feed_details(feed_id, formatter=create_formatter("json"))