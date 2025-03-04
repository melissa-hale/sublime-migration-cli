#!/usr/bin/env python
"""Test script for lists presentation layer."""
import os
from src.sublime_migration_cli.presentation.factory import create_formatter
from src.sublime_migration_cli.commands.get.refactored.lists import fetch_all_lists, get_list_details

if __name__ == "__main__":
    # Make sure environment variables are set
    if not os.environ.get("SUBLIME_API_KEY"):
        print("Please set SUBLIME_API_KEY environment variable")
        exit(1)
        
    if not os.environ.get("SUBLIME_REGION"):
        print("Please set SUBLIME_REGION environment variable")
        exit(1)
    
    # Test the all lists command
    print("\nTesting table format for all lists:")
    fetch_all_lists(formatter=create_formatter("table"))
    
    print("\nTesting table format with fetch_details:")
    fetch_all_lists(fetch_details=True, formatter=create_formatter("table"))
    
    print("\nTesting JSON format for all lists:")
    fetch_all_lists(formatter=create_formatter("json"))
    
    # Get a valid list ID from the first test
    list_id = input("\nEnter a list ID to test (or press Enter to skip): ")
    if list_id:
        print(f"\nTesting table format for list {list_id}:")
        get_list_details(list_id, formatter=create_formatter("table"))
        
        print(f"\nTesting JSON format for list {list_id}:")
        get_list_details(list_id, formatter=create_formatter("json"))