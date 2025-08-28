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
    ClaimTechState,
    ClaimTechDesc,
    TravelerTaskState,
    InventoryState,
    PassiveCraftState,
    StaminaState,
    CharacterStatsState,
    MarketOrderState,
    # Reference data dataclasses
    ResourceDesc,
    ItemDesc,
    CargoDesc,
    ToolDesc,
    BuildingDesc,
    BuildingTypeDesc,
    CraftingRecipeDesc,
    ExtractionRecipeDesc,
    ItemConversionRecipeDesc,
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
    "ClaimTechState", 
    "ClaimTechDesc",
    "TravelerTaskState",
    "InventoryState",
    "PassiveCraftState",
    "StaminaState",
    "CharacterStatsState",
    "MarketOrderState",
    # Reference data dataclasses
    "ResourceDesc",
    "ItemDesc",
    "CargoDesc",
    "ToolDesc",
    "BuildingDesc",
    "BuildingTypeDesc",
    "CraftingRecipeDesc",
    "ExtractionRecipeDesc",
    "ItemConversionRecipeDesc",
    "ItemListDesc",
    "ClaimTileCost",
    "NpcDesc",
    "BuildingFunctionTypeMappingDesc",
]