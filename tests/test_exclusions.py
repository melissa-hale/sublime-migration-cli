#!/usr/bin/env python
"""Test script for exclusions presentation layer."""
import os
from src.sublime_migration_cli.presentation.factory import create_formatter
from src.sublime_migration_cli.commands.get.refactored.exclusions import fetch_all_exclusions, get_exclusion_details

if __name__ == "__main__":
    # Make sure environment variables are set
    if not os.environ.get("SUBLIME_API_KEY"):
        print("Please set SUBLIME_API_KEY environment variable")
        exit(1)
        
    if not os.environ.get("SUBLIME_REGION"):
        print("Please set SUBLIME_REGION environment variable")
        exit(1)
    
    # Test the all exclusions command
    print("\nTesting table format for all exclusions:")
    fetch_all_exclusions(formatter=create_formatter("table"))
    
    print("\nTesting table format with scope filter:")
    fetch_all_exclusions(scope="exclusion", formatter=create_formatter("table"))
    
    print("\nTesting table format with active filter:")
    fetch_all_exclusions(active=True, formatter=create_formatter("table"))
    
    print("\nTesting JSON format for all exclusions:")
    fetch_all_exclusions(formatter=create_formatter("json"))
    
    # Get a valid exclusion ID from the first test
    exclusion_id = input("\nEnter an exclusion ID to test (or press Enter to skip): ")
    if exclusion_id:
        print(f"\nTesting table format for exclusion {exclusion_id}:")
        get_exclusion_details(exclusion_id, formatter=create_formatter("table"))
        
        print(f"\nTesting JSON format for exclusion {exclusion_id}:")
        get_exclusion_details(exclusion_id, formatter=create_formatter("json"))