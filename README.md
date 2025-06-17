# Sublime Migration CLI

A command-line utility for migrating, exporting, and managing configuration between Sublime Security Platform instances.

## Overview

The Sublime Migration CLI enables you to manage and migrate configuration objects between different Sublime Security Platform instances, as well as export configurations for version control and backup purposes.

## Features

- **Command Categories**:
  - `get`: Retrieve configuration objects from your instance
  - `migrate`: Copy configuration between instances
  - `export`: Export configuration to local files for version control
  - `report`: Generate comparison reports between instances
  
- **Supported Object Types**:
  - Actions
  - Lists (string and user_group)
  - Exclusions (global and detection)
  - Feeds
  - Rules (detection and triage)
  - Rule-Action Associations
  - Rule Exclusions
  - Organization Settings

- **Cross-Region Support**: Migrate between any of Sublime's global regions

- **Multiple Output Formats**: Human-readable tables, machine-parsable JSON, or structured YAML/Markdown reports

- **Comprehensive Filtering**: Select specific objects to migrate or export

- **Dry Run Mode**: Preview migrations before applying changes

- **Version Control Ready**: Export configurations as YAML files for Git tracking

## Installation

### Requirements

- Python 3.8 or higher
- Required packages: click, requests, rich, tabulate, PyYAML

### Install from Source

```bash
git clone https://github.com/yourusername/sublime-migration-cli.git
cd sublime-migration-cli
pip install -e .
```

## Authentication

The CLI supports authentication via:

1. Command-line parameters
2. Environment variables
3. Configuration file

### Using Environment Variables

```bash
# For source instance
export SUBLIME_API_KEY="your-api-key"
export SUBLIME_REGION="NA_EAST"

# For destination instance (when migrating)
export SUBLIME_DEST_API_KEY="dest-api-key" 
export SUBLIME_DEST_REGION="EU_DUBLIN"
```

### Available Regions

- `NA_EAST`: North America East (Virginia)
- `NA_WEST`: North America West (Oregon)
- `CANADA`: Canada (Montréal)
- `EU_DUBLIN`: Europe (Dublin)
- `EU_UK`: Europe (UK)
- `AUSTRALIA`: Australia (Sydney)

## Usage Examples

### Getting Configuration Data

```bash
# List all actions
sublime get actions all

# Get details for a specific action
sublime get actions action action-id-123

# List all rules with their exclusions
sublime get rules all --show-exclusions

# List specific types of lists
sublime get lists all --type string
```

### Exporting Configuration

```bash
# Export all configuration to YAML files
sublime export all

# Export to specific directory
sublime export all --output-dir ./my-config

# Export only rules and actions
sublime export all --include-types rules,actions

# Export in JSON format
sublime export all --format json

# Export with sensitive organization data
sublime export all --include-sensitive

# Export individual object types
sublime export actions
sublime export rules --type detection
sublime export lists --type string
sublime export exclusions --scope global
sublime export feeds
sublime export organization --include-sensitive
```

### Migrating Configuration

```bash
# Migrate all actions between instances
sublime migrate actions --source-api-key KEY1 --source-region NA_EAST \
                        --dest-api-key KEY2 --dest-region EU_DUBLIN

# Migrate only webhook actions
sublime migrate actions --include-types webhook

# Preview a migration without making changes
sublime migrate lists --dry-run

# Migrate specific rules by ID
sublime migrate rules --include-rule-ids id1,id2,id3

# Migrate everything
sublime migrate all

# Migrate everything except feeds
sublime migrate all --skip feeds

# Skip confirmation prompts
sublime migrate actions --yes
```

### Generating Reports

```bash
# Compare configuration between instances
sublime report compare --source-api-key KEY1 --dest-api-key KEY2

# Compare only specific object types
sublime report compare --include-types actions,rules --source-api-key KEY1 --dest-api-key KEY2

# Generate markdown report to file
sublime report compare --output-file report.md --source-api-key KEY1 --dest-api-key KEY2
```

### Output Formats

```bash
# Default tabular output
sublime get rules all

# JSON output
sublime get rules all --format json

# JSON output to a file
sublime get rules all --format json > rules.json

# YAML export for version control
sublime export all --format yaml
```

## Export Directory Structure

When using `sublime export all`, files are organized as follows:

```
sublime-export/
├── README.md                    # Export summary
├── organization.yml             # Organization settings
├── actions/
│   ├── webhook-alert.yml
│   └── warning-banner.yml
├── rules/
│   ├── detection/
│   │   ├── phishing-detection.yml
│   │   └── malware-scan.yml
│   └── triage/
│       └── auto-classification.yml
├── lists/
│   ├── string/
│   │   ├── trusted-domains.yml
│   │   └── blocked-extensions.yml
│   └── user_group/
│       └── executives.yml
├── exclusions/
│   ├── global/
│   │   └── newsletter-exclusion.yml
│   └── detection/
│       └── false-positive-fix.yml
└── feeds/
    └── custom-rules-feed.yml
```

## Configuration File Format

Exported YAML files follow a consistent schema. Example rule:

```yaml
name: "Phishing Detection Rule"
type: "rule"
severity: "high"
description: "Detects suspicious phishing attempts"
source: |
  type.inbound
  and sender.email.domain.domain not in $trusted_domains
  and any(body.links, .href_url.domain.domain in $suspicious_domains)
tags:
  - "phishing"
  - "security"
actions:
  - "Quarantine Message - 3bc152f2-6722-57be-b924-055c35fa1e60"
  - "Send Alert - a905543a-60ed-44b4-adbc-81d99e9e797b"
exclusions:
  recipient_email:
    - "trusted@company.com"
  sender_domain:
    - "legitimate-partner.com"
```

## Common Workflows

### Backup and Version Control

```bash
# Export everything for backup
sublime export all --output-dir ./backup-$(date +%Y%m%d)

# Daily backup with Git
sublime export all --output-dir ./config
cd config
git add .
git commit -m "Daily config backup $(date)"
git push
```

### Environment Migration

```bash
# 1. Export from development
sublime export all --output-dir ./dev-config --api-key DEV_KEY

# 2. Review changes
git diff

# 3. Migrate to production
sublime migrate all --source-api-key DEV_KEY --dest-api-key PROD_KEY --dry-run
sublime migrate all --source-api-key DEV_KEY --dest-api-key PROD_KEY --yes
```

### Configuration Audit

```bash
# Generate comparison report
sublime report compare --source-api-key PROD_KEY --dest-api-key DEV_KEY --output-file audit.md

# Export current state for compliance
sublime export all --include-sensitive --output-dir ./compliance-export
```

## Project Structure

```
sublime-migration-cli/
├── src/
│   └── sublime_migration_cli/
│       ├── api/               # API communication layer
│       ├── commands/          # CLI command implementations
│       │   ├── get/           # Commands for retrieving data
│       │   ├── migrate/       # Commands for migrations
│       │   ├── export/        # Commands for exporting
│       │   └── report/        # Commands for reporting
│       ├── models/            # Data models for objects
│       ├── presentation/      # Output formatting
│       └── utils/             # Utility functions
└── pyproject.toml             # Project configuration
```

### Getting Help

```bash
# General help
sublime --help

# Command-specific help
sublime export --help
sublime migrate actions --help

# View available regions and options
sublime get actions --help
```

## Support

For issues or questions, please contact melissa@sublimesecurity.com