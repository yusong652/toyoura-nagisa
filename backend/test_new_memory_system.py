#!/usr/bin/env python3
"""
Test script for the new memory injection architecture.

This script tests the SessionMemoryContextManager and its integration
with the system prompt mechanism.
"""

import asyncio
import sys
import os

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from backend.infrastructure.memory.session_memory_context import get_session_memory_manager
from backend.presentation.streaming.memory_injection_handler import get_system_prompt_with_memory_context
from backend.config import get_system_prompt


async def test_session_memory_manager():
    """Test the basic functionality of SessionMemoryContextManager."""
    print("=" * 60)
    print("Testing SessionMemoryContextManager")
    print("=" * 60)
    
    # Get the session memory manager
    manager = get_session_memory_manager()
    
    # Test session ID and user query
    test_session_id = "test_session_001"
    test_user_query = "What's the weather like today?"
    test_base_prompt = "You are aiNagisa, a helpful AI assistant."
    
    print(f"Session ID: {test_session_id}")
    print(f"User Query: {test_user_query}")
    print(f"Base Prompt: {test_base_prompt}")
    print()
    
    try:
        # Test getting enhanced system prompt
        print("Testing enhanced system prompt generation...")
        enhanced_prompt, metadata = await manager.get_enhanced_system_prompt(
            session_id=test_session_id,
            user_query=test_user_query,
            base_system_prompt=test_base_prompt
        )
        
        print(f"Enhanced System Prompt Length: {len(enhanced_prompt)} characters")
        print(f"Metadata: {metadata}")
        print()
        print("Enhanced System Prompt Preview:")
        print("-" * 40)
        print(enhanced_prompt[:300] + "..." if len(enhanced_prompt) > 300 else enhanced_prompt)
        print("-" * 40)
        print()
        
        # Test saving a conversation
        print("Testing conversation save...")
        await manager.save_conversation_turn(
            session_id=test_session_id,
            user_message=test_user_query,
            assistant_response="Based on current data, I cannot access real-time weather information.",
            user_id="test_user"
        )
        print("✅ Conversation saved successfully")
        print()
        
        # Test cached retrieval
        print("Testing cached memory retrieval...")
        cached_prompt, cached_metadata = await manager.get_enhanced_system_prompt(
            session_id=test_session_id,
            user_query=test_user_query,
            base_system_prompt=test_base_prompt
        )
        
        print(f"Cached: {cached_metadata.get('cached', False)}")
        print(f"Memory Count: {cached_metadata.get('memory_count', 0)}")
        print()
        
        # Test with different query
        print("Testing with different query...")
        different_query = "Tell me about artificial intelligence"
        fresh_prompt, fresh_metadata = await manager.get_enhanced_system_prompt(
            session_id=test_session_id,
            user_query=different_query,
            base_system_prompt=test_base_prompt
        )
        
        print(f"Different Query Cached: {fresh_metadata.get('cached', False)}")
        print(f"Different Query Memory Count: {fresh_metadata.get('memory_count', 0)}")
        
    except Exception as e:
        print(f"❌ Error testing SessionMemoryContextManager: {e}")
        import traceback
        traceback.print_exc()


async def test_memory_injection_handler():
    """Test the memory injection handler integration."""
    print("=" * 60)
    print("Testing Memory Injection Handler Integration")
    print("=" * 60)
    
    try:
        # Get base system prompt from config
        base_system_prompt = get_system_prompt(tools_enabled=True)
        
        # Test session
        test_session_id = "test_session_002"
        test_user_query = "How can I improve my productivity?"
        
        print(f"Base System Prompt Length: {len(base_system_prompt)} characters")
        print(f"Session ID: {test_session_id}")
        print(f"User Query: {test_user_query}")
        print()
        
        # Test the new memory injection handler
        print("Testing get_system_prompt_with_memory_context...")
        enhanced_prompt, status_updates = await get_system_prompt_with_memory_context(
            session_id=test_session_id,
            user_query=test_user_query,
            base_system_prompt=base_system_prompt,
            enable_memory=True
        )
        
        print(f"Enhanced Prompt Length: {len(enhanced_prompt)} characters")
        print(f"Status Updates Count: {len(status_updates)}")
        print()
        
        print("Status Updates:")
        for i, update in enumerate(status_updates):
            print(f"  {i+1}. {update.get('status', 'unknown')}: {update.get('details', {}).get('message', 'N/A')}")
        print()
        
        # Test with memory disabled
        print("Testing with memory disabled...")
        no_memory_prompt, no_memory_status = await get_system_prompt_with_memory_context(
            session_id=test_session_id,
            user_query=test_user_query,
            base_system_prompt=base_system_prompt,
            enable_memory=False
        )
        
        print(f"No Memory Prompt == Base Prompt: {no_memory_prompt == base_system_prompt}")
        print(f"No Memory Status Updates: {len(no_memory_status)}")
        
    except Exception as e:
        print(f"❌ Error testing memory injection handler: {e}")
        import traceback
        traceback.print_exc()


async def test_cache_behavior():
    """Test caching behavior and TTL."""
    print("=" * 60)
    print("Testing Cache Behavior")
    print("=" * 60)
    
    try:
        manager = get_session_memory_manager()
        
        test_session_id = "test_cache_session"
        test_query = "What is machine learning?"
        base_prompt = "You are a helpful assistant."
        
        # First call - should not be cached
        print("First call (should not be cached)...")
        prompt1, meta1 = await manager.get_enhanced_system_prompt(
            session_id=test_session_id,
            user_query=test_query,
            base_system_prompt=base_prompt
        )
        print(f"First call cached: {meta1.get('cached', False)}")
        
        # Second call with same query - should be cached
        print("Second call with same query (should be cached)...")
        prompt2, meta2 = await manager.get_enhanced_system_prompt(
            session_id=test_session_id,
            user_query=test_query,
            base_system_prompt=base_prompt
        )
        print(f"Second call cached: {meta2.get('cached', False)}")
        print(f"Prompts identical: {prompt1 == prompt2}")
        
        # Clear cache manually
        print("Clearing cache...")
        manager.clear_session_cache(test_session_id)
        
        # Third call - should not be cached after clearing
        print("Third call after cache clear (should not be cached)...")
        prompt3, meta3 = await manager.get_enhanced_system_prompt(
            session_id=test_session_id,
            user_query=test_query,
            base_system_prompt=base_prompt
        )
        print(f"Third call cached: {meta3.get('cached', False)}")
        
    except Exception as e:
        print(f"❌ Error testing cache behavior: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main test runner."""
    print("🧪 Testing New Memory Injection Architecture")
    print("=" * 60)
    print()
    
    # Run all tests
    await test_session_memory_manager()
    print()
    await test_memory_injection_handler()
    print()
    await test_cache_behavior()
    
    print("=" * 60)
    print("✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())