#!/usr/bin/env python3
"""Demonstration of tool composition: glob + search_file_content working together.

This script showcases the atomic design principle where each tool has a focused
responsibility and they compose beautifully together for complex workflows.
"""

import sys
from pathlib import Path

# Add the backend directory to Python path for imports
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from nagisa_mcp.tools.coding.tools.glob import glob
from nagisa_mcp.tools.coding.tools.grep import grep

def demo_tool_composition():
    """Demonstrate powerful workflows using tool composition."""
    
    print("🚀 SOTA Tool Composition Demo: glob + grep")
    print("=" * 60)
    print()
    
    # Workflow 1: Find Python files, then analyze their imports
    print("📁 Workflow 1: Python Project Analysis")
    print("-" * 40)
    
    # Step 1: Use glob to discover Python files
    print("Step 1: Discovering Python files...")
    python_files = glob(
        pattern="**/*.py",
        path="backend",
        exclude=["**/test_*.py", "**/__pycache__/**"]
    )
    
    if python_files.get('status') == 'success':
        files_info = python_files['llm_content']['files']
        print(f"✅ Found {len(files_info)} Python files")
        
        # Step 2: Use grep to analyze imports
        print("\nStep 2: Analyzing import patterns...")
        import_analysis = grep(
            pattern=r"^(from|import)\s+.*",
            path="backend",
            include="*.py",
            max_matches=30
        )
        
        if import_analysis.get('status') == 'success':
            import_files = import_analysis['llm_content']['files']
            total_imports = import_analysis['llm_content']['summary']['total_matches']
            print(f"✅ Found {total_imports} import statements in {len(import_files)} files")
            
            # Analyze import diversity
            import_patterns = {}
            for file_data in import_files[:5]:  # Top 5 files
                print(f"\n  📄 {file_data['file_path']} ({file_data['match_count']} imports):")
                for match in file_data['matches'][:3]:  # Show top 3 imports per file
                    import_line = match['line_content'].strip()
                    print(f"    • {import_line}")
                    
                    # Extract import type
                    if import_line.startswith('from'):
                        import_patterns['from_imports'] = import_patterns.get('from_imports', 0) + 1
                    else:
                        import_patterns['direct_imports'] = import_patterns.get('direct_imports', 0) + 1
            
            print(f"\n📊 Import Statistics: {import_patterns}")
    
    print("\n" + "=" * 60)
    
    # Workflow 2: Security audit - find potential security issues
    print("\n🔒 Workflow 2: Security Audit")
    print("-" * 40)
    
    # Step 1: Find all code files
    print("Step 1: Discovering code files...")
    code_files = glob(
        pattern="**/*.{py,js,ts}",  # Note: This might not work as expected with our current glob
        path="backend",
    )
    
    # Step 2: Search for security-sensitive patterns
    print("Step 2: Scanning for security patterns...")
    security_patterns = [
        (r"password\s*=", "Hardcoded passwords"),
        (r"secret\s*=", "Hardcoded secrets"),
        (r"eval\s*\(", "Dangerous eval usage"),
        (r"exec\s*\(", "Dangerous exec usage"),
        (r"shell=True", "Shell injection risk"),
    ]
    
    total_security_issues = 0
    for pattern, description in security_patterns:
        print(f"\n  🔍 Checking: {description}")
        security_results = grep(
            pattern=pattern,
            path="backend",
            include="*.py",
            case_sensitive=False,
            max_matches=10
        )
        
        if security_results.get('status') == 'success':
            files = security_results['llm_content']['files']
            if files:
                issue_count = sum(f['match_count'] for f in files)
                total_security_issues += issue_count
                print(f"    ⚠️  Found {issue_count} potential issues in {len(files)} files")
                
                for file_data in files[:2]:  # Show top 2 files
                    for match in file_data['matches'][:1]:  # Show 1 match per file
                        print(f"      📍 {file_data['file_path']}:{match['line_number']}")
                        print(f"         {match['line_content']}")
            else:
                print(f"    ✅ No issues found")
    
    print(f"\n🔒 Security Summary: {total_security_issues} potential issues found")
    
    print("\n" + "=" * 60)
    
    # Workflow 3: Architecture analysis - find design patterns
    print("\n🏗️  Workflow 3: Architecture Analysis")
    print("-" * 40)
    
    # Find classes and their methods
    print("Step 1: Analyzing class structures...")
    class_analysis = grep(
        pattern=r"^class\s+(\w+)",
        path="backend",
        include="*.py",
        max_matches=20
    )
    
    if class_analysis.get('status') == 'success':
        class_files = class_analysis['llm_content']['files']
        total_classes = class_analysis['llm_content']['summary']['total_matches']
        print(f"✅ Found {total_classes} class definitions")
        
        # Find method definitions
        print("\nStep 2: Analyzing method patterns...")
        method_analysis = grep(
            pattern=r"^\s+def\s+(\w+)",
            path="backend", 
            include="*.py",
            max_matches=30
        )
        
        if method_analysis.get('status') == 'success':
            method_files = method_analysis['llm_content']['files']
            total_methods = method_analysis['llm_content']['summary']['total_matches']
            print(f"✅ Found {total_methods} method definitions")
            
            # Calculate average methods per file
            files_with_methods = len(method_files)
            avg_methods = total_methods / files_with_methods if files_with_methods > 0 else 0
            print(f"📊 Average methods per file: {avg_methods:.1f}")
    
    print("\n" + "=" * 60)
    print("\n🎯 Composition Benefits Demonstrated:")
    print("  ✅ Atomic Tools: Each tool has single responsibility")
    print("  ✅ Composability: Tools work together seamlessly")
    print("  ✅ Flexibility: Same tools, different workflows")
    print("  ✅ Performance: Right tool for each step")
    print("  ✅ Rich Metadata: Detailed insights for decision making")

if __name__ == "__main__":
    try:
        demo_tool_composition()
        print("\n✅ Tool composition demo completed successfully!")
    except Exception as e:
        print(f"❌ Error during demo: {e}")
        import traceback
        traceback.print_exc() 