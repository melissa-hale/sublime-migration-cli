#!/usr/bin/env python
"""Test script for rules presentation layer."""
import os
from src.sublime_migration_cli.presentation.factory import create_formatter
from src.sublime_migration_cli.commands.get.refactored.rules import fetch_all_rules, get_rule_details

if __name__ == "__main__":
    # Make sure environment variables are set
    if not os.environ.get("SUBLIME_API_KEY"):
        print("Please set SUBLIME_API_KEY environment variable")
        exit(1)
        
    if not os.environ.get("SUBLIME_REGION"):
        print("Please set SUBLIME_REGION environment variable")
        exit(1)
    
    # Test the all rules command
    print("\nTesting table format for all rules:")
    fetch_all_rules(formatter=create_formatter("table"))
    
    print("\nTesting table format with active filter:")
    fetch_all_rules(active=True, formatter=create_formatter("table"))
    
    print("\nTesting table format with rule type filter:")
    fetch_all_rules(rule_type="detection", formatter=create_formatter("table"))
    
    print("\nTesting table format with exclusions:")
    fetch_all_rules(show_exclusions=True, formatter=create_formatter("table"))
    
    print("\nTesting JSON format for all rules:")
    fetch_all_rules(formatter=create_formatter("json"))
    
    # Get a valid rule ID from the first test
    rule_id = input("\nEnter a rule ID to test (or press Enter to skip): ")
    if rule_id:
        print(f"\nTesting table format for rule {rule_id}:")
        get_rule_details(rule_id, formatter=create_formatter("table"))
        
        print(f"\nTesting JSON format for rule {rule_id}:")
        get_rule_details(rule_id, formatter=create_formatter("json"))