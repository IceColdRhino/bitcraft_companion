"""
Cascading Inventory Service

Provides cascading inventory optimization that reduces material requirements
based on intermediate materials already in inventory.

Example: Having 100 Cloth in inventory reduces requirements for:
- 100 Cloth Strip (direct dependency)
- 100 Wispweave Filament (direct dependency)
- 300 Thread (indirect via Cloth Strip)
- 900 Fiber (indirect via Thread)

This creates a cascading reduction where higher-tier materials automatically
reduce ALL their dependency chains.
"""

import logging
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


class CascadingInventoryCalculator:
    """
    Calculates optimized material requirements using cascading inventory reductions.

    Uses pre-computed dependency trees from templates to efficiently apply
    inventory reductions across complete crafting chains.
    """

    def __init__(self):
        self._cache = {}  # Cache for performance optimization
        self._cache_hits = 0
        self._cache_misses = 0
        self._complexity_scores = {}

    def apply_cascading_reductions(
        self, base_requirements: Dict[str, int], consolidated_inventory: Dict[str, Dict], dependency_trees: Dict[str, Dict]
    ) -> Dict[str, Dict]:
        """
        Apply cascading inventory reductions to base material requirements with tier-based filtering.

        Args:
            base_requirements: Dict of {material_name: quantity_needed}
            consolidated_inventory: Dict of {material_name: {'total_quantity': int, 'tier': int, ...}}
            dependency_trees: Dict of {material_name: {'dependencies': {'all': [(name, qty)]}, 'tier': int}}

        Returns:
            Dict of {material_name: {
                'original_need': int,
                'inventory_reduction': int,
                'final_need': int,
                'has_inventory': bool
            }}
        """
        # Create cache key for performance
        inventory_supplies = {k: v.get('total_quantity', 0) for k, v in consolidated_inventory.items()}
        cache_key = self._build_cache_key(base_requirements, inventory_supplies)
        if cache_key in self._cache:
            self._cache_hits += 1
            return self._cache[cache_key]

        self._cache_misses += 1

        # Start with base requirements
        result = {}
        working_requirements = base_requirements.copy()
        total_reductions = defaultdict(int)
        
        inventory_items = self._get_sorted_inventory_items_from_consolidated(consolidated_inventory, dependency_trees)

        for material_name, inventory_quantity, inventory_tier in inventory_items:
            if inventory_quantity <= 0:
                continue

            material_info = dependency_trees.get(material_name, {})
            dependencies = material_info.get("dependencies", {})
            all_deps = dependencies.get("all", [])

            reductions_applied = 0
            material_base_quantity = material_info.get('quantity', 1)
            if material_base_quantity <= 0:
                material_base_quantity = 1
                
            for dep_name, dep_total_quantity in all_deps:
                if dep_name in working_requirements:
                    dep_material_info = dependency_trees.get(dep_name, {})
                    dep_tier = dep_material_info.get('tier', 1)
                    dep_ratio = dep_total_quantity / material_base_quantity
                    
                    if inventory_tier >= dep_tier:
                        max_reduction = min(
                            inventory_quantity * dep_ratio,
                            working_requirements[dep_name],
                        )

                        if max_reduction > 0:
                            working_requirements[dep_name] -= max_reduction
                            total_reductions[dep_name] += max_reduction
                            reductions_applied += 1

        # Build result with detailed reduction info
        for material_name, original_need in base_requirements.items():
            final_need = max(0, working_requirements.get(material_name, 0))
            inventory_reduction = total_reductions.get(material_name, 0)
            has_inventory = consolidated_inventory.get(material_name, {}).get('total_quantity', 0) > 0

            result[material_name] = {
                "original_need": original_need,
                "inventory_reduction": inventory_reduction,
                "final_need": final_need,
                "has_inventory": has_inventory,
            }

        # Cache the result
        self._cache[cache_key] = result

        return result

    def _update_complexity_scores(self, dependency_trees: Dict[str, Dict]):
        """Pre-compute complexity scores for all materials to avoid repeated calculations."""
        for material_name, material_info in dependency_trees.items():
            if material_name not in self._complexity_scores:
                dependencies = material_info.get("dependencies", {})
                self._complexity_scores[material_name] = len(dependencies.get("all", []))

    def _get_sorted_inventory_items_from_consolidated(self, consolidated_inventory: Dict[str, Dict], dependency_trees: Dict[str, Dict]) -> List[Tuple[str, int, int]]:
        """Get inventory items sorted by complexity for optimal reduction, with tier information."""
        self._update_complexity_scores(dependency_trees)

        inventory_with_complexity = []
        for material_name, item_data in consolidated_inventory.items():
            if isinstance(item_data, dict):
                quantity = item_data.get('total_quantity', 0)
                tier = item_data.get('tier', 1)
                if quantity > 0:
                    complexity = self._complexity_scores.get(material_name, 0)
                    inventory_with_complexity.append((material_name, quantity, tier, complexity))

        inventory_with_complexity.sort(key=lambda x: (x[3], x[1]), reverse=True)
        return [(name, qty, tier) for name, qty, tier, _ in inventory_with_complexity]

    def _get_sorted_inventory_items(self, inventory: Dict[str, int], dependency_trees: Dict[str, Dict]) -> List[Tuple[str, int]]:
        """Get inventory items sorted by complexity for optimal reduction."""
        self._update_complexity_scores(dependency_trees)

        inventory_with_complexity = []
        for material_name, quantity in inventory.items():
            if quantity > 0:
                complexity = self._complexity_scores.get(material_name, 0)
                inventory_with_complexity.append((material_name, quantity, complexity))

        inventory_with_complexity.sort(key=lambda x: (x[2], x[1]), reverse=True)
        return [(name, qty) for name, qty, _ in inventory_with_complexity]

    def _build_cache_key(self, base_requirements: Dict[str, int], inventory: Dict[str, int]) -> str:
        """Build cache key from requirements and inventory state."""
        req_items = sorted(base_requirements.items())
        inv_items = sorted((k, v) for k, v in inventory.items() if v > 0)
        return f"req:{req_items}|inv:{inv_items}"

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache performance statistics."""
        return {"hits": self._cache_hits, "misses": self._cache_misses, "entries": len(self._cache)}

    def clear_cache(self):
        """Clear the calculation cache."""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0


def extract_dependency_trees_from_templates(profession_templates: Dict) -> Dict[str, Dict]:
    """
    Extract dependency trees from loaded profession templates.

    Args:
        profession_templates: Loaded template data with dependency information

    Returns:
        Flattened dict of {material_name: dependency_info} for all materials
    """
    dependency_trees = {}

    for profession, tiers in profession_templates.items():
        for tier, materials in tiers.items():
            for material_name, material_info in materials.items():
                if material_name not in dependency_trees:
                    dependency_trees[material_name] = material_info
                # If material appears in multiple places, keep the one with more dependencies
                elif len(material_info.get("dependencies", {}).get("all", [])) > len(
                    dependency_trees[material_name].get("dependencies", {}).get("all", [])
                ):
                    dependency_trees[material_name] = material_info

    return dependency_trees
