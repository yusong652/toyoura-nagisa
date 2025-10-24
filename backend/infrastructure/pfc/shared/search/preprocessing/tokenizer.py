"""Text tokenization for PFC search system.

This module provides tokenization functionality optimized for technical
documentation, handling special cases like hyphenated terms, numbers,
and technical abbreviations.
"""

import re
from typing import List, Set
from backend.infrastructure.pfc.shared.search.preprocessing.stopwords import is_stopword


class TextTokenizer:
    """Tokenizer for technical documentation text.

    Features:
    - Preserves technical terms and numbers
    - Handles hyphenated terms (e.g., "ball-ball" → ["ball", "ball"])
    - Handles underscored terms (e.g., "vel_x" → ["vel", "x"])
    - Removes stopwords while preserving technical vocabulary
    - Lowercases for consistent matching

    Design:
    - Regex-based for performance
    - No stemming (preserves exact technical terms)
    - No lemmatization (not needed for partial matching)
    - Splits on hyphens and underscores for flexible matching

    Usage:
        >>> tokenizer = TextTokenizer()
        >>> tokenizer.tokenize("Create ball with radius 1.5")
        ['create', 'ball', 'radius', '1.5']

        >>> tokenizer.tokenize("ball-ball contact model")
        ['ball', 'ball', 'contact', 'model']

        >>> tokenizer.tokenize("velocity vel_x component")
        ['velocity', 'vel', 'x', 'component']
    """

    # Regex pattern for word extraction
    # Matches: alphanumeric + hyphens + underscores + dots (for numbers)
    WORD_PATTERN = re.compile(r'\b[\w.-]+\b')

    # Minimum word length (avoid single-char noise)
    MIN_WORD_LENGTH = 2

    # Technical single-character tokens that should be preserved
    # These are common in scientific/engineering contexts
    TECHNICAL_SINGLE_CHARS = {'x', 'y', 'z', 'r', 'n', 't'}  # Coordinates, radius, normal, tangent

    def __init__(self, remove_stopwords: bool = True, min_length: int = 2):
        """Initialize tokenizer.

        Args:
            remove_stopwords: Whether to filter out stopwords
            min_length: Minimum word length to keep (default: 2)
        """
        self.remove_stopwords = remove_stopwords
        self.min_length = min_length

    def tokenize(self, text: str) -> List[str]:
        """Tokenize text into words.

        Args:
            text: Input text to tokenize

        Returns:
            List of tokens (lowercase, filtered)

        Example:
            >>> tokenizer = TextTokenizer()
            >>> tokenizer.tokenize("Distribute balls with overlaps")
            ['distribute', 'balls', 'overlaps']

            >>> tokenizer.tokenize("2D simulation with PFC")
            ['2d', 'simulation', 'pfc']

            >>> tokenizer.tokenize("ball-ball contact")
            ['ball', 'ball', 'contact']
        """
        if not text:
            return []

        # 1. Convert to lowercase
        text = text.lower()

        # 2. Extract words using regex
        words = self.WORD_PATTERN.findall(text)

        # 3. Process each word
        tokens = []
        for word in words:
            # Handle hyphenated terms (split and keep parts)
            # Context: technical compound terms like "ball-ball"
            if '-' in word:
                parts = word.split('-')
                for part in parts:
                    # In hyphenated context, preserve technical single chars
                    if self._is_valid_token(part, from_technical_context=True):
                        tokens.append(part)
            # Handle underscored terms (e.g., "vel_x", "set_pos", "end_1")
            # Split to improve matching: "vel_x" → ["vel", "x"]
            # Context: API naming conventions with direction/index suffixes
            elif '_' in word:
                parts = word.split('_')
                for part in parts:
                    # In underscore context, preserve technical single chars
                    if self._is_valid_token(part, from_technical_context=True):
                        tokens.append(part)
            else:
                if self._is_valid_token(word, from_technical_context=False):
                    tokens.append(word)

        return tokens

    def tokenize_to_set(self, text: str) -> Set[str]:
        """Tokenize text into a set of unique words.

        Useful for matching operations where duplicates don't matter.

        Args:
            text: Input text to tokenize

        Returns:
            Set of unique tokens

        Example:
            >>> tokenizer = TextTokenizer()
            >>> tokenizer.tokenize_to_set("ball ball contact")
            {'ball', 'contact'}
        """
        return set(self.tokenize(text))

    def _is_valid_token(self, word: str, from_technical_context: bool = False) -> bool:
        """Check if a word is a valid token.

        Args:
            word: Word to check
            from_technical_context: True if word comes from underscore/hyphen splitting
                                   (e.g., "x" from "vel_x", "1" from "end_1")

        Returns:
            True if word should be kept, False otherwise

        Filtering rules:
        1. Length >= min_length (except numbers and technical context)
        2. Not a stopword (unless it's a technical term)
        3. Contains at least one alphanumeric character

        Special handling for technical contexts:
        - Single-character technical tokens (x, y, z, r, n, t) preserved in underscore/hyphen context
        - Single-digit numbers always preserved
        """
        # Allow single-digit numbers (e.g., "1" from "end_1")
        if word.isdigit():
            return True

        # In technical context (from underscore/hyphen splitting),
        # preserve technical single characters
        if from_technical_context and len(word) == 1:
            if word.lower() in self.TECHNICAL_SINGLE_CHARS:
                return True

        # Must have minimum length for non-technical contexts
        if len(word) < self.min_length:
            return False

        # Must contain at least one alphanumeric character
        if not any(c.isalnum() for c in word):
            return False

        # Check stopwords (if enabled)
        if self.remove_stopwords and is_stopword(word):
            return False

        return True

    def extract_technical_terms(self, text: str) -> Set[str]:
        """Extract technical terms from text.

        Technical terms are identified as:
        - All-caps abbreviations (2-5 chars): PFC, DEM, FEM
        - CamelCase terms: BallBallContact, IterMechanical
        - Terms with numbers: 2D, 3D, C3D8

        Args:
            text: Input text

        Returns:
            Set of extracted technical terms (lowercased)

        Example:
            >>> tokenizer = TextTokenizer()
            >>> tokenizer.extract_technical_terms("Use PFC 2D for BallBallContact analysis")
            {'pfc', '2d', 'ballballcontact'}
        """
        terms = set()

        # 1. Extract all-caps abbreviations (2-5 chars)
        caps_pattern = re.compile(r'\b[A-Z]{2,5}\b')
        caps_terms = caps_pattern.findall(text)
        terms.update(t.lower() for t in caps_terms)

        # 2. Extract CamelCase terms
        camel_pattern = re.compile(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b')
        camel_terms = camel_pattern.findall(text)
        terms.update(t.lower() for t in camel_terms)

        # 3. Extract terms with numbers
        number_pattern = re.compile(r'\b(?:[A-Z]*\d+[A-Z]*|[A-Z]+\d+)\b', re.IGNORECASE)
        number_terms = number_pattern.findall(text)
        terms.update(t.lower() for t in number_terms)

        return terms

    @staticmethod
    def normalize_query(query: str) -> str:
        """Normalize query text for consistent processing.

        Args:
            query: User query string

        Returns:
            Normalized query (lowercase, whitespace normalized)

        Example:
            >>> TextTokenizer.normalize_query("  Create   Ball  ")
            'create ball'
        """
        # Remove extra whitespace and lowercase
        query = ' '.join(query.split())
        return query.lower()
