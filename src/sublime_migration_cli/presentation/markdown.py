"""Markdown output formatter for Sublime CLI reports."""
import os
import datetime
from typing import Any, Dict, List, Optional, Union

from sublime_migration_cli.presentation.base import OutputFormatter, CommandResult


class MarkdownFormatter(OutputFormatter):
    """Formatter for markdown output, primarily for reports."""
    
    def __init__(self, output_file: Optional[str] = None):
        """Initialize markdown formatter.
        
        Args:
            output_file: Optional file path to write markdown output to
        """
        self.output_file = output_file
        self.buffer = []
    
    def output_result(self, result: Any) -> None:
        """Output a result in markdown format.
        
        Args:
            result: The data to output (CommandResult or other)
        """
        if isinstance(result, CommandResult):
            # Clear buffer
            self.buffer = []
            
            if result.success:
                # Add title
                self.buffer.append("# " + result.message + "\n")
                
                # Output data if present
                if result.data is not None:
                    self._output_data(result.data)
                
                # Add notes if present
                if result.notes:
                    self.buffer.append("\n> " + result.notes)
            else:
                self.output_error(result.message, result.error_details)
            
            # Write to file or stdout
            self._write_output()
        else:
            # Direct output of other data types
            self.buffer = []
            self._output_data(result)
            self._write_output()
    
    def output_error(self, error_message: str, details: Optional[Any] = None) -> None:
        """Output an error message in markdown format.
        
        Args:
            error_message: The main error message
            details: Additional error details (optional)
        """
        self.buffer = []
        self.buffer.append("# Error: " + error_message + "\n")
        
        if details:
            if isinstance(details, str):
                self.buffer.append(details)
            else:
                self.buffer.append("## Details\n")
                self._output_data(details)
        
        self._write_output()
    
    def output_success(self, message: str) -> None:
        """Output a success message in markdown format.
        
        Args:
            message: The success message
        """
        self.buffer = []
        self.buffer.append("# " + message + "\n")
        self._write_output()
    
    def create_progress(self, description: str, total: Optional[int] = None):
        """Create a 'progress indicator' for markdown output (no-op).
        
        Args:
            description: Description of the task (unused)
            total: Total number of steps (unused)
            
        Returns:
            A dummy progress context manager
        """
        class DummyProgress:
            def update(self, *args, **kwargs):
                pass
                
        class DummyContextManager:
            def __enter__(self):
                return DummyProgress(), 0
                
            def __exit__(self, *args):
                pass
                
        return DummyContextManager()
    
    def prompt_confirmation(self, message: str) -> bool:
        """Prompt the user for confirmation (no-op, always returns True).
        
        Args:
            message: The confirmation message (unused)
            
        Returns:
            bool: Always True in markdown mode
        """
        return True
    
    def _write_output(self) -> None:
        """Write the buffer contents to file or stdout."""
        content = "\n".join(self.buffer)
        
        if self.output_file:
            with open(self.output_file, "w") as f:
                f.write(content)
            print(f"Report written to: {self.output_file}")
        else:
            print(content)
    
    def _output_data(self, data: Any) -> None:
        """Output data based on its type.
        
        Args:
            data: The data to output
        """
        # Check for compare report data
        if isinstance(data, dict) and "summary" in data and "differences" in data:
            self._format_comparison_report(data)
        elif isinstance(data, dict):
            # Standard dictionary
            self._format_dictionary(data)
        elif isinstance(data, list):
            # List of items
            self._format_list(data)
        else:
            # Fallback for other types
            self.buffer.append("```\n" + str(data) + "\n```")
    
    def _safe_get(self, obj: Any, key: str, default: Any = None) -> Any:
        """Safely get an attribute from an object, handling non-dict objects.
        
        Args:
            obj: Object to get attribute from
            key: Key to get
            default: Default value if key doesn't exist
            
        Returns:
            Value for key or default
        """
        if not isinstance(obj, dict):
            return default
            
        return obj.get(key, default)
    
    def _format_comparison_report(self, data: Dict) -> None:
        """Format a comparison report in markdown.
        
        Args:
            data: Comparison report data
        """
        # Extract data with type safety
        summary = self._safe_get(data, "summary", {})
        differences = self._safe_get(data, "differences", {})
        source_info = self._safe_get(data, "source_info", {})
        dest_info = self._safe_get(data, "dest_info", {})
        
        # Add summary section
        self.buffer.append("## Summary\n")
        
        # Create summary table
        self.buffer.append("| Configuration Type | Source Count | Destination Count | Matching | Differences |")
        self.buffer.append("|-------------------|--------------|-------------------|----------|-------------|")
        
        total_source = 0
        total_dest = 0
        total_matching = 0
        total_diff = 0
        
        # Add rows for each configuration type
        if isinstance(summary, dict):
            for config_type, counts in summary.items():
                if config_type == "total" or not isinstance(counts, dict):
                    continue
                    
                source_count = self._safe_get(counts, "source_count", 0)
                dest_count = self._safe_get(counts, "dest_count", 0)
                matching = self._safe_get(counts, "matching", 0)
                diff_count = self._safe_get(counts, "differences", 0)
                
                total_source += source_count
                total_dest += dest_count
                total_matching += matching
                total_diff += diff_count
                
                # Format the row
                self.buffer.append(f"| {config_type.title()} | {source_count} | {dest_count} | {matching} | {diff_count} |")
        
        # Add totals row
        self.buffer.append(f"| **Total** | **{total_source}** | **{total_dest}** | **{total_matching}** | **{total_diff}** |")
        
        # Add differences details section if there are differences
        if isinstance(differences, dict) and len(differences) > 0:
            # Check if there are any differences to show
            has_differences = False
            for category, category_diffs in differences.items():
                if isinstance(category_diffs, dict):
                    missing_in_dest = self._safe_get(category_diffs, "missing_in_dest", [])
                    missing_in_source = self._safe_get(category_diffs, "missing_in_source", [])
                    content_differs = self._safe_get(category_diffs, "content_differs", [])
                    
                    if (isinstance(missing_in_dest, list) and len(missing_in_dest) > 0) or \
                       (isinstance(missing_in_source, list) and len(missing_in_source) > 0) or \
                       (isinstance(content_differs, list) and len(content_differs) > 0):
                        has_differences = True
                        break
            
            if has_differences:
                self.buffer.append("\n## Differences Details\n")
                
                for category, category_diffs in differences.items():
                    if not isinstance(category_diffs, dict):
                        continue
                        
                    missing_in_dest = self._safe_get(category_diffs, "missing_in_dest", [])
                    missing_in_source = self._safe_get(category_diffs, "missing_in_source", [])
                    content_differs = self._safe_get(category_diffs, "content_differs", [])
                    
                    if not all(isinstance(x, list) for x in [missing_in_dest, missing_in_source, content_differs]):
                        continue
                        
                    total_diffs = len(missing_in_dest) + len(missing_in_source) + len(content_differs)
                    
                    if total_diffs == 0:
                        continue
                        
                    # Add category header
                    self.buffer.append(f"### {category.title()} ({total_diffs} differences)")
                    
                    # Add missing in destination items
                    if missing_in_dest:
                        self.buffer.append(f"- **Missing in destination ({len(missing_in_dest)})**:")
                        for item in missing_in_dest:
                            self.buffer.append(f"  - \"{item}\"")
                    
                    # Add missing in source items
                    if missing_in_source:
                        self.buffer.append(f"- **Missing in source ({len(missing_in_source)})**:")
                        for item in missing_in_source:
                            self.buffer.append(f"  - \"{item}\"")
                    
                    # Add content differs items
                    if content_differs:
                        self.buffer.append(f"- **Definition drift ({len(content_differs)})**:")
                        for item in content_differs:
                            self.buffer.append(f"  - \"{item}\"")
                    
                    # Add empty line between categories
                    self.buffer.append("")
        
        # Add action items section if there are differences
        if total_diff > 0 and isinstance(differences, dict):
            self.buffer.append("\n## Action Items")
            
            # Calculate counts based on the differences object
            actions = self._safe_get(differences, "actions", {})
            actions_missing = len(self._safe_get(actions, "missing_in_dest", [])) if isinstance(actions, dict) else 0
            actions_content = len(self._safe_get(actions, "content_differs", [])) if isinstance(actions, dict) else 0
            
            rules = self._safe_get(differences, "rules", {})
            rules_missing = len(self._safe_get(rules, "missing_in_dest", [])) if isinstance(rules, dict) else 0
            rules_content_differs = len(self._safe_get(rules, "content_differs", [])) if isinstance(rules, dict) else 0
            
            lists = self._safe_get(differences, "lists", {})
            lists_missing = len(self._safe_get(lists, "missing_in_dest", [])) if isinstance(lists, dict) else 0
            lists_content = len(self._safe_get(lists, "content_differs", [])) if isinstance(lists, dict) else 0
            
            exclusions = self._safe_get(differences, "exclusions", {})
            exclusions_missing = len(self._safe_get(exclusions, "missing_in_dest", [])) if isinstance(exclusions, dict) else 0
            exclusions_content = len(self._safe_get(exclusions, "content_differs", [])) if isinstance(exclusions, dict) else 0
            
            feeds = self._safe_get(differences, "feeds", {})
            feeds_missing = len(self._safe_get(feeds, "missing_in_dest", [])) if isinstance(feeds, dict) else 0
            feeds_content = len(self._safe_get(feeds, "content_differs", [])) if isinstance(feeds, dict) else 0
            
            # Add items for missing in destination
            if actions_missing > 0:
                self.buffer.append(f"- ⚠️ Migrate {actions_missing} actions to destination")
            
            if rules_missing > 0:
                self.buffer.append(f"- ⚠️ Migrate {rules_missing} rules to destination")
            
            if lists_missing > 0:
                self.buffer.append(f"- ⚠️ Migrate {lists_missing} lists to destination")
            
            if exclusions_missing > 0:
                self.buffer.append(f"- ⚠️ Migrate {exclusions_missing} exclusions to destination")
            
            if feeds_missing > 0:
                self.buffer.append(f"- ⚠️ Migrate {feeds_missing} feeds to destination")
            
            # Add items for content differences
            if actions_content > 0:
                self.buffer.append(f"- ⚠️ Update {actions_content} actions with content differences")
            
            if rules_content_differs > 0:
                self.buffer.append(f"- ⚠️ Update {rules_content_differs} rules with content differences")
                
            if lists_content > 0:
                self.buffer.append(f"- ⚠️ Update {lists_content} lists with content differences")
                
            if exclusions_content > 0:
                self.buffer.append(f"- ⚠️ Update {exclusions_content} exclusions with content differences")
                
            if feeds_content > 0:
                self.buffer.append(f"- ⚠️ Update {feeds_content} feeds with content differences")
            
            # Add items for missing in source
            lists_source_missing = len(self._safe_get(lists, "missing_in_source", [])) if isinstance(lists, dict) else 0
            if lists_source_missing > 0:
                self.buffer.append(f"- ⚠️ {lists_source_missing} lists exist in destination but not in source")
                
            rules_source_missing = len(self._safe_get(rules, "missing_in_source", [])) if isinstance(rules, dict) else 0
            if rules_source_missing > 0:
                self.buffer.append(f"- ⚠️ {rules_source_missing} rules exist in destination but not in source")
                
            feeds_source_missing = len(self._safe_get(feeds, "missing_in_source", [])) if isinstance(feeds, dict) else 0
            if feeds_source_missing > 0:
                self.buffer.append(f"- ⚠️ {feeds_source_missing} feeds exist in destination but not in source")
            
            # Add exclusions content differences
            exclusions_source_missing = len(self._safe_get(exclusions, "missing_in_source", [])) if isinstance(exclusions, dict) else 0
            if exclusions_source_missing > 0:
                self.buffer.append(f"- ⚠️ {exclusions_source_missing} exclusions exist in destination but not in source")
            
            # Recommend using migrate commands for categories with differences
            self.buffer.append("\n### Recommended Commands")
            
            differences_found = False
            if isinstance(summary, dict):
                for category, summary_data in summary.items():
                    if category != "total" and isinstance(summary_data, dict) and summary_data.get("differences", 0) > 0:
                        differences_found = True
                        category_cmd = category
                        # Special case for plurals
                        if category in ["exclusions", "lists", "feeds", "rules"]:
                            category_cmd = category
                        elif category[-1] != 's':
                            category_cmd = f"{category}s"
                        
                        self.buffer.append(f"- 💡 Run `sublime migrate {category_cmd}` to resolve {category} differences")
            
            if not differences_found:
                self.buffer.append("- No migration commands needed")
        
        # Add report information
        self.buffer.append("\n## Report Information")
        
        # Source and destination information
        if isinstance(source_info, dict):
            source_org = self._safe_get(source_info, "org_name", "Unknown")
            source_region = self._safe_get(source_info, "region", "Unknown")
            self.buffer.append(f"- **Source Instance**: {source_org} ({source_region})")
        
        if isinstance(dest_info, dict):
            dest_org = self._safe_get(dest_info, "org_name", "Unknown")
            dest_region = self._safe_get(dest_info, "region", "Unknown")
            self.buffer.append(f"- **Destination Instance**: {dest_org} ({dest_region})")
        
        # Add timestamp
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%d at %H:%M UTC")
        self.buffer.append(f"- **Report Generated**: {timestamp}")
        
        # Add CLI version
        from sublime_migration_cli import __version__
        self.buffer.append(f"- **Generated By**: sublime-migration-cli v{__version__}")
            
    def _format_dictionary(self, data: Dict) -> None:
        """Format a dictionary as markdown.
        
        Args:
            data: Dictionary to format
        """
        if not isinstance(data, dict):
            self.buffer.append(str(data))
            return
            
        for key, value in data.items():
            formatted_key = key.replace("_", " ").title()
            
            if isinstance(value, dict):
                self.buffer.append(f"### {formatted_key}\n")
                self._format_dictionary(value)
            elif isinstance(value, list):
                self.buffer.append(f"### {formatted_key}\n")
                self._format_list(value)
            else:
                self.buffer.append(f"**{formatted_key}**: {value}\n")
    
    def _format_list(self, data: List) -> None:
        """Format a list as markdown bullets.
        
        Args:
            data: List to format
        """
        if not isinstance(data, list):
            self.buffer.append(str(data))
            return
            
        for item in data:
            if isinstance(item, dict):
                # For dictionaries in a list, try to use a name field if available
                name = self._safe_get(item, "name", self._safe_get(item, "id", None))
                if name:
                    self.buffer.append(f"- **{name}**")
                    # Indent and format the rest of the dictionary
                    for k, v in item.items():
                        if k not in ["name", "id"]:
                            formatted_key = k.replace("_", " ").title()
                            self.buffer.append(f"  - {formatted_key}: {v}")
                else:
                    # No name field, just format as a bullet dictionary
                    self.buffer.append("- " + str(item))
            else:
                # Simple items
                self.buffer.append(f"- {item}")