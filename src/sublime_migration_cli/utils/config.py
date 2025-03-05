"""Configuration utilities for managing user configuration."""
import os
import json
from pathlib import Path
from typing import Any, Dict, Optional

from sublime_migration_cli.utils.errors import ConfigurationError

# Default configuration directory
DEFAULT_CONFIG_DIR = os.path.expanduser("~/.sublime-cli")
DEFAULT_CONFIG_FILE = "config.json"


def get_config_dir() -> str:
    """Get the configuration directory path.
    
    Uses environment variable SUBLIME_CONFIG_DIR if set,
    otherwise uses the default ~/.sublime-cli directory.
    
    Returns:
        str: Path to the configuration directory
    """
    config_dir = os.environ.get("SUBLIME_CONFIG_DIR", DEFAULT_CONFIG_DIR)
    
    # Create directory if it doesn't exist
    if not os.path.exists(config_dir):
        try:
            os.makedirs(config_dir, mode=0o700)  # Secure permissions
        except OSError as e:
            raise ConfigurationError(f"Failed to create configuration directory: {str(e)}")
    
    return config_dir


def get_config_file_path(filename: Optional[str] = None) -> str:
    """Get the path to a configuration file.
    
    Args:
        filename: Optional filename (defaults to config.json)
        
    Returns:
        str: Path to the configuration file
    """
    config_dir = get_config_dir()
    filename = filename or DEFAULT_CONFIG_FILE
    return os.path.join(config_dir, filename)


def load_config(filename: Optional[str] = None) -> Dict:
    """Load configuration from file.
    
    Args:
        filename: Optional filename (defaults to config.json)
        
    Returns:
        Dict: Configuration data
        
    Raises:
        ConfigurationError: If the configuration file cannot be read or parsed
    """
    config_path = get_config_file_path(filename)
    
    # Return empty config if file doesn't exist
    if not os.path.exists(config_path):
        return {}
    
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid configuration file format: {str(e)}")
    except OSError as e:
        raise ConfigurationError(f"Failed to read configuration file: {str(e)}")


def save_config(config: Dict, filename: Optional[str] = None) -> None:
    """Save configuration to file.
    
    Args:
        config: Configuration data to save
        filename: Optional filename (defaults to config.json)
        
    Raises:
        ConfigurationError: If the configuration file cannot be written
    """
    config_path = get_config_file_path(filename)
    
    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        
        # Set secure permissions
        os.chmod(config_path, 0o600)
    except OSError as e:
        raise ConfigurationError(f"Failed to write configuration file: {str(e)}")


def get_config_value(key: str, default: Any = None, filename: Optional[str] = None) -> Any:
    """Get a configuration value by key.
    
    Args:
        key: Configuration key
        default: Default value if key is not found
        filename: Optional filename (defaults to config.json)
        
    Returns:
        Any: Configuration value or default
    """
    config = load_config(filename)
    return config.get(key, default)


def set_config_value(key: str, value: Any, filename: Optional[str] = None) -> None:
    """Set a configuration value by key.
    
    Args:
        key: Configuration key
        value: Value to set
        filename: Optional filename (defaults to config.json)
    """
    config = load_config(filename)
    config[key] = value
    save_config(config, filename)


def remove_config_value(key: str, filename: Optional[str] = None) -> None:
    """Remove a configuration value by key.
    
    Args:
        key: Configuration key to remove
        filename: Optional filename (defaults to config.json)
    """
    config = load_config(filename)
    if key in config:
        del config[key]
        save_config(config, filename)


def get_api_config(destination: bool = False) -> Dict[str, str]:
    """Get API configuration (key and region).
    
    Args:
        destination: Whether to get destination API config
        
    Returns:
        Dict[str, str]: API configuration with "api_key" and "region" keys
    """
    config = load_config()
    
    if destination:
        return {
            "api_key": config.get("dest_api_key"),
            "region": config.get("dest_region")
        }
    else:
        return {
            "api_key": config.get("api_key"),
            "region": config.get("region")
        }


def set_api_config(api_key: str, region: str, destination: bool = False) -> None:
    """Set API configuration (key and region).
    
    Args:
        api_key: API key
        region: Region code
        destination: Whether to set destination API config
    """
    config = load_config()
    
    if destination:
        config["dest_api_key"] = api_key
        config["dest_region"] = region
    else:
        config["api_key"] = api_key
        config["region"] = region
    
    save_config(config)


def clear_api_config(destination: bool = False) -> None:
    """Clear API configuration (key and region).
    
    Args:
        destination: Whether to clear destination API config
    """
    config = load_config()
    
    if destination:
        if "dest_api_key" in config:
            del config["dest_api_key"]
        if "dest_region" in config:
            del config["dest_region"]
    else:
        if "api_key" in config:
            del config["api_key"]
        if "region" in config:
            del config["region"]
    
    save_config(config)


class Config:
    """Class for managing configuration values."""
    
    def __init__(self, filename: Optional[str] = None):
        """Initialize Config object.
        
        Args:
            filename: Optional configuration filename
        """
        self.filename = filename
        self._config = load_config(filename)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key is not found
            
        Returns:
            Any: Configuration value or default
        """
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value.
        
        Args:
            key: Configuration key
            value: Value to set
        """
        self._config[key] = value
        save_config(self._config, self.filename)
    
    def remove(self, key: str) -> None:
        """Remove a configuration value.
        
        Args:
            key: Configuration key to remove
        """
        if key in self._config:
            del self._config[key]
            save_config(self._config, self.filename)
    
    def get_all(self) -> Dict:
        """Get all configuration values.
        
        Returns:
            Dict: All configuration values
        """
        return self._config.copy()
    
    def update(self, values: Dict) -> None:
        """Update multiple configuration values.
        
        Args:
            values: Dictionary of values to update
        """
        self._config.update(values)
        save_config(self._config, self.filename)
    
    def clear(self) -> None:
        """Clear all configuration values."""
        self._config = {}
        save_config(self._config, self.filename)
    
    def exists(self, key: str) -> bool:
        """Check if a configuration key exists.
        
        Args:
            key: Configuration key to check
            
        Returns:
            bool: True if the key exists
        """
        return key in self._config
    
    def reload(self) -> None:
        """Reload configuration from file."""
        self._config = load_config(self.filename)


# Helper functions for specific configuration scenarios

def get_credentials_config() -> Dict:
    """Get stored API credentials.
    
    Returns:
        Dict: Dictionary containing credentials for all configured instances
    """
    config = load_config()
    credentials = {}
    
    # Extract credential information
    if "api_key" in config and "region" in config:
        credentials["source"] = {
            "api_key": config["api_key"],
            "region": config["region"]
        }
    
    if "dest_api_key" in config and "dest_region" in config:
        credentials["destination"] = {
            "api_key": config["dest_api_key"],
            "region": config["dest_region"]
        }
    
    # Add any named instance credentials
    instances = config.get("instances", {})
    if instances:
        credentials["instances"] = instances
    
    return credentials


def get_output_preferences() -> Dict:
    """Get output preferences.
    
    Returns:
        Dict: Output preferences including format, verbosity, etc.
    """
    config = load_config()
    preferences = {
        "format": config.get("output_format", "table"),
        "verbose": config.get("verbose", False),
        "color": config.get("color", True),
        "pager": config.get("use_pager", True)
    }
    
    return preferences


def set_output_preferences(
    format: Optional[str] = None,
    verbose: Optional[bool] = None,
    color: Optional[bool] = None,
    pager: Optional[bool] = None
) -> None:
    """Set output preferences.
    
    Args:
        format: Output format (table, json, etc.)
        verbose: Verbose output
        color: Use color
        pager: Use pager for large outputs
    """
    config = load_config()
    
    if format is not None:
        config["output_format"] = format
    
    if verbose is not None:
        config["verbose"] = verbose
    
    if color is not None:
        config["color"] = color
    
    if pager is not None:
        config["use_pager"] = pager
    
    save_config(config)


def store_instance_credentials(
    name: str,
    api_key: str,
    region: str
) -> None:
    """Store credentials for a named instance.
    
    Args:
        name: Instance name
        api_key: API key
        region: Region code
    """
    config = load_config()
    
    # Initialize instances dictionary if it doesn't exist
    if "instances" not in config:
        config["instances"] = {}
    
    # Store instance credentials
    config["instances"][name] = {
        "api_key": api_key,
        "region": region
    }
    
    save_config(config)


def remove_instance_credentials(name: str) -> bool:
    """Remove credentials for a named instance.
    
    Args:
        name: Instance name
        
    Returns:
        bool: True if instance was removed, False if not found
    """
    config = load_config()
    
    if "instances" in config and name in config["instances"]:
        del config["instances"][name]
        save_config(config)
        return True
    
    return False