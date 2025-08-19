"""
Search parser service for handling keyword-based search with comparison operators.

Supports search syntax like:
- item=plank (string contains)
- tier>3 (numeric greater than)
- quantity<100 (numeric less than)
- container=carving (special container search)
- Mixed: "item=stone tier>2 quantity<50"
"""

import re
import logging
from typing import Dict, List, Tuple, Union, Any, Optional


class SearchParser:
    """
    Parses search queries with keyword filters and comparison operators.
    
    Supports operators: =, >, <, >=, <=, !=
    Handles both string and numeric field types.
    """
    
    # Regex pattern to match keyword operators
    # Matches: field>=value, field<=value, field!=value, field>value, field<value, field=value
    KEYWORD_PATTERN = re.compile(r'(\w+)(>=|<=|!=|>|<|=)([^\s]+)')
    
    # Define which fields are numeric for proper comparison handling
    NUMERIC_FIELDS = {
        'tier', 'quantity', 'qty', 'time', 'effort', 'remaining_effort', 
        'time_remaining', 'jobs', 'accept_help'
    }
    
    # Define field aliases for different tabs
    FIELD_ALIASES = {
        'item': ['name', 'item'],
        'container': ['containers', 'container'],
        'containers': ['containers', 'container'],
        'building': ['building'],
        'crafter': ['crafter'],
        'traveler': ['traveler'],
        'status': ['status'],
        'tag': ['tag'],
        'tier': ['tier'],
        'quantity': ['quantity'],
        'qty': ['quantity'],  # Shortcut for quantity
        'time': ['time_remaining', 'time'],
        'effort': ['remaining_effort', 'effort'],
        'jobs': ['jobs'],
        'help': ['accept_help']
    }
    
    def __init__(self):
        """Initialize the search parser."""
        self.logger = logging.getLogger(__name__)
    
    def parse_search_query(self, search_text: str) -> Dict[str, Any]:
        """
        Parse a search query into keywords and regular search terms.
        
        Args:
            search_text: The raw search query string
            
        Returns:
            Dict containing:
            - 'keywords': Dict of {field: (operator, value)}
            - 'regular_terms': List of non-keyword search terms
        """
        if not search_text or not search_text.strip():
            return {'keywords': {}, 'regular_terms': []}
        
        search_text = search_text.strip()
        keywords = {}
        remaining_text = search_text
        
        # Find all keyword matches
        for match in self.KEYWORD_PATTERN.finditer(search_text):
            field = match.group(1).lower()
            operator = match.group(2)
            value_str = match.group(3)
            
            # Process the value based on field type
            processed_value = self._process_value(field, value_str)
            
            # Store the parsed keyword - support multiple conditions per field
            if field not in keywords:
                keywords[field] = []
            keywords[field].append((operator, processed_value))
            
            # Remove this match from the remaining text
            remaining_text = remaining_text.replace(match.group(0), ' ', 1)
        
        # Extract any remaining non-keyword terms
        regular_terms = [term.strip() for term in remaining_text.split() if term.strip()]
        
        self.logger.debug(f"Parsed search '{search_text}' → keywords: {keywords}, regular: {regular_terms}")
        
        return {
            'keywords': keywords,
            'regular_terms': regular_terms
        }
    
    def _process_value(self, field: str, value_str: str) -> Union[str, int, float]:
        """
        Process a search value based on the field type.
        
        Args:
            field: The field name
            value_str: The raw value string
            
        Returns:
            Processed value (string, int, or float)
        """
        # Check if this field should be treated as numeric
        if field in self.NUMERIC_FIELDS:
            try:
                # Try integer first, then float
                if '.' in value_str:
                    return float(value_str)
                else:
                    return int(value_str)
            except ValueError:
                # If numeric conversion fails, treat as string
                self.logger.warning(f"Failed to convert '{value_str}' to number for field '{field}', treating as string")
                return value_str.lower()
        
        # For string fields, convert to lowercase for case-insensitive matching
        return value_str.lower()
    
    def match_row(self, row: Dict[str, Any], parsed_query: Dict[str, Any]) -> bool:
        """
        Check if a data row matches the parsed search query.
        
        Args:
            row: The data row to check
            parsed_query: Result from parse_search_query()
            
        Returns:
            True if the row matches, False otherwise
        """
        # Check keyword filters
        for field, conditions in parsed_query['keywords'].items():
            if not self._match_keyword_filter(row, field, conditions):
                return False
        
        # Check regular terms (must match somewhere in the row)
        for term in parsed_query['regular_terms']:
            if not self._match_regular_term(row, term):
                return False
        
        return True
    
    def _match_keyword_filter(self, row: Dict[str, Any], field: str, conditions: List[Tuple[str, Union[str, int, float]]]) -> bool:
        """
        Check if a row matches all conditions for a specific keyword field.
        
        Args:
            row: The data row
            field: The field name to check
            conditions: List of (operator, value) tuples - ALL must be satisfied (AND logic)
            
        Returns:
            True if ALL conditions match, False otherwise
        """
        # Get the actual field names to check (handle aliases)
        field_names = self.FIELD_ALIASES.get(field, [field])
        
        # Try each possible field name
        for field_name in field_names:
            row_value = row.get(field_name)
            if row_value is not None:
                # Check if ALL conditions are satisfied for this field
                all_conditions_met = True
                for operator, value in conditions:
                    if not self._compare_values(row_value, operator, value, field_name):
                        all_conditions_met = False
                        break
                
                # If all conditions are met for this field name, the filter passes
                if all_conditions_met:
                    return True
        
        return False
    
    def _compare_values(self, row_value: Any, operator: str, search_value: Union[str, int, float], field_name: str) -> bool:
        """
        Compare a row value against a search value using the specified operator.
        
        Args:
            row_value: Value from the data row
            operator: Comparison operator (=, >, <, >=, <=, !=)
            search_value: Value to compare against
            field_name: Name of the field being compared
            
        Returns:
            True if comparison matches, False otherwise
        """
        try:
            # Special handling for containers field
            if field_name in ['containers', 'container'] and isinstance(row_value, dict):
                return self._match_containers(row_value, operator, search_value)
            
            # Handle numeric comparisons
            if isinstance(search_value, (int, float)):
                row_numeric = self._convert_to_numeric(row_value)
                if row_numeric is not None:
                    return self._numeric_compare(row_numeric, operator, search_value)
            
            # Handle string comparisons
            row_str = str(row_value).lower()
            search_str = str(search_value).lower()
            
            if operator == '=':
                return search_str in row_str
            elif operator == '!=':
                return search_str not in row_str
            else:
                # For non-= operators on strings, try numeric conversion
                row_numeric = self._convert_to_numeric(row_value)
                search_numeric = self._convert_to_numeric(search_value)
                if row_numeric is not None and search_numeric is not None:
                    return self._numeric_compare(row_numeric, operator, search_numeric)
                # Fall back to string comparison for >, < on strings (alphabetical)
                return self._string_compare(row_str, operator, search_str)
                
        except Exception as e:
            self.logger.debug(f"Error comparing {row_value} {operator} {search_value}: {e}")
            return False
    
    def _match_containers(self, containers: Dict[str, Any], operator: str, search_value: str) -> bool:
        """
        Special matching logic for containers field.
        
        Args:
            containers: Dict of container names to quantities
            operator: Comparison operator
            search_value: Search term
            
        Returns:
            True if condition matches, False otherwise
        """
        search_str = str(search_value).lower()
        
        if operator == '=':
            # For = operator, return True if ANY container contains the search term
            for container_name in containers.keys():
                container_str = str(container_name).lower()
                if search_str in container_str:
                    return True
            return False
        elif operator == '!=':
            # For != operator, return True if NO container contains the search term
            for container_name in containers.keys():
                container_str = str(container_name).lower()
                if search_str in container_str:
                    return False  # Found a match, so != condition fails
            return True  # No matches found, so != condition passes
        
        return False
    
    def _numeric_compare(self, row_value: Union[int, float], operator: str, search_value: Union[int, float]) -> bool:
        """
        Perform numeric comparison.
        
        Args:
            row_value: Numeric value from row
            operator: Comparison operator
            search_value: Numeric search value
            
        Returns:
            True if comparison matches, False otherwise
        """
        if operator == '=':
            return row_value == search_value
        elif operator == '!=':
            return row_value != search_value
        elif operator == '>':
            return row_value > search_value
        elif operator == '<':
            return row_value < search_value
        elif operator == '>=':
            return row_value >= search_value
        elif operator == '<=':
            return row_value <= search_value
        
        return False
    
    def _string_compare(self, row_str: str, operator: str, search_str: str) -> bool:
        """
        Perform string comparison (alphabetical for >, <).
        
        Args:
            row_str: String value from row (lowercase)
            operator: Comparison operator
            search_str: Search string (lowercase)
            
        Returns:
            True if comparison matches, False otherwise
        """
        if operator == '>':
            return row_str > search_str
        elif operator == '<':
            return row_str < search_str
        elif operator == '>=':
            return row_str >= search_str
        elif operator == '<=':
            return row_str <= search_str
        
        return False
    
    def _convert_to_numeric(self, value: Any) -> Optional[Union[int, float]]:
        """
        Try to convert a value to numeric type.
        
        Args:
            value: Value to convert
            
        Returns:
            Numeric value or None if conversion fails
        """
        if isinstance(value, (int, float)):
            return value
        
        if isinstance(value, str):
            # Remove common non-numeric parts
            clean_value = value.strip()
            
            # Handle percentage values
            if clean_value.endswith('%'):
                try:
                    return float(clean_value[:-1])
                except ValueError:
                    pass
            
            # Try direct conversion
            try:
                if '.' in clean_value:
                    return float(clean_value)
                else:
                    return int(clean_value)
            except ValueError:
                pass
        
        return None
    
    def _match_regular_term(self, row: Dict[str, Any], term: str) -> bool:
        """
        Check if a regular search term matches anywhere in the row.
        
        Args:
            row: The data row
            term: Search term to match
            
        Returns:
            True if term matches somewhere in the row, False otherwise
        """
        term_lower = term.lower()
        
        for key, value in row.items():
            # Special handling for containers
            if key in ['containers', 'container'] and isinstance(value, dict):
                for container_name in value.keys():
                    if term_lower in str(container_name).lower():
                        return True
            else:
                if term_lower in str(value).lower():
                    return True
        
        return False
    
    def get_keyword_suggestions(self, tab_name: str) -> List[str]:
        """
        Get suggested keywords for a specific tab.
        
        Args:
            tab_name: Name of the current tab
            
        Returns:
            List of suggested keyword examples
        """
        base_suggestions = ['item=plank', 'tier>2', 'quantity<100']
        
        if 'inventory' in tab_name.lower():
            return base_suggestions + ['container=carving', 'tag=refined']
        elif 'crafting' in tab_name.lower():
            return base_suggestions + ['building=workshop', 'crafter=john', 'time<60']
        elif 'task' in tab_name.lower():
            return base_suggestions + ['traveler=merchant', 'status=active']
        
        return base_suggestions