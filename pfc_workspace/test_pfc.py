import sys
print("=== PFC Python Environment Test ===")
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")

# Try to import itasca
try:
    import itasca
    print("✓ itasca module available!")
    print(f"itasca module location: {itasca.__file__}")
except ImportError as e:
    print(f"✗ itasca module not available: {e}")

# List available modules
print("\nAvailable modules:")
import pkgutil
for importer, modname, ispkg in pkgutil.iter_modules():
    if 'itasca' in modname.lower() or 'pfc' in modname.lower():
        print(f"  - {modname}")

print("\n=== Test Complete ===")
