---
name: pfc-doc-curator
description: Curate and enhance PFC (Particle Flow Code) documentation for standalone pfc-mcp. Use when working with PFC command docs, Python SDK docs, or when user mentions updating/adding/improving PFC documentation in pfc-mcp/src/pfc_mcp/docs/resources/.
---

# PFC Documentation Curator

## Purpose

Help curate and enhance PFC documentation by fetching from official ITASCA sources and organizing into the toyoura-nagisa project structure.

## Official Documentation Sources

- **PFC 7.0 Manual**: https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/pfchome.html
- **Command Reference**: https://docs.itascacg.com/pfc700/pfc/docproject/source/manual/commands.html
- **Python API Reference**: https://docs.itascacg.com/pfc700/pfc/docproject/source/python/python.html

## Project Documentation Structure

See [STRUCTURE.md](STRUCTURE.md) for the full target structure.

### Quick Reference

```
pfc-mcp/src/pfc_mcp/docs/resources/
├── command_docs/           # PFC command documentation
│   ├── index.json          # Master command index
│   ├── commands/           # Individual command docs
│   └── STRUCTURE_DESIGN.md # Design specification
├── python_sdk_docs/        # Python SDK documentation
│   ├── index.json          # Python API index
│   ├── itasca.json         # Main module docs
│   └── modules/            # Submodule docs
└── references/             # Cross-references and guides
```

## Workflow

1. **Identify Gap**: Check existing index.json to find missing commands/APIs
2. **Fetch Official Doc**: Use WebFetch to get content from docs.itascacg.com
3. **Extract Key Info**: Parse syntax, parameters, examples, notes
4. **Format as JSON**: Follow the schema in STRUCTURE_DESIGN.md
5. **Update Index**: Add entry to appropriate index.json
6. **Cross-Reference**: Link to related Python APIs or commands

## Command Doc Schema

```json
{
  "command": "ball generate",
  "category": "ball",
  "description": "...",
  "syntax": "ball generate <keyword> ...",
  "keywords": [...],
  "examples": [...],
  "python_sdk_alternative": {...},
  "documentation_url": "https://docs.itascacg.com/..."
}
```

## Python SDK Doc Schema

```json
{
  "module": "itasca.ball",
  "functions": [...],
  "classes": [...],
  "command_alternatives": {...}
}
```

## Tips

- Always include `documentation_url` linking to official source
- Note when Python SDK cannot achieve what a command can (and vice versa)
- Use the existing generate_index.py script to regenerate index after updates
