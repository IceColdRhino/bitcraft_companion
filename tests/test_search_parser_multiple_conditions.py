"""
Tests for SearchParser multiple conditions functionality.

Tests the enhanced search system that supports multiple conditions per field
with AND logic (e.g., item=log item!=package qty<500).
"""

import pytest
from app.services.search_parser import SearchParser


class TestSearchParserMultipleConditions:
    """Test multiple conditions per field functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = SearchParser()
    
    def test_parse_multiple_conditions_same_field(self):
        """Test parsing multiple conditions for the same field."""
        result = self.parser.parse_search_query("item=log item!=package qty<500")
        
        expected = {
            'keywords': {
                'item': [('=', 'log'), ('!=', 'package')],
                'qty': [('<', 500)]
            },
            'regular_terms': []
        }
        
        assert result == expected
    
    def test_parse_multiple_numeric_conditions(self):
        """Test parsing multiple numeric conditions (range queries)."""
        result = self.parser.parse_search_query("tier>2 tier<6 qty>=10 qty<=100")
        
        expected = {
            'keywords': {
                'tier': [('>', 2), ('<', 6)],
                'qty': [('>=', 10), ('<=', 100)]
            },
            'regular_terms': []
        }
        
        assert result == expected
    
    def test_parse_single_condition_backward_compatibility(self):
        """Test that single conditions still work (backward compatibility)."""
        result = self.parser.parse_search_query("item=plank tier>3")
        
        expected = {
            'keywords': {
                'item': [('=', 'plank')],
                'tier': [('>', 3)]
            },
            'regular_terms': []
        }
        
        assert result == expected
    
    def test_match_multiple_conditions_all_true(self):
        """Test matching when all conditions are satisfied."""
        query = self.parser.parse_search_query("item=log item!=package qty<500")
        
        # Row that should match
        row = {
            'name': 'oak log bundle',
            'quantity': 250,
            'tier': 3
        }
        
        assert self.parser.match_row(row, query) == True
    
    def test_match_multiple_conditions_first_fails(self):
        """Test matching when first condition fails."""
        query = self.parser.parse_search_query("item=log item!=package qty<500")
        
        # Row that should NOT match (doesn't contain "log")
        row = {
            'name': 'stone block',
            'quantity': 250,
            'tier': 3
        }
        
        assert self.parser.match_row(row, query) == False
    
    def test_match_multiple_conditions_second_fails(self):
        """Test matching when second condition fails."""
        query = self.parser.parse_search_query("item=log item!=package qty<500")
        
        # Row that should NOT match (contains "package")
        row = {
            'name': 'log package bundle',
            'quantity': 250,
            'tier': 3
        }
        
        assert self.parser.match_row(row, query) == False
    
    def test_match_numeric_range_conditions(self):
        """Test matching numeric range conditions."""
        query = self.parser.parse_search_query("tier>2 tier<6 qty>=10 qty<=100")
        
        # Row that should match (tier 3, qty 50)
        row = {
            'name': 'test item',
            'tier': 3,
            'quantity': 50
        }
        
        assert self.parser.match_row(row, query) == True
        
        # Row that should NOT match (tier too high)
        row_fail = {
            'name': 'test item',
            'tier': 7,
            'quantity': 50
        }
        
        assert self.parser.match_row(row_fail, query) == False
    
    def test_match_quantity_range(self):
        """Test quantity range matching."""
        query = self.parser.parse_search_query("qty>=10 qty<=100")
        
        # Test boundary values
        assert self.parser.match_row({'quantity': 10}, query) == True   # Lower bound
        assert self.parser.match_row({'quantity': 100}, query) == True  # Upper bound
        assert self.parser.match_row({'quantity': 50}, query) == True   # Within range
        assert self.parser.match_row({'quantity': 5}, query) == False   # Below range
        assert self.parser.match_row({'quantity': 150}, query) == False # Above range
    
    def test_match_with_field_aliases(self):
        """Test multiple conditions work with field aliases."""
        query = self.parser.parse_search_query("qty>10 quantity<100")
        
        # Both "qty" and "quantity" should map to the same field
        row = {
            'quantity': 50
        }
        
        assert self.parser.match_row(row, query) == True
    
    def test_mixed_conditions_and_regular_terms(self):
        """Test multiple conditions mixed with regular search terms."""
        query = self.parser.parse_search_query("item=stone item!=refined tier>1 building")
        
        expected = {
            'keywords': {
                'item': [('=', 'stone'), ('!=', 'refined')],
                'tier': [('>', 1)]
            },
            'regular_terms': ['building']
        }
        
        assert query == expected
    
    def test_complex_container_conditions(self):
        """Test multiple conditions with container fields."""
        query = self.parser.parse_search_query("container=carving container!=workshop")
        
        # Row with containers dict
        row = {
            'containers': {
                'carving bench': 5,
                'storage chest': 10
            }
        }
        
        assert self.parser.match_row(row, query) == True
        
        # Row that should fail (contains workshop)
        row_fail = {
            'containers': {
                'carving workshop': 5,
                'storage chest': 10
            }
        }
        
        assert self.parser.match_row(row_fail, query) == False
    
    def test_building_multiple_conditions(self):
        """Test multiple building conditions."""
        query = self.parser.parse_search_query("building=workshop building!=forge")
        
        # Should match workshop that's not a forge
        row = {
            'building': 'crafting workshop'
        }
        
        assert self.parser.match_row(row, query) == True
        
        # Should NOT match forge workshop
        row_fail = {
            'building': 'forge workshop'
        }
        
        assert self.parser.match_row(row_fail, query) == False
    
    def test_three_conditions_same_field(self):
        """Test three or more conditions on the same field."""
        query = self.parser.parse_search_query("tier>1 tier<5 tier!=3")
        
        # Should match tier 2 and 4, but not 1, 3, or 5+
        assert self.parser.match_row({'tier': 2}, query) == True
        assert self.parser.match_row({'tier': 4}, query) == True
        assert self.parser.match_row({'tier': 1}, query) == False  # Too low
        assert self.parser.match_row({'tier': 3}, query) == False  # Excluded
        assert self.parser.match_row({'tier': 5}, query) == False  # Too high
    
    def test_empty_query_multiple_conditions(self):
        """Test empty query returns everything."""
        query = self.parser.parse_search_query("")
        
        expected = {
            'keywords': {},
            'regular_terms': []
        }
        
        assert query == expected
        assert self.parser.match_row({'name': 'anything'}, query) == True
    
    def test_performance_many_conditions(self):
        """Test performance with many conditions (basic smoke test)."""
        # This shouldn't crash or be extremely slow
        complex_query = "item=log item!=package item!=bundle tier>1 tier<6 tier!=3 qty>5 qty<1000 qty!=100"
        query = self.parser.parse_search_query(complex_query)
        
        # Should parse without errors
        assert 'item' in query['keywords']
        assert 'tier' in query['keywords']
        assert 'qty' in query['keywords']
        
        # Check we have the right number of conditions
        assert len(query['keywords']['item']) == 3
        assert len(query['keywords']['tier']) == 3  
        assert len(query['keywords']['qty']) == 3
    
    def test_debug_logging(self):
        """Test that debug logging works with multiple conditions."""
        import logging
        
        # Enable debug logging temporarily
        logger = logging.getLogger('app.services.search_parser')
        original_level = logger.level
        logger.setLevel(logging.DEBUG)
        
        try:
            query = self.parser.parse_search_query("item=log item!=package")
            # Should not crash with debug logging
            assert len(query['keywords']['item']) == 2
        finally:
            logger.setLevel(original_level)


class TestSearchParserOrAndOperators:
    """Test OR (||) and AND (&) operators within field values."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = SearchParser()
    
    def test_parse_or_operator(self):
        """Test parsing OR operator within field values."""
        result = self.parser.parse_search_query("item=plank||lumber||wood")
        
        expected = {
            'keywords': {
                'item': [('=', {'type': 'or', 'values': ['plank', 'lumber', 'wood']})]
            },
            'regular_terms': []
        }
        
        assert result == expected
    
    def test_parse_and_operator(self):
        """Test parsing AND operator within field values."""
        result = self.parser.parse_search_query("item=refined&ore")
        
        expected = {
            'keywords': {
                'item': [('=', {'type': 'and', 'values': ['refined', 'ore']})]
            },
            'regular_terms': []
        }
        
        assert result == expected
    
    def test_match_or_operator_success(self):
        """Test OR matching returns true when any value matches."""
        query = self.parser.parse_search_query("item=plank||lumber||wood")
        
        # Should match any of the OR values
        assert self.parser.match_row({'item': 'oak plank'}, query) == True
        assert self.parser.match_row({'item': 'maple lumber'}, query) == True
        assert self.parser.match_row({'item': 'birch wood'}, query) == True
        assert self.parser.match_row({'item': 'hardwood plank'}, query) == True
    
    def test_match_or_operator_failure(self):
        """Test OR matching returns false when no values match."""
        query = self.parser.parse_search_query("item=plank||lumber||wood")
        
        # Should not match non-matching values
        assert self.parser.match_row({'item': 'stone block'}, query) == False
        assert self.parser.match_row({'item': 'iron ore'}, query) == False
        assert self.parser.match_row({'item': 'clay pot'}, query) == False
    
    def test_match_and_operator_success(self):
        """Test AND matching returns true when all values match."""
        query = self.parser.parse_search_query("item=refined&ore")
        
        # Should match only when both terms are present
        assert self.parser.match_row({'item': 'refined iron ore'}, query) == True
        assert self.parser.match_row({'item': 'refined copper ore'}, query) == True
        assert self.parser.match_row({'item': 'high grade refined ore'}, query) == True
    
    def test_match_and_operator_failure(self):
        """Test AND matching returns false when not all values match."""
        query = self.parser.parse_search_query("item=refined&ore")
        
        # Should not match when only one term is present
        assert self.parser.match_row({'item': 'refined ingot'}, query) == False
        assert self.parser.match_row({'item': 'iron ore'}, query) == False
        assert self.parser.match_row({'item': 'raw copper'}, query) == False
        assert self.parser.match_row({'item': 'stone block'}, query) == False
    
    def test_numeric_or_operator(self):
        """Test OR operator with numeric values."""
        query = self.parser.parse_search_query("tier=1||3||5")
        
        # Should match any of the specified tiers
        assert self.parser.match_row({'tier': 1}, query) == True
        assert self.parser.match_row({'tier': 3}, query) == True
        assert self.parser.match_row({'tier': 5}, query) == True
        assert self.parser.match_row({'tier': 2}, query) == False
        assert self.parser.match_row({'tier': 4}, query) == False
    
    def test_mixed_or_and_operators(self):
        """Test combining OR and AND operators in different fields."""
        query = self.parser.parse_search_query("item=plank||lumber container=workshop&storage")
        
        # Test item OR logic
        test_row1 = {'item': 'oak plank', 'container': 'workshop storage chest'}
        assert self.parser.match_row(test_row1, query) == True
        
        test_row2 = {'item': 'maple lumber', 'container': 'workshop storage box'}
        assert self.parser.match_row(test_row2, query) == True
        
        # Should fail if container doesn't match AND condition
        test_row3 = {'item': 'oak plank', 'container': 'workshop'}
        assert self.parser.match_row(test_row3, query) == False
        
        # Should fail if item doesn't match OR condition
        test_row4 = {'item': 'stone block', 'container': 'workshop storage'}
        assert self.parser.match_row(test_row4, query) == False
    
    def test_or_and_with_other_operators(self):
        """Test OR/AND operators combined with other comparison operators."""
        # This should work: find items that are either plank or lumber AND tier > 2
        query = self.parser.parse_search_query("item=plank||lumber tier>2")
        
        test_row1 = {'item': 'oak plank', 'tier': 3}
        assert self.parser.match_row(test_row1, query) == True
        
        test_row2 = {'item': 'maple lumber', 'tier': 4}
        assert self.parser.match_row(test_row2, query) == True
        
        # Should fail if tier is too low
        test_row3 = {'item': 'oak plank', 'tier': 1}
        assert self.parser.match_row(test_row3, query) == False
    
    def test_container_or_operator(self):
        """Test OR operator with containers field."""
        query = self.parser.parse_search_query("container=workshop||carving")
        
        # Should match if item is in either container type
        test_row1 = {'containers': {'workshop chest': 5, 'storage': 2}}
        assert self.parser.match_row(test_row1, query) == True
        
        test_row2 = {'containers': {'carving table': 3, 'supply box': 1}}
        assert self.parser.match_row(test_row2, query) == True
        
        # Should not match if neither container type is present
        test_row3 = {'containers': {'storage chest': 5, 'supply box': 2}}
        assert self.parser.match_row(test_row3, query) == False
    
    def test_edge_cases_or_and(self):
        """Test edge cases for OR and AND operators."""
        # Empty values should be handled gracefully
        query1 = self.parser.parse_search_query("item=||lumber")
        # Should still work with one valid value
        assert 'item' in query1['keywords']
        
        # Single value with OR should work like normal
        query2 = self.parser.parse_search_query("item=plank||")
        assert 'item' in query2['keywords']
        
        # Whitespace should be handled
        query3 = self.parser.parse_search_query("item=plank || lumber || wood")
        test_row = {'item': 'oak plank'}
        assert self.parser.match_row(test_row, query3) == True