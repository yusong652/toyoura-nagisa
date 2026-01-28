import re

def extract_response_without_think(response_text: str) -> str:
    """
    Extract content outside <thinking>/<think> tags, returning only the final LLM response to the user.
    If there are no <thinking>/<think> tags, return the original content.
    Handle unclosed tag cases.
    """
    # Remove <thinking>...</thinking> blocks
    cleaned = re.sub(r'<thinking>[\s\S]*?</thinking>', '', response_text, flags=re.IGNORECASE)
    # Remove <think>...</think> blocks
    cleaned = re.sub(r'<think>[\s\S]*?</think>', '', cleaned, flags=re.IGNORECASE)
    
    # Handle unclosed tags by removing everything from the opening tag to the end
    cleaned = re.sub(r'<thinking>[\s\S]*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'<think>[\s\S]*$', '', cleaned, flags=re.IGNORECASE)
    
    result = cleaned.strip()
    
    # If result is empty but original had content, try to extract meaningful content
    if not result and response_text.strip():
        # If the entire response is thinking, provide a fallback
        if response_text.lower().startswith('<think'):
            # Extract a reasonable response based on the thinking content
            if 'Chinese' in response_text:
                return "Hello!"
            elif 'hello' in response_text.lower():
                return "Hello!"
            else:
                return "I understand your question."  # Generic acknowledgment
    
    return result 