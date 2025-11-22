"""
Token estimation utilities.

Provides utilities for estimating token counts for various text inputs.
"""


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text using simple character-based approximation.
    
    This is a simple estimation based on average character-to-token ratios.
    For production use with specific models, consider using proper tokenizers
    like tiktoken for OpenAI models or model-specific tokenizers.
    
    Args:
        text: Text to estimate token count for
        
    Returns:
        int: Estimated token count
        
    Note:
        This estimation assumes ~4 characters per token, which is roughly
        accurate for English text with most modern tokenizers.
    """
    if not text:
        return 0
    
    # Simple estimation: ~4 characters per token
    # This works reasonably well for English text across most tokenizers
    return len(text) // 4


def estimate_tokens_precise(text: str, model_type: str = "gpt") -> int:
    """
    More precise token estimation based on model type.
    
    Args:
        text: Text to estimate
        model_type: Model type ("gpt", "claude", "gemini", etc.)
        
    Returns:
        int: Estimated token count
        
    Note:
        Currently uses the same simple estimation. Can be extended
        to use model-specific tokenizers when available.
    """
    # For now, use the same simple estimation
    # TODO: Implement model-specific tokenization when needed
    return estimate_tokens(text)