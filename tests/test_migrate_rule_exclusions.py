#!/usr/bin/env python
"""Test script for the migrate rule-exclusions presentation layer."""
import os
from src.sublime_migration_cli.presentation.factory import create_formatter
from src.sublime_migration_cli.commands.migrate.refactored.rule_exclusions import migrate_rule_exclusions_between_instances

if __name__ == "__main__":
    # Make sure environment variables are set
    if not os.environ.get("SUBLIME_API_KEY") or not os.environ.get("SUBLIME_REGION"):
        print("Please set SUBLIME_API_KEY and SUBLIME_REGION environment variables for source instance")
        exit(1)
        
    if not os.environ.get("SUBLIME_DEST_API_KEY") or not os.environ.get("SUBLIME_DEST_REGION"):
        print("Please set SUBLIME_DEST_API_KEY and SUBLIME_DEST_REGION environment variables for destination instance")
        exit(1)
    
    source_api_key = os.environ.get("SUBLIME_API_KEY")
    source_region = os.environ.get("SUBLIME_REGION")
    dest_api_key = os.environ.get("SUBLIME_DEST_API_KEY")
    dest_region = os.environ.get("SUBLIME_DEST_REGION")
    
    # Test with dry run in table format
    print("\nTesting table format with dry run:")
    formatter = create_formatter("table")
    result = migrate_rule_exclusions_between_instances(
        source_api_key, source_region,
        dest_api_key, dest_region,
        dry_run=True,
        formatter=formatter
    )
    formatter.output_result(result)
    
    # Test with JSON format
    print("\nTesting JSON format with dry run:")
    formatter = create_formatter("json")
    result = migrate_rule_exclusions_between_instances(
        source_api_key, source_region,
        dest_api_key, dest_region,
        dry_run=True,
        formatter=formatter
    )
    formatter.output_result(result)
    
    # Prompt for actual migration (with confirmation)
    if input("\nWould you like to test a real migration? (y/N): ").lower() == 'y':
        include_rule_ids = input("Enter rule IDs to include (comma-separated, or leave empty for all): ")
        
        print("\nTesting actual migration with table format:")
        formatter = create_formatter("table")
        result = migrate_rule_exclusions_between_instances(
            source_api_key, source_region,
            dest_api_key, dest_region,
            include_rule_ids=include_rule_ids if include_rule_ids else None,
            formatter=formatter
        )
        formatter.output_result(result)