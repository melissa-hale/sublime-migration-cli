#!/usr/bin/env python
"""Test script for presentation layer."""
import os
from src.sublime_migration_cli.presentation.factory import create_formatter
from src.sublime_migration_cli.commands.get.refactored.actions import list_actions, get_action_details

if __name__ == "__main__":
    # Make sure environment variables are set
    if not os.environ.get("SUBLIME_API_KEY"):
        print("Please set SUBLIME_API_KEY environment variable")
        exit(1)
        
    if not os.environ.get("SUBLIME_REGION"):
        print("Please set SUBLIME_REGION environment variable")
        exit(1)
    
    # Test the all actions command
    print("\nTesting table format for all actions:")
    list_actions(formatter=create_formatter("table"))
    
    print("\nTesting JSON format for all actions:")
    list_actions(formatter=create_formatter("json"))
    
    # Get a valid action ID from the first test
    # If this isn't feasible, you can hardcode a known action ID
    action_id = input("\nEnter an action ID to test (or press Enter to skip): ")
    if action_id:
        print(f"\nTesting table format for action {action_id}:")
        get_action_details(action_id, formatter=create_formatter("table"))
        
        print(f"\nTesting JSON format for action {action_id}:")
        get_action_details(action_id, formatter=create_formatter("json"))