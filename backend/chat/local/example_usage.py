"""
Example Usage - Distributed HPC LLM Inference

Simple examples showing how to use the distributed LLM framework.
"""

import asyncio
from backend.chat.llm_factory import get_client
from backend.chat.models import BaseMessage

async def example_basic_usage():
    """Basic distributed vLLM usage example."""
    
    print("🚀 Distributed vLLM Example")
    print("=" * 40)
    
    # Create distributed client through factory
    client = get_client(
        name="distributed-vllm",
        hpc_host="hpc.university.edu",
        ssh_user="your_username",
        model_path="/shared/models/llama-7b-chat",
        ssh_key_path="~/.ssh/id_rsa"
    )
    
    try:
        # Start distributed deployment
        print("📡 Starting HPC deployment...")
        success = await client.start_service()
        
        if not success:
            print("❌ Deployment failed")
            return
        
        print("✅ Deployment successful!")
        
        # Test inference
        messages = [
            BaseMessage(role="user", content="Hello! Can you explain quantum computing?")
        ]
        
        print("🤖 Generating response...")
        response = await client.generate(messages)
        
        print(f"💬 Response: {response.content}")
        print(f"📊 Tokens: {response.usage}")
        
    except Exception as e:
        print(f"💥 Error: {e}")
    
    finally:
        # Clean shutdown
        print("🛑 Shutting down...")
        await client.stop_service()

async def example_config_file():
    """Example using configuration file."""
    
    # This would read from deployment_config.yaml
    config = {
        "hpc_host": "hpc.university.edu",
        "ssh_user": "username",
        "model_path": "/shared/models/llama-7b",
        "ssh_key_path": "~/.ssh/id_rsa",
        "session_hours": 8
    }
    
    client = get_client(
        name="distributed-vllm",
        **config
    )
    
    # ... rest same as above

def main():
    """Main example runner."""
    
    print("🎯 HPC Distributed LLM Examples")
    print("=" * 50)
    print()
    print("Available examples:")
    print("1. Basic distributed vLLM")
    print("2. Configuration-based setup")
    print("3. Manual deployment scripts")
    print()
    
    print("🔧 For manual deployment:")
    print("1. Run: python hpc_deployment_template.py")
    print("2. Follow generated quickstart.sh instructions")
    print("3. Use distributed client to connect")
    print()
    
    # Run basic example
    asyncio.run(example_basic_usage())

if __name__ == "__main__":
    main()