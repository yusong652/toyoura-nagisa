# PFC Documentation Target Structure

## Command Categories to Document

### High Priority (Core Simulation)
- `ball` - Ball object commands (generate, delete, attribute, property)
- `wall` - Wall object commands (create, generate, delete)
- `contact` - Contact commands and contact models (linear, hertz, etc.)
- `model` - Model control (solve, cycle, configure, domain)
- `measure` - Measurement utilities

### Medium Priority (Configuration)
- `set` - System settings
- `group` - Grouping operations
- `range` - Range specifications
- `history` - History tracking

### Lower Priority (Advanced)
- `clump` - Clump operations
- `fragment` - Fragment operations
- `dfn` - Discrete Fracture Network

## URL Patterns

### Command Documentation
```
https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/{category}/commands/cmd_{category}.{subcommand}.html

Examples:
- ball generate: .../manual/ball/commands/cmd_ball.generate.html
- contact model linear: .../manual/contact_models/cmd_contact.model.linear.html
- model solve: .../manual/model/commands/cmd_model.solve.html
```

### Python SDK Documentation
```
https://docs.itascacg.com/pfc700/pfc/docproject/source/python/{module}.html

Examples:
- itasca.ball: .../python/itasca.ball.html
- itasca.wall: .../python/itasca.wall.html
- itasca.contact: .../python/itasca.contact.html
```

## Current Coverage Status

### command_docs/
Check `command_docs/index.json` for current coverage. Key gaps:
- Most command categories have basic structure but incomplete keyword details
- Examples need expansion
- Python SDK cross-references need completion

### python_sdk_docs/
Check `python_sdk_docs/index.json` for current coverage. Key gaps:
- Module-level documentation exists but method details sparse
- Return types and parameter specifications incomplete
- Usage examples needed

## Extraction Guidelines

When fetching from official docs:

1. **Syntax**: Extract the exact command syntax with all optional parameters
2. **Parameters**: Document each keyword with type, default, and description
3. **Examples**: Include at least 2 practical examples per command
4. **Notes**: Capture important caveats or limitations
5. **Cross-refs**: Note which Python API achieves similar results
