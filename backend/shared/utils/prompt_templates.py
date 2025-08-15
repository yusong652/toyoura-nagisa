"""
Prompt template utilities.

Provides utilities for loading and processing prompt templates from markdown files.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional


def get_prompts_directory() -> Path:
    """
    Get the path to the prompts directory.
    
    Returns:
        Path: Path to the prompts directory
    """
    # Get the backend directory (parent of shared)
    backend_dir = Path(__file__).parent.parent.parent
    return backend_dir / "config" / "prompts"


def load_prompt_template(template_name: str) -> str:
    """
    Load a prompt template from the prompts directory.
    
    Args:
        template_name: Name of the template file (without .md extension)
        
    Returns:
        str: Template content
        
    Raises:
        FileNotFoundError: If template file doesn't exist
        IOError: If template file can't be read
    """
    prompts_dir = get_prompts_directory()
    template_path = prompts_dir / f"{template_name}.md"
    
    if not template_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {template_path}")
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    except IOError as e:
        raise IOError(f"Failed to read prompt template {template_path}: {e}")


def format_memory_context_prompt(base_prompt: str, memory_context: str) -> str:
    """
    Format the memory context prompt using the template.
    
    Args:
        base_prompt: Base system prompt
        memory_context: Formatted memory context
        
    Returns:
        str: Enhanced prompt with memory context
    """
    if not memory_context or not memory_context.strip():
        return base_prompt
    
    # Load the memory context template
    try:
        template = load_prompt_template("memory_context_template")
        
        # Extract the context integration part (after the template documentation)
        # Look for the "## Relevant Context" section
        lines = template.split('\n')
        integration_start = None
        
        for i, line in enumerate(lines):
            if line.startswith("## Relevant Context from Previous Conversations"):
                integration_start = i
                break
        
        if integration_start is None:
            # Fallback to simple format if template structure is unexpected
            return f"""{base_prompt}

## Relevant Context from Previous Conversations

{memory_context}

## Instructions

Use the above context to provide more personalized and contextually aware responses. Reference specific information from previous conversations when relevant, but don't explicitly mention that you're using memory unless asked."""
        
        # Extract the integration part of the template
        integration_lines = lines[integration_start:]
        integration_template = '\n'.join(integration_lines)
        
        # Format with the memory context
        formatted_integration = integration_template.format(memory_context=memory_context)
        
        # Combine with base prompt
        return f"{base_prompt}\n\n{formatted_integration}"
        
    except (FileNotFoundError, IOError) as e:
        # Fallback to hardcoded template if file can't be loaded
        return f"""{base_prompt}

## Relevant Context from Previous Conversations

{memory_context}

## Instructions

Use the above context to provide more personalized and contextually aware responses. Reference specific information from previous conversations when relevant, but don't explicitly mention that you're using memory unless asked."""