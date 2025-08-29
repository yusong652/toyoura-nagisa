"""
Base content generator class.

Provides the abstract base class for all specialized content generators.
"""

from abc import ABC


class BaseContentGenerator(ABC):
    """
    Abstract base class for content generators.
    
    Provides common interface for specialized content generation utilities
    like title generation, image prompt generation, and web search.
    """
    
    def __init__(self, client, config=None):
        """
        Initialize content generator.
        
        Args:
            client: LLM client instance
            config: Optional configuration object
        """
        self.client = client
        self.config = config