# Replace Tool - SOTA Design Documentation

## Overview

The `replace` tool provides **atomic file editing functionality** with precise text replacement capabilities. Designed as a direct equivalent to gemini-cli's replace tool, it maintains full compatibility while adding enterprise-grade security, validation, and error handling.

## Core Design Principles

### 1. **Atomic Functionality**
- **Single Responsibility**: Replace specific text content within files
- **No Overlap**: Does NOT list files (use `glob`) or read entire contents (use `read_file`)
- **Precise Targeting**: Requires exact string matching with context validation

### 2. **gemini-cli Compatibility**
- **Tool Name**: `replace` (matches gemini-cli exactly)
- **Parameter Names**: `file_path`, `old_string`, `new_string`, `expected_replacements`
- **Behavior**: Identical error handling and validation logic
- **Return Structure**: Compatible JSON response format

### 3. **SOTA Security Model**
- **Workspace Boundaries**: All operations confined to workspace directory
- **Path Validation**: Absolute paths required, relative paths rejected for clarity
- **Symlink Safety**: Comprehensive symlink attack prevention
- **Size Limits**: Protection against resource exhaustion attacks

## Architecture

### Core Components

```python
replace(
    file_path: str,           # Absolute path within workspace
    old_string: str,          # Exact text to replace (with context)
    new_string: str,          # Replacement text
    expected_replacements: int = 1  # Expected occurrence count
) -> Dict[str, Any]
```

### Key Features

#### 1. **Precise Text Matching**
- Requires **exact literal matching** including whitespace and indentation
- Context validation: single replacements need 3+ lines before/after target
- Multiple replacement support with occurrence count validation

#### 2. **File Creation Capability**
- New file creation when `old_string=""` and file doesn't exist
- Automatic parent directory creation
- Proper file encoding handling (UTF-8 default)

#### 3. **Intelligent Error Handling**
```python
# Error scenarios with specific messages:
- File not found → "Use empty old_string to create new file"
- String not found → "Ensure exact match including whitespace"
- Wrong count → "Expected X occurrences but found Y"
- Invalid path → "file_path must be absolute"
- Outside workspace → "File path is outside workspace"
```

#### 4. **Rich Metadata Response**
```json
{
  "edit_result": {
    "file_path": "/workspace/src/main.py",
    "replacements_made": 1,
    "is_new_file": false,
    "file_size_bytes": 1024,
    "diff_preview": "--- original\n+++ modified\n..."
  },
  "operation_info": {
    "old_string_length": 156,
    "new_string_length": 168,
    "expected_replacements": 1,
    "validation_warnings": []
  }
}
```

## Security Architecture

### 1. **Path Security**
- **`validate_path_in_workspace()`**: Ensures all paths stay within workspace
- **Absolute Path Requirement**: Prevents ambiguity in path interpretation
- **Symlink Protection**: `is_safe_symlink()` and `check_parent_symlinks()`

### 2. **File Validation**
- **Size Limits**: 5MB max file size for editing operations
- **Binary Detection**: Prevents editing binary files as text
- **Encoding Safety**: UTF-8 with error replacement for malformed content

### 3. **Input Validation**
- **String Length Limits**: 50KB max for old_string and new_string
- **Occurrence Limits**: Max 1000 replacements per operation
- **Parameter Sanitization**: Pydantic FieldInfo handling for programmatic calls

## Performance Optimizations

### 1. **Efficient Processing**
- **Single Pass Replacement**: `string.replace()` for optimal performance
- **Lazy Diff Generation**: Only generate diff when needed for display
- **Memory Conscious**: Stream processing for large files within limits

### 2. **Resource Protection**
- **File Size Limits**: Prevent memory exhaustion
- **Operation Timeouts**: Implicit through file size constraints
- **Context Validation**: Early rejection of malformed requests

## Error Handling Strategy

### 1. **Comprehensive Validation**
```python
# Parameter validation chain:
1. Required field validation
2. Path format validation (absolute requirement)
3. Workspace boundary validation  
4. File existence and editability validation
5. Content matching and occurrence validation
6. Context requirement validation (for single replacements)
```

### 2. **User-Friendly Messages**
- **Actionable Errors**: Each error includes guidance for resolution
- **Context Preservation**: Maintain enough information for debugging
- **Consistent Format**: ToolResult model for uniform response structure

## Integration Patterns

### 1. **Tool Composition Workflow**
```python
# Recommended usage pattern:
1. glob("**/*.py")              # Discover files
2. read_file("/path/to/file")   # Examine content  
3. replace(                     # Edit content
     file_path="/path/to/file",
     old_string="exact_context_block",
     new_string="replacement_block"
   )
```

### 2. **FastMCP Registration**
```python
def register_replace_tool(mcp: FastMCP):
    """Register with coding category and filesystem tags."""
    common = dict(
        tags={"filesystem", "coding", "edit"}, 
        annotations={"category": "coding"}
    )
    mcp.tool(**common)(replace)
```

## Best Practices

### 1. **For LLM Usage**
- **Always read file first**: Use `read_file` to examine current content
- **Include sufficient context**: 3+ lines before/after target for single replacements
- **Copy-paste exact text**: Don't retype content to avoid whitespace errors
- **Use absolute paths**: Prevent path ambiguity issues

### 2. **For Error Prevention**
- **Match whitespace exactly**: Include all spaces, tabs, and newlines
- **Verify occurrence count**: Set `expected_replacements` to actual count
- **Handle edge cases**: Empty files, end-of-file positions, special characters

### 3. **For Security**
- **Validate all inputs**: Never trust user-supplied paths
- **Check file types**: Prevent binary file corruption
- **Monitor file sizes**: Protect against resource exhaustion

## Testing Strategy

### 1. **Comprehensive Test Coverage**
- **File Creation**: New file with empty old_string
- **Single Replacement**: Context validation and exact matching
- **Multiple Replacements**: Occurrence count validation  
- **Error Scenarios**: All failure modes with specific messages
- **Security Tests**: Path validation and boundary checking

### 2. **Real-World Scenarios**
- **Code Refactoring**: Function name changes with context
- **Configuration Updates**: Multiple value replacements
- **Documentation Edits**: Content with formatting preservation

## Future Enhancements

### 1. **Potential Improvements**
- **Regex Support**: Pattern-based replacements (maintain exact-match as default)
- **Backup Creation**: Automatic file backup before edits
- **Undo Capability**: Operation reversal for safety
- **Batch Operations**: Multiple replacements in single call

### 2. **Performance Optimizations**
- **Streaming Processing**: Handle larger files incrementally
- **Parallel Processing**: Concurrent file operations where safe
- **Caching Strategy**: Optimize repeated operations on same files

## Conclusion

The replace tool represents a **state-of-the-art implementation** that balances:

- **Functionality**: Complete feature parity with gemini-cli
- **Security**: Enterprise-grade safety and validation
- **Usability**: Clear error messages and rich metadata
- **Performance**: Optimized for common use cases
- **Reliability**: Comprehensive error handling and edge case coverage

This design ensures the tool can serve as a **production-ready foundation** for file editing operations while maintaining the atomic design principles essential for tool composition and system reliability. 