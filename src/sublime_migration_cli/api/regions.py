"""Configuration for Sublime Security regions."""
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class Region:
    """Represents a Sublime Security deployment region."""

    code: str
    api_url: str
    description: str


# Define available regions with correct values
REGIONS: Dict[str, Region] = {
    "NA_WEST": Region(
        code="NA_WEST",
        api_url="https://na-west.platform.sublime.security",
        description="North America West (Oregon)",
    ),
    "NA_EAST": Region(
        code="NA_EAST",
        api_url="https://platform.sublime.security",
        description="North America East (Virginia)",
    ),
    "CANADA": Region(
        code="CANADA",
        api_url="https://ca.platform.sublime.security",
        description="Canada (Montréal)",
    ),
    "EU_DUBLIN": Region(
        code="EU_DUBLIN",
        api_url="https://eu.platform.sublime.security",
        description="Europe (Dublin)",
    ),
    "EU_UK": Region(
        code="EU_UK",
        api_url="https://uk.platform.sublime.security",
        description="Europe (UK)",
    ),
    "AUSTRALIA": Region(
        code="AUSTRALIA",
        api_url="https://au.platform.sublime.security",
        description="Australia (Sydney)",
    ),
}


def get_region(region_code: str) -> Region:
    """Get a region by code.

    Args:
        region_code: The code of the region

    Returns:
        Region: The region object

    Raises:
        ValueError: If the region is not found
    """
    if region_code not in REGIONS:
        available_regions = ", ".join(REGIONS.keys())
        raise ValueError(
            f"Region '{region_code}' not found. Available regions: {available_regions}"
        )
    return REGIONS[region_code]


def get_all_regions() -> List[Region]:
    """Get all available regions.

    Returns:
        List[Region]: List of all available regions
    """
    return list(REGIONS.values())


def get_regions_for_display() -> List[Tuple[str, str]]:
    """Get regions formatted for CLI display.

    Returns:
        List[Tuple[str, str]]: List of region codes and descriptions
    """
    return [(code, region.description) for code, region in REGIONS.items()]
