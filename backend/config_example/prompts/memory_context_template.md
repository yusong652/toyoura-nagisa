# Memory Context Integration Template

This template is used to enhance system prompts with relevant context from previous conversations.

## Template Structure

The memory context is integrated into the system prompt with clear separation:

1. **Base System Prompt** - The original system prompt comes first
2. **Relevant Context** - Memory context is inserted with clear headers
3. **Instructions** - Guidelines for using the memory context

---

## Relevant Context from Previous Conversations

{memory_context}

## Instructions

Use the above context to provide more personalized and contextually aware responses. Reference specific information from previous conversations when relevant, but don't explicitly mention that you're using memory unless asked.