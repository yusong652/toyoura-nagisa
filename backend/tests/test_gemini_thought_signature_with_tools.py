"""
Test Gemini thought_signature field with project's tool schemas

This test uses the actual aiNagisa GeminiClient with real tool schemas
to verify if thought_signature appears in responses.

Based on research:
- thought_signature is necessary for thinking to work with function calling
- It may appear in responses when using tools with thinking mode

Model: gemini-2.5-flash-preview-09-2025
Date: 2025-10-29
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from infrastructure.llm.providers.gemini.client import GeminiClient
from infrastructure.llm.providers.gemini.config import get_gemini_client_config
from config.llm import get_llm_settings
from google.genai import types


async def test_thought_signature_with_project_tools():
    """Test thought_signature using project's real tool schemas"""

    print("=" * 80)
    print("TEST: Thought Signature with aiNagisa Tool Schemas")
    print("=" * 80)
    print()

    # Initialize project's Gemini client
    llm_settings = get_llm_settings()
    gemini_config = llm_settings.get_gemini_config()
    api_key = gemini_config.google_api_key

    # Create client with project configuration
    client = GeminiClient(
        api_key=api_key
    )

    # Test session ID
    session_id = "test_thought_signature_session"

    print("Preparing context with tool schemas...")
    print("-" * 80)

    # Get tool schemas directly from tool manager
    tool_schemas = await client.tool_manager.get_function_call_schemas(session_id, "coding")

    # Get complete context with tool schemas
    try:
        context_contents, api_config = await client._prepare_complete_context(session_id)
    except:
        # If context doesn't exist, create minimal context
        context_contents = []

        # Build config with tools
        from backend.shared.utils.prompt.builder import build_system_prompt
        system_prompt = await build_system_prompt(
            agent_profile="coding",
            session_id=session_id,
            enable_memory=False,
            tool_schemas=await client.tool_manager.get_schemas_for_system_prompt(session_id, "coding")
        )

        config_kwargs = client.gemini_config.get_generation_config_kwargs(
            system_prompt=system_prompt or "",
            tool_schemas=tool_schemas
        )
        api_config = {'config': types.GenerateContentConfig(**config_kwargs)}

    print(f"Context items: {len(context_contents)}")
    print(f"API config keys: {list(api_config.keys())}")

    # Check tool schemas in config
    config = api_config['config']
    if config.tools:
        print(f"✓ Tools loaded: {len(config.tools)} tool groups")
        total_functions = sum(len(tool.function_declarations) for tool in config.tools)
        print(f"  Total functions: {total_functions}")
        print(f"  Sample functions:")
        for tool_group in config.tools[:2]:  # First 2 groups
            for func in tool_group.function_declarations[:3]:  # First 3 functions
                print(f"    - {func.name}")
    else:
        print("✗ No tools loaded")

    print()
    print("Testing with a prompt that might trigger tool usage...")
    print("-" * 80)

    # Add a user message that might trigger tool usage
    user_prompt = "Search for 'Python asyncio best practices' and write the results to a file called asyncio_tips.md"
    context_contents.append({
        "role": "user",
        "parts": [{"text": user_prompt}]
    })

    # Now call the streaming API
    from google import genai
    raw_client = genai.Client(api_key=api_key)

    stream_generator = raw_client.aio.models.generate_content_stream(
        model=client.gemini_config.model_settings.model,
        contents=context_contents,
        config=api_config['config']
    )

    print("Streaming response with tool schemas enabled...")
    print("-" * 80)
    print()

    chunk_count = 0
    has_signature = False
    has_function_call = False
    signature_details = []

    async for chunk in await stream_generator:
        chunk_count += 1

        if not chunk.candidates[0].content.parts:
            print(f"\nChunk #{chunk_count}: NO PARTS (final chunk)")
            print(f"  finish_reason: {chunk.candidates[0].finish_reason}")
            continue

        for part_idx, part in enumerate(chunk.candidates[0].content.parts):
            print(f"\n{'='*80}")
            print(f"Chunk #{chunk_count}, Part #{part_idx}")
            print(f"{'='*80}")

            # Print all available fields
            print(f"  thought: {part.thought}")
            print(f"  text: {part.text[:100] if part.text else None}...")
            print(f"  thought_signature: {part.thought_signature}")
            print(f"  function_call: {part.function_call}")
            print(f"  function_response: {part.function_response}")

            # Check for thought_signature
            if part.thought_signature:
                has_signature = True
                sig_info = {
                    "chunk": chunk_count,
                    "part": part_idx,
                    "length": len(part.thought_signature),
                    "preview": part.thought_signature[:50] if len(part.thought_signature) > 50 else part.thought_signature,
                    "has_function_call": bool(part.function_call),
                    "is_thinking": bool(part.thought)
                }
                signature_details.append(sig_info)
                print(f"\n  ✓✓✓ THOUGHT SIGNATURE FOUND ✓✓✓")
                print(f"  Length: {sig_info['length']} bytes")
                print(f"  Preview: {sig_info['preview']}")
                print(f"  Has function call: {sig_info['has_function_call']}")
                print(f"  Is thinking: {sig_info['is_thinking']}")

            # Check for function_call
            if part.function_call:
                has_function_call = True
                print(f"\n  ✓✓✓ FUNCTION CALL FOUND ✓✓✓")
                print(f"  Function name: {part.function_call.name}")
                print(f"  Function args: {dict(part.function_call.args)}")

            # Print model_fields_set (what fields are actually populated)
            print(f"\n  model_fields_set: {part.model_fields_set}")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print(f"Total chunks: {chunk_count}")
    print(f"Thought signature found: {'✓ YES' if has_signature else '✗ NO'}")
    print(f"Function calls found: {'✓ YES' if has_function_call else '✗ NO'}")
    print()

    if signature_details:
        print("Signature details:")
        print("-" * 80)
        for i, sig in enumerate(signature_details):
            print(f"  Signature #{i+1}:")
            print(f"    Location: Chunk {sig['chunk']}, Part {sig['part']}")
            print(f"    Length: {sig['length']} bytes")
            print(f"    Has function call: {sig['has_function_call']}")
            print(f"    Is thinking: {sig['is_thinking']}")
        print()

    return {
        "has_signature": has_signature,
        "has_function_call": has_function_call,
        "signature_count": len(signature_details),
        "signature_details": signature_details,
        "total_chunks": chunk_count
    }


async def test_simple_response_structure():
    """Test response structure for simple query to compare"""

    print("\n" + "=" * 80)
    print("TEST: Simple Response Structure (No Tool Call Expected)")
    print("=" * 80)
    print()

    llm_settings = get_llm_settings()
    gemini_config = llm_settings.get_gemini_config()
    api_key = gemini_config.google_api_key

    client = GeminiClient(
        api_key=api_key
    )

    session_id = "test_simple_session"

    # Get tool schemas
    tool_schemas = await client.tool_manager.get_function_call_schemas(session_id, "general")

    # Build simple context
    from backend.shared.utils.prompt.builder import build_system_prompt
    system_prompt = await build_system_prompt(
        agent_profile="general",
        session_id=session_id,
        enable_memory=False,
        tool_schemas=await client.tool_manager.get_schemas_for_system_prompt(session_id, "general")
    )

    config_kwargs = client.gemini_config.get_generation_config_kwargs(
        system_prompt=system_prompt or "",
        tool_schemas=tool_schemas
    )
    api_config = {'config': types.GenerateContentConfig(**config_kwargs)}

    # Add simple question
    context_contents = [{
        "role": "user",
        "parts": [{"text": "What is 7 * 8?"}]
    }]

    # Stream response
    from google import genai
    raw_client = genai.Client(api_key=api_key)

    stream_generator = raw_client.aio.models.generate_content_stream(
        model=client.gemini_config.model_settings.model,
        contents=context_contents,
        config=api_config['config']
    )

    print("Streaming simple response...")
    print("-" * 80)
    print()

    has_signature = False
    parts_with_fields = []

    async for chunk in await stream_generator:
        if not chunk.candidates[0].content.parts:
            continue

        for part in chunk.candidates[0].content.parts:
            fields_set = part.model_fields_set
            parts_with_fields.append({
                "fields_set": fields_set,
                "has_signature": bool(part.thought_signature),
                "is_thinking": bool(part.thought)
            })

            if part.thought_signature:
                has_signature = True
                print(f"✓ Signature found in simple response!")
                print(f"  Length: {len(part.thought_signature)} bytes")

    print("Part fields analysis:")
    print("-" * 80)
    for i, part_info in enumerate(parts_with_fields):
        print(f"Part {i}: fields_set={part_info['fields_set']}")
        print(f"  Has signature: {part_info['has_signature']}")
        print(f"  Is thinking: {part_info['is_thinking']}")

    print()
    print(f"Result: {'✓ Found signature' if has_signature else '✗ No signature'}")

    return {
        "has_signature": has_signature,
        "parts_count": len(parts_with_fields),
        "parts_details": parts_with_fields
    }


async def main():
    """Run all tests"""

    print("Starting Gemini Thought Signature Tests with aiNagisa Tools")
    print("=" * 80)
    print()

    # Test 1: With project tools
    result1 = await test_thought_signature_with_project_tools()

    # Test 2: Simple query for comparison
    result2 = await test_simple_response_structure()

    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    print()

    print("Test 1 (With tool schemas):")
    print(f"  Thought signature found: {'✓ YES' if result1['has_signature'] else '✗ NO'}")
    print(f"  Function calls found: {'✓ YES' if result1['has_function_call'] else '✗ NO'}")
    print(f"  Signature count: {result1['signature_count']}")
    print()

    print("Test 2 (Simple query):")
    print(f"  Thought signature found: {'✓ YES' if result2['has_signature'] else '✗ NO'}")
    print(f"  Parts analyzed: {result2['parts_count']}")
    print()

    print("=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print()

    if result1['has_signature'] or result2['has_signature']:
        print("✓ THOUGHT_SIGNATURE IS PRESENT IN RESPONSES")
        print()
        print("Implications for context assembly:")
        print("  1. We SHOULD preserve thought_signature in context")
        print("  2. Complete part structure needed:")
        print("     - text")
        print("     - thought (bool)")
        print("     - thought_signature (bytes, if present)")
        print("     - function_call (if present)")
        print()
        print("Recommended context format:")
        print('  {"role": "model", "parts": [')
        print('    {')
        print('      "text": "...",')
        print('      "thought": true/false,')
        print('      "thought_signature": <bytes>,  # if present')
        print('      "function_call": {...}  # if present')
        print('    },')
        print('    ...')
        print('  ]}')
    else:
        print("✗ THOUGHT_SIGNATURE NOT FOUND")
        print()
        print("Possible reasons:")
        print("  1. Model doesn't generate signatures with current config")
        print("  2. Requires specific thinking budget or mode")
        print("  3. Only appears in certain scenarios (extended thinking, etc.)")
        print()
        print("Current text-only approach may be sufficient.")

    return {
        "test1": result1,
        "test2": result2
    }


if __name__ == "__main__":
    asyncio.run(main())
