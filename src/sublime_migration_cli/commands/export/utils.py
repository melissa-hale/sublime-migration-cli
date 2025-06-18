"""Utilities for export functionality."""
import os
import re
import yaml
import json
from typing import Any, Dict, List, Optional, Set, Tuple
from pathlib import Path
import datetime

from sublime_migration_cli.utils.errors import ValidationError


def sanitize_filename(name: str, max_length: int = 25) -> str:
    """Sanitize a name for use as a filename.
    
    Args:
        name: Original name
        max_length: Maximum length for the base name
        
    Returns:
        str: Sanitized filename (without extension)
    """
    # Remove special characters and replace spaces with hyphens
    sanitized = re.sub(r'[^\w\s-]', '', name)
    sanitized = re.sub(r'[-\s]+', '-', sanitized)
    sanitized = sanitized.strip('-').lower()
    
    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rstrip('-')
    
    return sanitized


def resolve_filename_collision(base_name: str, existing_files: Set[str], 
                              obj_id: str, extension: str = ".yml") -> str:
    """Resolve filename collisions by adding UUID suffix.
    
    Args:
        base_name: Base filename (without extension)
        existing_files: Set of existing filenames
        obj_id: Object ID to use for suffix
        extension: File extension
        
    Returns:
        str: Unique filename
    """
    filename = f"{base_name}{extension}"
    
    if filename not in existing_files:
        return filename
    
    # Use last 6 characters of UUID for suffix
    uuid_suffix = obj_id.replace("-", "")[-6:]
    filename = f"{base_name}-{uuid_suffix}{extension}"
    
    return filename


def create_directory_structure(output_dir: str) -> Dict[str, str]:
    """Create the export directory structure.
    
    Args:
        output_dir: Base output directory
        
    Returns:
        Dict[str, str]: Mapping of resource type to directory path
    """
    base_path = Path(output_dir)
    
    directories = {
        "actions": base_path / "actions",
        "rules_detection": base_path / "rules" / "detection",
        "rules_triage": base_path / "rules" / "triage", 
        "lists_string": base_path / "lists" / "string",
        "lists_user_group": base_path / "lists" / "user_group",
        "exclusions_global": base_path / "exclusions" / "global",
        "exclusions_detection": base_path / "exclusions" / "detection",
        "feeds": base_path / "feeds"
    }
    
    # Create all directories
    for dir_path in directories.values():
        dir_path.mkdir(parents=True, exist_ok=True)
    
    return {key: str(path) for key, path in directories.items()}


def write_resource_file(resource_data: Dict, file_path: str, 
                       output_format: str = "yaml") -> None:
    """Write a resource to a file.
    
    Args:
        resource_data: Resource data to write
        file_path: Path to write the file to
        output_format: Output format (yaml or json)
    """
    if output_format == "yaml":
        with open(file_path, 'w') as f:
            # Custom YAML dumper for consistent indentation
            class CustomDumper(yaml.SafeDumper):
                def increase_indent(self, flow=False, indentless=False):
                    return super().increase_indent(flow, False)
            
            def represent_str(dumper, data):
                # Use literal style for multiline strings (like rule source)
                if '\n' in data:
                    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
                return dumper.represent_scalar('tag:yaml.org,2002:str', data)
            
            CustomDumper.add_representer(str, represent_str)
            
            yaml.dump(resource_data, f, 
                     Dumper=CustomDumper,
                     default_flow_style=False, 
                     sort_keys=False, 
                     allow_unicode=True,
                     indent=2,
                     width=120)
    elif output_format == "json":
        with open(file_path, 'w') as f:
            json.dump(resource_data, f, indent=2, ensure_ascii=False)
    else:
        raise ValidationError(f"Unsupported output format: {output_format}")


def parse_rule_exclusion(exclusion_source: str) -> Optional[Tuple[str, str]]:
    """Parse a rule exclusion source to extract type and value.
    
    Args:
        exclusion_source: Exclusion source string
        
    Returns:
        Optional[Tuple[str, str]]: (exclusion_type, exclusion_value) or None
    """
    # Patterns from the existing rule_exclusions.py
    patterns = {
        "recipient_email": re.compile(r"any\(recipients\.to, \.email\.email == '([^']+)'\)"),
        "sender_email": re.compile(r"sender\.email\.email == '([^']+)'"),
        "sender_domain": re.compile(r"sender\.email\.domain\.domain == '([^']+)'")
    }
    
    for exclusion_type, pattern in patterns.items():
        match = pattern.search(exclusion_source)
        if match:
            return (exclusion_type, match.group(1))
    
    return None


def generate_export_summary(export_results: Dict, output_dir: str, 
                           source_info: Dict) -> str:
    """Generate an export summary README file.
    
    Args:
        export_results: Results from the export operation
        output_dir: Output directory
        source_info: Information about the source instance
        
    Returns:
        str: Path to the generated README file
    """
    readme_path = os.path.join(output_dir, "README.md")
    
    # Calculate totals
    total_exported = sum(result.get("exported", 0) for result in export_results.values() 
                        if isinstance(result, dict))
    total_failed = sum(result.get("failed", 0) for result in export_results.values() 
                      if isinstance(result, dict))
    
    readme_content = "# Sublime Security Configuration Export\n\n"
    readme_content += "## Export Summary\n\n"
    readme_content += f"**Source Instance:** {source_info.get('org_name', 'Unknown')} ({source_info.get('region', 'Unknown')})\n"
    readme_content += f"**Export Date:** {export_results.get('timestamp', 'Unknown')}\n"
    readme_content += f"**Total Objects Exported:** {total_exported}\n"
    readme_content += f"**Total Failures:** {total_failed}\n\n"
    readme_content += "## Export Results by Type\n\n"
    
    for resource_type, result in export_results.items():
        if resource_type == 'timestamp' or not isinstance(result, dict):
            continue
            
        exported = result.get("exported", 0)
        failed = result.get("failed", 0)
        
        readme_content += f"- **{resource_type.title()}:** {exported} exported"
        if failed > 0:
            readme_content += f", {failed} failed"
        readme_content += "\n"
    
    readme_content += "\n## Directory Structure\n\n"
    readme_content += "```\n"
    readme_content += "./\n"
    readme_content += "├── actions/           # Action configurations\n"
    readme_content += "├── rules/\n"
    readme_content += "│   ├── detection/     # Detection rules\n"
    readme_content += "│   └── triage/        # Triage rules\n"
    readme_content += "├── lists/\n"
    readme_content += "│   ├── string/        # String lists\n"
    readme_content += "│   └── user_group/    # User group lists\n"
    readme_content += "├── exclusions/\n"
    readme_content += "│   ├── global/        # Global exclusions\n"
    readme_content += "│   └── detection/     # Detection exclusions\n"
    readme_content += "└── feeds/             # Feed configurations\n"
    readme_content += "```\n\n"
    readme_content += "## Usage\n\n"
    readme_content += "These exported configurations can be used for:\n"
    readme_content += "- Version control and change tracking\n"
    readme_content += "- Backup and disaster recovery\n"
    readme_content += "- Configuration migration between instances\n"
    readme_content += "- Audit and compliance reporting\n\n"
    readme_content += "Generated by sublime-migration-cli\n"
    
    with open(readme_path, 'w') as f:
        f.write(readme_content)
    
    return readme_path