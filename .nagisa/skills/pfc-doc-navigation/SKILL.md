---
name: pfc-doc-navigation
description: >
  PFC documentation navigation strategies and tool usage patterns.
  Use when searching for PFC commands, browsing Python API, or need to
  understand the difference between Commands and Python API capabilities.
---

# PFC Documentation Navigation

Effective strategies for finding and using PFC documentation.

---

## Query vs Browse: Decision Tree

**Query tools** - Fast keyword search returning documentation paths
- `pfc_query_command(query="...")` - Find command paths
- `pfc_query_python_api(query="...")` - Find API paths
- **Use when**: Know WHAT you need, not WHERE it is

**Browse tools** - Hierarchical navigation showing full documentation
- `pfc_browse_commands(command="...")` - Navigate command hierarchy
- `pfc_browse_python_api(api="...")` - Navigate Python API hierarchy
- `pfc_browse_reference(topic="...")` - Reference docs (contact models, range elements)
- **Use when**: Know WHERE to look OR need to explore capability boundaries

**Decision tree**:
- Know exact path? → Browse directly
- Have keywords only? → Query first, then Browse
- Exploring what's available? → Browse with no/partial path
- Need to check if feature exists? → Browse category (no match = implement custom)

**Workflow**: Query → Browse → Implement
```python
pfc_query_python_api(query="ball velocity")        # → Found: itasca.ball.Ball.vel
pfc_browse_python_api(api="itasca.ball.Ball.vel")  # → Full method docs
```

---

## The Fundamental Division: Commands vs Python API

**Critical architectural insight**:

| Component | Can Do | Cannot Do |
|-----------|--------|-----------|
| **Commands** | CREATE, MODIFY state | READ data |
| **Python API** | READ data, ITERATE objects | (rarely modifies) |

**Why this matters**:
```python
# ✗ IMPOSSIBLE - Commands cannot retrieve data
itasca.command('ball get velocity')  # No such command exists!

# ✓ CORRECT - Python API for data access
for ball in itasca.ball.list():
    vel = ball.vel()  # Only Python API can READ

# ✗ IMPOSSIBLE - Python API rarely has setters
ball.set_radius(0.2)  # Most objects have no setters

# ✓ CORRECT - Commands for state modification
itasca.command('ball attribute radius 0.2')
```

**When exploring**: If Browse tools show no PFC feature for your need (e.g., "calculate stress tensor"), you MUST implement custom Python logic using READ operations from Python API.

---

## Search Strategy (Priority Order)

1. **Exact Query** - Use keywords directly
   - `pfc_query_command(query="confining pressure")`

2. **Semantic Variants** - Try synonyms and related terms
   - "confining pressure" → "stress boundary", "servo", "wall velocity"

3. **Parent Category Exploration** - Browse parent categories when keywords fail
   - "servo" unclear → `pfc_browse_commands(command="wall")` → discover related

4. **Cross-Reference** - Check if Python API has what commands lack (or vice versa)
   - Command syntax found but no Python example → query `pfc_query_python_api`
   - Python API found but no command → some features are Python-only

5. **Confirm Absence** - If Steps 1-4 fail, explicitly confirm non-existence
   - Report: "Feature does not exist in PFC. Closest alternatives: [list]"

**Stop Condition**: Report when you have either:
- Complete documentation for the requested capability, OR
- Confirmed absence with closest alternatives

---

## High-Level vs Low-Level Approaches

Many high-level PFC features have limitations. Consider low-level alternatives:

| High-Level Feature | Limitations | Low-Level Alternative |
|--------------------|-------------|----------------------|
| `servo` command | Single force direction only | `wall.vertices()` + manual velocity/position control |
| `ball generate` | Predefined patterns only | `ball create` + custom positioning |
| `wall generate` | Simple geometries only | `wall create` + vertex specification |

**When to consider alternatives**:
- Compression/shear tests → Check servo AND wall vertex control
- Particle generation → Check generate AND manual create
- Boundary conditions → Check built-in AND manual implementation

**Philosophy**: Find BOTH high-level and low-level options. Choose based on:
- High-level: Simpler, faster to implement, sufficient for standard cases
- Low-level: More control, handles edge cases, requires more code

---

## Quick Reference

```python
# Browse - Commands (CREATE/MODIFY)
pfc_browse_commands()                        # List categories
pfc_browse_commands(command="ball create")   # Full docs

# Browse - Python API (READ/ITERATE)
pfc_browse_python_api()                              # Overview
pfc_browse_python_api(api="itasca.ball.Ball.pos")   # Full method docs

# Browse - Reference Documentation
pfc_browse_reference(topic="contact-models linear")  # Properties: kn, ks, fric...
pfc_browse_reference(topic="range-elements group")   # Range filtering syntax

# Query (keyword search → returns paths)
pfc_query_command(query="generate")
pfc_query_python_api(query="contact force")
```
