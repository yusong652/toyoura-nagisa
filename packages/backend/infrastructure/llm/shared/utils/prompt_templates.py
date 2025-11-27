"""
Prompt template utilities shared across LLM providers.

Common prompt template processing and context formatting functions.
"""

from typing import Dict, Any, List, Optional
from backend.domain.models.messages import BaseMessage
from .text_processing import extract_text_content


def apply_template_variables(template: str, variables: Dict[str, Any]) -> str:
    """
    Apply template variables to a prompt template.
    
    Args:
        template: Template string with {variable} placeholders
        variables: Dictionary of variable values
        
    Returns:
        Template with variables substituted
    """
    try:
        return template.format(**variables)
    except KeyError as e:
        print(f"[WARNING] Missing template variable: {e}")
        return template
    except Exception as e:
        print(f"[ERROR] Template processing failed: {e}")
        return template


def format_conversation_context(
    messages: List[BaseMessage], 
    context_prefix: str = "Recent conversation:\n",
    max_messages: Optional[int] = None
) -> str:
    """
    Format conversation messages into a readable context string.
    
    Args:
        messages: List of BaseMessage objects
        context_prefix: Prefix text for the context
        max_messages: Maximum number of messages to include
        
    Returns:
        Formatted conversation context string
    """
    if not messages:
        return ""
    
    # Limit messages if specified
    if max_messages and len(messages) > max_messages:
        messages = messages[-max_messages:]
    
    context_parts = [context_prefix]
    
    for msg in messages:
        if msg is not None:
            # Extract text content properly
            text_content = extract_text_content(msg.content)
            context_parts.append(f"{msg.role}: {text_content}")
    
    return "\n".join(context_parts)


def build_few_shot_context(
    examples: List[Dict[str, Any]], 
    max_examples: Optional[int] = None
) -> str:
    """
    Build few-shot learning context from examples.
    
    Args:
        examples: List of example dictionaries with 'input' and 'output' keys
        max_examples: Maximum number of examples to include
        
    Returns:
        Formatted few-shot context string
    """
    if not examples:
        return ""
    
    # Limit examples if specified
    if max_examples and len(examples) > max_examples:
        examples = examples[-max_examples:]
    
    context_parts = []
    for i, example in enumerate(examples, 1):
        input_text = example.get('input', '')
        output_text = example.get('output', '')
        
        context_parts.append(f"Example {i}:")
        context_parts.append(f"Input: {input_text}")
        context_parts.append(f"Output: {output_text}")
        context_parts.append("")  # Empty line between examples
    
    return "\n".join(context_parts)


def extract_template_variables(template: str) -> List[str]:
    """
    Extract variable names from a template string.
    
    Args:
        template: Template string with {variable} placeholders
        
    Returns:
        List of variable names found in the template
    """
    import re
    
    # Find all {variable} patterns
    matches = re.findall(r'\{([^}]+)\}', template)
    return list(set(matches))  # Remove duplicates