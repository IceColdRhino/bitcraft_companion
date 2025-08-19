"""
Claims processor for handling claim state table updates.
"""
import ast
import json
import logging

from .base_processor import BaseProcessor
from app.models import ClaimLocalState, ClaimState, ClaimMemberState


class ClaimsProcessor(BaseProcessor):
    """
    Processes claim_local_state and claim_state table updates from SpacetimeDB.

    Handles both real-time transactions and batch subscription updates
    for claim information changes.
    """

    def get_table_names(self):
        """Return list of table names this processor handles."""
        return ["claim_local_state", "claim_state", "claim_member_state"]

    def process_transaction(self, table_update, reducer_name, timestamp):
        """
        Handle claim state transactions - LIVE incremental updates.

        Processes real-time changes to claim data without full refresh.
        """
        try:
            table_name = table_update.get("table_name", "")
            updates = table_update.get("updates", [])

            # Process incremental updates
            claim_updates = {}

            for update in updates:
                inserts = update.get("inserts", [])
                deletes = update.get("deletes", [])

                # Process claim_local_state updates (supplies, treasury, etc.)
                if table_name == "claim_local_state":
                    for insert_str in inserts:
                        try:
                            # Parse JSON string to list first, then use dataclass
                            data = json.loads(insert_str)
                            claim_local = ClaimLocalState.from_array(data)
                            if claim_local:
                                # Only process updates for the current claim
                                claim = self.services.get("claim")
                                if claim and claim.claim_id and str(claim_local.entity_id) == str(claim.claim_id):
                                    claim_updates.update(claim_local.to_dict())
                        except Exception as e:
                            logging.debug(f"Failed to parse claim_local_state transaction: {e}")
                            # Fallback to legacy parsing
                            parsed_data = self._parse_claim_local_state(insert_str)
                            if parsed_data:
                                claim = self.services.get("claim")
                                if claim and claim.claim_id and str(parsed_data.get("entity_id")) == str(claim.claim_id):
                                    claim_updates.update(parsed_data)

                # Process claim_state updates (name changes, etc.)
                elif table_name == "claim_state":
                    for insert_str in inserts:
                        try:
                            # Parse JSON string to list first, then use dataclass
                            data = json.loads(insert_str)
                            claim_state = ClaimState.from_array(data) 
                            if claim_state:
                                # Only process updates for the current claim
                                claim = self.services.get("claim")
                                if claim and claim.claim_id and str(claim_state.entity_id) == str(claim.claim_id):
                                    claim_updates.update(claim_state.to_dict())
                        except Exception as e:
                            logging.debug(f"Failed to parse claim_state transaction: {e}")
                            # Fallback to legacy parsing
                            parsed_data = self._parse_claim_state(insert_str)
                            if parsed_data:
                                claim = self.services.get("claim")
                                if claim and claim.claim_id and str(parsed_data.get("entity_id")) == str(claim.claim_id):
                                    claim_updates.update(parsed_data)

                # Process claim_member_state updates (membership changes)
                elif table_name == "claim_member_state":
                    # For membership changes, do a full refresh since it affects many things
                    self._refresh_claim_info()
                    return

            # Send incremental update if we have changes
            if claim_updates:
                self._send_incremental_claim_update(claim_updates, reducer_name, timestamp)

        except Exception as e:
            logging.error(f"Error handling claim transaction: {e}")

    def process_subscription(self, table_update):
        """
        Handle claim state subscription updates.
        Updates claim object with subscription data and sends to UI.
        """
        try:
            table_name = table_update.get("table_name", "")
            table_rows = []

            # Extract rows from table update
            for update in table_update.get("updates", []):
                for insert_str in update.get("inserts", []):
                    try:
                        row_data = json.loads(insert_str)
                        table_rows.append(row_data)
                    except:
                        pass

            if not table_rows:
                return

            # Handle different table types
            if table_name == "claim_member_state":
                self._process_claim_member_data(table_rows)
            elif table_name == "claim_state":
                # Store claim names
                self._process_claim_state_data(table_rows)

            elif table_name == "claim_local_state":
                # Store claim local details (treasury, supplies, etc.)
                self._process_claim_local_data(table_rows)

            # Send updated claim info to UI
            self._send_claim_info_update()

        except Exception as e:
            logging.error(f"Error handling claim subscription: {e}")

    def _process_claim_member_data(self, claim_member_rows):
        """
        Process claim_member_state data to determine available claims.
        """
        try:
            # Store claim member data for later combination with claim details
            if not hasattr(self, "_claim_members"):
                self._claim_members = {}

            for row in claim_member_rows:
                try:
                    # Create ClaimMemberState dataclass instance
                    member = ClaimMemberState.from_dict(row)
                    self._claim_members[member.claim_entity_id] = {
                        "claim_entity_id": member.claim_entity_id,
                        "player_entity_id": member.player_entity_id,
                        "user_name": member.user_name,
                        "permissions": {
                            "inventory": member.inventory_permission,
                            "build": member.build_permission,
                            "officer": member.officer_permission,
                            "co_owner": member.co_owner_permission,
                        },
                    }
                except (ValueError, TypeError) as e:
                    logging.debug(f"Failed to process claim member row: {e}")
                    # Fallback to manual processing
                    claim_entity_id = row.get("claim_entity_id")
                    if claim_entity_id:
                        self._claim_members[claim_entity_id] = {
                            "claim_entity_id": claim_entity_id,
                            "player_entity_id": row.get("player_entity_id"),
                            "user_name": row.get("user_name"),
                            "permissions": {
                                "inventory": row.get("inventory_permission", False),
                                "build": row.get("build_permission", False),
                                "officer": row.get("officer_permission", False),
                                "co_owner": row.get("co_owner_permission", False),
                            },
                        }

            # Send current claim info update instead of claims list
            # (Claims list is managed by DataService with one-off queries for all user claims)
            self._send_claim_info_update()

        except Exception as e:
            logging.error(f"Error processing claim member data: {e}")

    def _process_claim_state_data(self, claim_state_rows):
        """
        Process claim_state data to store claim names.
        """
        try:
            # Store claim names data
            if not hasattr(self, "_claim_names"):
                self._claim_names = {}

            for row in claim_state_rows:
                try:
                    # Create ClaimState dataclass instance
                    claim_state = ClaimState.from_dict(row)
                    self._claim_names[claim_state.entity_id] = claim_state.name or f"Claim {claim_state.entity_id}"
                except (ValueError, TypeError) as e:
                    logging.debug(f"Failed to process claim state row: {e}")
                    # Fallback to manual processing
                    entity_id = row.get("entity_id")
                    if entity_id:
                        self._claim_names[entity_id] = row.get("name", f"Claim {entity_id}")

            # Send current claim info update instead of claims list
            self._send_claim_info_update()

        except Exception as e:
            logging.error(f"Error processing claim state data: {e}")

    def _process_claim_local_data(self, claim_local_rows):
        """
        Process claim_local_state data to store claim details (treasury, supplies, etc.).
        """
        try:
            # Store claim local details data
            if not hasattr(self, "_claim_local_details"):
                self._claim_local_details = {}

            for row in claim_local_rows:
                try:
                    # Create ClaimLocalState dataclass instance
                    local_state = ClaimLocalState.from_dict(row)
                    self._claim_local_details[local_state.entity_id] = {
                        "treasury": local_state.treasury,
                        "supplies": local_state.supplies,
                        "tile_count": local_state.num_tiles,
                        "building_description_id": local_state.building_description_id,
                        "location": local_state.location,
                    }
                except (ValueError, TypeError) as e:
                    logging.debug(f"Failed to process claim local row: {e}")
                    # Fallback to manual processing
                    entity_id = row.get("entity_id")
                    if entity_id:
                        self._claim_local_details[entity_id] = {
                            "treasury": row.get("treasury", 0),
                            "supplies": row.get("supplies", 0),
                            "tile_count": row.get("num_tiles", 0),
                            "building_description_id": row.get("building_description_id"),
                            "location": row.get("location", []),
                        }

            # Send current claim info update instead of claims list
            self._send_claim_info_update()

        except Exception as e:
            logging.error(f"Error processing claim local data: {e}")

    def _send_claim_info_update(self):
        """
        Send claim info update for the current claim only.
        Claims list management is handled by DataService.
        """
        try:
            # Check if we have all required data types
            if not (hasattr(self, "_claim_members") and self._claim_members):
                return

            if not (hasattr(self, "_claim_names") and self._claim_names):
                return

            if not (hasattr(self, "_claim_local_details") and self._claim_local_details):
                return

            claim = self.services.get("claim")
            if not claim:
                return

            current_claim_id = getattr(claim, "claim_id", None)
            if not current_claim_id:
                return

            # Send claim info update only for the current claim
            if current_claim_id in self._claim_members:
                claim_details = self._get_claim_details(current_claim_id)
                claim_info = {
                    "entity_id": current_claim_id,
                    "name": claim_details["name"],
                    "treasury": claim_details["treasury"],
                    "supplies": claim_details["supplies"],
                    "tile_count": claim_details["tile_count"],
                }

                self._queue_update("claim_info_update", claim_info)

        except Exception as e:
            logging.error(f"Error sending claim info update: {e}")

    def _get_claim_details(self, claim_entity_id):
        """
        Get claim details for a specific claim entity ID by combining cached subscription data.
        """
        # Get name from claim_state cache
        claim_name = (
            self._claim_names.get(claim_entity_id, f"Claim {claim_entity_id}")
            if hasattr(self, "_claim_names")
            else f"Claim {claim_entity_id}"
        )

        # Get details from claim_local_state cache
        local_details = self._claim_local_details.get(claim_entity_id, {}) if hasattr(self, "_claim_local_details") else {}

        return {
            "name": claim_name,
            "treasury": local_details.get("treasury", 0),
            "supplies": local_details.get("supplies", 0),
            "tile_count": local_details.get("tile_count", 0),
        }

    def _refresh_claim_info(self):
        """
        Process claim info from subscription data and send to UI.
        Uses only data already available from claim object (populated by subscriptions).
        """
        try:
            # Get claim from services
            claim = self.services.get("claim")

            if claim and claim.claim_id:
                # Use data that's already been populated by subscription updates
                fresh_claim_info = {
                    "claim_id": claim.claim_id,
                    "name": getattr(claim, "claim_name", "Unknown Claim"),
                    "treasury": getattr(claim, "treasury", 0),
                    "supplies": getattr(claim, "supplies", 0),
                    "tile_count": getattr(claim, "size", 0),
                    "supplies_per_hour": 0,  # Calculated in UI
                }

                self._queue_update("claim_info_update", fresh_claim_info, {"subscription_update": True})
            else:
                logging.warning("Cannot refresh claim info - missing claim")

        except Exception as e:
            logging.error(f"Error processing claim info from subscription: {e}")

    def _parse_claim_local_state(self, data_str):
        """
        Parse claim_local_state from SpacetimeDB transaction format.

        Format: [entity_id, supplies, building_maintenance, num_tiles, num_tile_neighbors, location, treasury, xp_gained_since_last_coin_minting, supplies_purchase_threshold, supplies_purchase_price, building_description_id]
        Example: [360287970205437165,9898,0.0,1411,8074,[0,[10956,8796,1]],16158,367,200,1.0,405]
        Position: 0=entity_id, 1=supplies, 2=building_maintenance, 3=num_tiles, 4=num_tile_neighbors, 5=location, 6=treasury, 7=xp_gained_since_last_coin_minting, 8=supplies_purchase_threshold, 9=supplies_purchase_price, 10=building_description_id
        """
        try:

            data = ast.literal_eval(data_str)
            if not isinstance(data, list) or len(data) < 11:
                return None

            # Extract values based on exact claim_local_state structure
            entity_id = data[0]  # Position 0: entity_id
            supplies = data[1]  # Position 1: supplies
            building_maintenance = data[2]  # Position 2: building_maintenance
            num_tiles = data[3]  # Position 3: num_tiles
            num_tile_neighbors = data[4]  # Position 4: num_tile_neighbors
            location = data[5]  # Position 5: location
            treasury = data[6]  # Position 6: treasury
            xp_gained = data[7]  # Position 7: xp_gained_since_last_coin_minting
            supplies_threshold = data[8]  # Position 8: supplies_purchase_threshold
            supplies_price = data[9]  # Position 9: supplies_purchase_price
            building_desc_id = data[10]  # Position 10: building_description_id

            return {
                "entity_id": entity_id,
                "supplies": supplies,
                "treasury": treasury,
                "num_tiles": num_tiles,
                "building_maintenance": building_maintenance,
                "num_tile_neighbors": num_tile_neighbors,
                "location": location,
                "xp_gained_since_last_coin_minting": xp_gained,
                "supplies_purchase_threshold": supplies_threshold,
                "supplies_purchase_price": supplies_price,
                "building_description_id": building_desc_id,
            }

        except Exception as e:
            return None

    def _parse_claim_state(self, data_str):
        """
        Parse claim_state from SpacetimeDB transaction format.

        Format: [entity_id, owner_player_entity_id, owner_building_entity_id, name, neutral]
        Example: [360287970203715017, 576460752315731874, 360287970203714996, "Retirement Home T4", false]
        """
        try:
            data = ast.literal_eval(data_str)
            if not isinstance(data, list) or len(data) < 5:
                return None

            # Extract values based on claim_state structure
            entity_id = data[0]  # Position 0: entity_id
            owner_player_entity_id = data[1]  # Position 1: owner_player_entity_id
            owner_building_entity_id = data[2]  # Position 2: owner_building_entity_id
            name = data[3] if len(data) > 3 else "Unknown Claim"  # Position 3: name
            neutral = data[4] if len(data) > 4 else False  # Position 4: neutral

            return {
                "entity_id": entity_id,
                "owner_player_entity_id": owner_player_entity_id,
                "owner_building_entity_id": owner_building_entity_id,
                "name": name,
                "neutral": neutral,
            }

        except Exception as e:
            return None

    def _send_incremental_claim_update(self, claim_updates, reducer_name, timestamp):
        """
        Send incremental claim update to UI without full refresh.
        """
        try:
            # Get current claim from services
            claim = self.services.get("claim")

            if not claim:
                logging.warning("No claim available for incremental update")
                return

            # Build current claim info
            current_claim_info = {
                "claim_id": claim.claim_id,
                "name": getattr(claim, "claim_name", "Unknown Claim"),
                "treasury": getattr(claim, "treasury", 0),
                "supplies": getattr(claim, "supplies", 0),
                "tile_count": getattr(claim, "size", 0),
                "supplies_per_hour": 0,
            }

            # Apply incremental updates and update claim object
            updated_fields = []

            if "supplies" in claim_updates:
                current_claim_info["supplies"] = claim_updates["supplies"]
                setattr(claim, "supplies", claim_updates["supplies"])
                updated_fields.append("supplies")

            if "treasury" in claim_updates:
                current_claim_info["treasury"] = claim_updates["treasury"]
                setattr(claim, "treasury", claim_updates["treasury"])
                updated_fields.append("treasury")

            if "name" in claim_updates:
                current_claim_info["name"] = claim_updates["name"]
                setattr(claim, "claim_name", claim_updates["name"])
                updated_fields.append("name")

            if "num_tiles" in claim_updates:
                current_claim_info["tile_count"] = claim_updates["num_tiles"]
                setattr(claim, "size", claim_updates["num_tiles"])
                updated_fields.append("tile_count")

            # Send targeted update with incremental flag
            self._queue_update(
                "claim_info_update",
                current_claim_info,
                changes={
                    "type": "incremental",
                    "source": "live_transaction",
                    "reducer": reducer_name,
                    "updated_fields": updated_fields,
                },
                timestamp=timestamp,
            )

            # Log the actual values that were updated (focus on UI-relevant fields)
            log_parts = []
            if "supplies" in claim_updates:
                log_parts.append(f"Supplies={claim_updates['supplies']}")
            if "treasury" in claim_updates:
                log_parts.append(f"Treasury={claim_updates['treasury']}")
            if "num_tiles" in claim_updates:
                log_parts.append(f"Tiles={claim_updates['num_tiles']}")
            if "name" in claim_updates:
                log_parts.append(f"Name='{claim_updates['name']}'")
            if "xp_gained_since_last_coin_minting" in claim_updates:
                log_parts.append(f"XP={claim_updates['xp_gained_since_last_coin_minting']}")

            if not log_parts:
                # Log other field updates that don't affect UI directly
                other_fields = [
                    k
                    for k in claim_updates.keys()
                    if k not in ["supplies", "treasury", "num_tiles", "name", "xp_gained_since_last_coin_minting"]
                ]

        except Exception as e:
            logging.error(f"Error sending incremental claim update: {e}")

    def clear_cache(self):
        """Clear cached claims data when switching claims."""
        super().clear_cache()

        # Clear claim-specific cached data
        if hasattr(self, "_claim_members"):
            self._claim_members.clear()

        if hasattr(self, "_claim_names"):
            self._claim_names.clear()

        if hasattr(self, "_claim_local_details"):
            self._claim_local_details.clear()
