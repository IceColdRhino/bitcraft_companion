"""
Simplified Claim model for essential claim data.
"""


class Claim:
    """
    Simplified claim representation containing only essential attributes.
    
    This class provides a lightweight container for claim information
    needed by the DataService. Complex inventory and building processing
    is now handled by processors.
    """

    def __init__(self, client=None, reference_data: dict = None):
        """
        Initialize a Claim instance with essential attributes.

        Args:
            client: Legacy parameter, kept for compatibility (unused)
            reference_data: Legacy parameter, kept for compatibility (unused)
        """
        # Essential claim attributes
        self.claim_name = None
        self.claim_id = None
        self.supplies = 0
        self.size = 0
        self.treasury = 0