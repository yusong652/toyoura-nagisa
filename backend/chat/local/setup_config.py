#!/usr/bin/env python3
"""
HPC Configuration Setup Script

Helps set up the local configuration file safely with your HPC credentials.
"""

import os
import shutil
from pathlib import Path

def setup_config():
    """Set up configuration file from template."""
    
    current_dir = Path(__file__).parent
    template_file = current_dir / "config.example.py"
    config_file = current_dir / "config.py"
    
    print("🚀 HPC LLM Configuration Setup")
    print("=" * 50)
    
    # Check if config already exists
    if config_file.exists():
        print(f"⚠️  Configuration file already exists: {config_file}")
        choice = input("Do you want to overwrite it? (y/N): ").lower().strip()
        if choice not in ['y', 'yes']:
            print("❌ Setup cancelled.")
            return False
    
    # Check if template exists
    if not template_file.exists():
        print(f"❌ Template file not found: {template_file}")
        return False
    
    try:
        # Copy template to config
        shutil.copy2(template_file, config_file)
        print(f"✅ Configuration file created: {config_file}")
        
        # Show next steps
        print("\n📝 Next Steps:")
        print("=" * 30)
        print(f"1. Edit the file: {config_file}")
        print("2. Replace the following placeholders with your actual values:")
        print("   - YOUR_HPC_CLUSTER.edu → Your HPC hostname")
        print("   - YOUR_USERNAME → Your HPC username")
        print("   - YOUR_VLLM_MODEL → Path to your model on HPC")
        print("3. Set enabled=True to activate HPC mode")
        print("4. Test with: python config_example.py")
        
        print("\n🔒 Security Notes:")
        print("- This file is in .gitignore to protect your credentials")
        print("- Never commit SSH keys or passwords to version control")
        print("- Use SSH key authentication (not passwords)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating configuration file: {e}")
        return False

def check_git_ignore():
    """Check if config.py is properly ignored."""
    
    gitignore_path = Path(__file__).parent.parent.parent.parent / ".gitignore"
    
    if not gitignore_path.exists():
        print("⚠️  .gitignore file not found")
        return False
    
    try:
        with open(gitignore_path, 'r') as f:
            content = f.read()
        
        if "backend/chat/local/config.py" in content:
            print("✅ config.py is properly ignored by git")
            return True
        else:
            print("⚠️  config.py may not be ignored by git")
            print("   Please ensure 'backend/chat/local/config.py' is in .gitignore")
            return False
            
    except Exception as e:
        print(f"❌ Error checking .gitignore: {e}")
        return False

def test_configuration():
    """Test the current configuration."""
    
    try:
        from backend.chat.local.config import get_hpc_config, validate_local_config
        
        print("\n🧪 Testing Configuration")
        print("=" * 30)
        
        # Get HPC config
        hpc_config = get_hpc_config()
        
        print(f"HPC Enabled: {hpc_config.get('enabled')}")
        print(f"HPC Host: {hpc_config.get('host')}")
        print(f"Username: {hpc_config.get('username')}")
        print(f"SSH Key: {hpc_config.get('ssh_key_path')}")
        
        # Validate configuration
        validation = validate_local_config()
        
        print("\n📊 Validation Results:")
        for component, status in validation.items():
            status_icon = "✅" if status else "❌"
            print(f"  {status_icon} {component}: {'OK' if status else 'NEEDS CONFIGURATION'}")
        
        # Check for placeholder values
        if hpc_config.get('host') == 'YOUR_HPC_CLUSTER.edu':
            print("\n⚠️  Warning: HPC host still contains placeholder value")
            print("   Please update 'host' in config.py")
        
        if hpc_config.get('username') == 'YOUR_USERNAME':
            print("\n⚠️  Warning: Username still contains placeholder value")
            print("   Please update 'username' in config.py")
        
        return all(validation.values())
        
    except ImportError as e:
        print(f"❌ Configuration file not found or invalid: {e}")
        print("   Please run setup first: python setup_config.py")
        return False
    except Exception as e:
        print(f"❌ Error testing configuration: {e}")
        return False

def show_usage_example():
    """Show usage example."""
    
    print("\n📖 Usage Example:")
    print("=" * 20)
    print("""
# After configuration, use distributed client:
from backend.chat.llm_factory import get_client

# Create distributed vLLM client (reads from config.py)
client = get_client("distributed-vllm")

# Start HPC connection
await client.start_service()

# Generate response
messages = [{"role": "user", "content": "Hello!"}]
response = await client.generate(messages)

print(response.content)

# Clean shutdown
await client.stop_service()
""")

def main():
    """Main setup function."""
    
    print("🔧 HPC LLM Configuration Manager")
    print("=" * 40)
    
    while True:
        print("\nOptions:")
        print("1. Setup new configuration")
        print("2. Test current configuration") 
        print("3. Check git ignore status")
        print("4. Show usage example")
        print("5. Exit")
        
        choice = input("\nSelect option (1-5): ").strip()
        
        if choice == "1":
            setup_config()
        elif choice == "2":
            test_configuration()
        elif choice == "3":
            check_git_ignore()
        elif choice == "4":
            show_usage_example()
        elif choice == "5":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid option. Please choose 1-5.")

if __name__ == "__main__":
    main()