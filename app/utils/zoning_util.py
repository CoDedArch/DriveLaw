# Utility functions for compliance checks
from typing import List
from app.core.constants import ZONE_USES, ZoneType


def get_permitted_uses(zone: ZoneType) -> List[str]:
    """Returns allowed uses for a zone"""
    return ZONE_USES.get(zone, {}).get("permitted", [])

def get_prohibited_uses(zone: ZoneType) -> List[str]:
    """Returns banned uses for a zone"""
    return ZONE_USES.get(zone, {}).get("prohibited", [])

def is_use_permitted(zone: ZoneType, proposed_use: str) -> bool:
    """Core zoning compliance check"""
    prohibited = get_prohibited_uses(zone)
    permitted = get_permitted_uses(zone)
    
    # Explicit prohibition takes precedence
    if proposed_use in prohibited:
        return False
    return proposed_use in permitted