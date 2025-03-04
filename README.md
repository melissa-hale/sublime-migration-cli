# Sublime CLI

A simplified command-line utility for interacting with the Sublime Security Platform.

## Installation

```bash
pip install sublime-cli
```

## Usage

```bash
# Using command-line arguments
sublime --api-key YOUR_API_KEY --region NA_EAST <command>

# Using environment variables
export SUBLIME_API_KEY=your_api_key
export SUBLIME_REGION=NA_EAST

export SUBLIME_DEST_API_KEY=your_api_key
export SUBLIME_DEST_REGION=NA_EAST
sublime <command>
```

## Available Commands

### Authentication

Verify API key:
```bash
sublime auth verify
```

List available regions:
```bash
sublime auth regions
```

### Actions

List all actions:
```bash
sublime get actions
```

Get action details:
```bash
sublime get actions action <action-id>
```

## Development

Set up a development environment:

```bash
# Clone the repository
git clone https://github.com/your-org/sublime-migration-cli.git
cd sublime-migration-cli

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest
```
