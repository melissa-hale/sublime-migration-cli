"""Simple tests for CLI commands."""
import pytest
from unittest.mock import patch
from click.testing import CliRunner

from sublime_migration_cli.cli import cli
from sublime_migration_cli.commands.get.actions import actions


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


def test_cli_help(runner):
    """Test the CLI provides help output."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Sublime Security CLI" in result.output


@patch("sublime_cli.commands.actions.get_api_client_from_env_or_args")
def test_list_actions(mock_get_client, runner):
    """Test listing actions command."""
    # Setup mock client response
    mock_client = mock_get_client.return_value
    mock_client.get.return_value = [
        {
            "id": "test-id-1",
            "name": "Test Action 1",
            "type": "quarantine_message",
            "active": True
        },
        {
            "id": "test-id-2",
            "name": "Test Action 2",
            "type": "trash_message",
            "active": False
        }
    ]
    
    # Run the command
    result = runner.invoke(cli, ["get", "actions", "--json"])
    
    # Check results
    assert result.exit_code == 0
    assert "test-id-1" in result.output
    assert "Test Action 1" in result.output
    
    # Verify the API call was made
    mock_client.get.assert_called_once_with("/v1/actions")
