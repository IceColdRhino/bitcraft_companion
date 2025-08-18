"""
Models package for BitCraft Companion.

Contains structured data classes for SpacetimeDB entities and other data models.
"""

from .object_dataclasses import (
    ProgressiveActionState,
    PublicProgressiveActionState,
    BuildingState,
    ClaimMemberState,
    ClaimState,
    ClaimLocalState,
    TravelerTaskState,
    InventoryState,
    PassiveCraftState,
    MarketOrderState,
    # Reference data dataclasses
    ResourceDesc,
    ItemDesc,
    CargoDesc,
    BuildingDesc,
    BuildingTypeDesc,
    CraftingRecipeDesc,
    ExtractionRecipeDesc,
    ItemListDesc,
    ClaimTileCost,
    NpcDesc,
    BuildingFunctionTypeMappingDesc,
)

__all__ = [
    "ProgressiveActionState",
    "PublicProgressiveActionState", 
    "BuildingState",
    "ClaimMemberState",
    "ClaimState",
    "ClaimLocalState",
    "TravelerTaskState",
    "InventoryState",
    "PassiveCraftState",
    "MarketOrderState",
    # Reference data dataclasses
    "ResourceDesc",
    "ItemDesc",
    "CargoDesc",
    "BuildingDesc",
    "BuildingTypeDesc",
    "CraftingRecipeDesc",
    "ExtractionRecipeDesc",
    "ItemListDesc",
    "ClaimTileCost",
    "NpcDesc",
    "BuildingFunctionTypeMappingDesc",
]