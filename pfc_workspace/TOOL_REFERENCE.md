# PFC Tools Reference

Detailed reference for all PFC MCP tools available in aiNagisa.

## Table of Contents

- [Low-Level Tools](#low-level-tools)
  - [pfc_execute_command](#pfc_execute_command)
- [Particle Creation](#particle-creation)
  - [pfc_create_ball](#pfc_create_ball)
- [Simulation Control](#simulation-control)
  - [pfc_run_cycles](#pfc_run_cycles)
- [Model Queries](#model-queries)
  - [pfc_query_balls](#pfc_query_balls)
- [State Management](#state-management)
  - [pfc_save_state](#pfc_save_state)
  - [pfc_load_state](#pfc_load_state)

---

## Low-Level Tools

### pfc_execute_command

Execute raw ITASCA PFC SDK commands directly.

**Purpose**: Low-level tool for executing any PFC SDK command that isn't wrapped by high-level tools.

**Parameters**:
- `command` (str, required): PFC SDK command in dot notation
  - Example: `"ball.create"`, `"set.gravity"`, `"contact.list"`
- `params` (str, optional): JSON string of command parameters
  - Must be valid JSON
  - Keys match PFC SDK parameter names

**Returns**:
- JSON string containing `ToolResult`
- On success: `status="success"`, `data` contains command result
- On error: `status="error"`, `error` contains error message

**Example Usage**:

```python
# Set gravity
result = await pfc_execute_command(
    command="set.gravity",
    params='{"z": -9.81}'
)

# Create contact model
result = await pfc_execute_command(
    command="contact.model.create",
    params='{"name": "linear", "type": "ball-ball"}'
)

# Query PFC version
result = await pfc_execute_command(
    command="version",
    params=None
)
```

**Common Commands**:
- `"set.gravity"`: Set gravitational acceleration
- `"model.new"`: Create new model
- `"contact.model.create"`: Create contact model
- `"zone.create"`: Create zones
- `"measure.create"`: Create measurement sphere

**Notes**:
- Most flexible tool, but requires knowledge of ITASCA SDK
- Use high-level tools when available (better error handling)
- Check ITASCA documentation for command syntax

---

## Particle Creation

### pfc_create_ball

Create a ball (spherical particle) in the PFC model.

**Purpose**: High-level tool for creating individual ball particles.

**Parameters**:
- `radius` (float, required): Ball radius in model units
- `x` (float, optional): X-coordinate of ball center (default: 0.0)
- `y` (float, optional): Y-coordinate of ball center (default: 0.0)
- `z` (float, optional): Z-coordinate of ball center (default: 0.0)
- `density` (float, optional): Ball material density (default: 2500.0)

**Returns**:
- JSON string containing `ToolResult`
- On success: `data` includes ball ID and creation status

**Example Usage**:

```python
# Create ball at origin
result = await pfc_create_ball(radius=0.5)

# Create ball at specific position
result = await pfc_create_ball(
    radius=0.3,
    x=1.0,
    y=2.0,
    z=3.0,
    density=2650.0
)

# Create lightweight ball
result = await pfc_create_ball(
    radius=0.2,
    density=1000.0
)
```

**Units**:
- Coordinates and radius: model units (typically meters or millimeters)
- Density: typically kg/m³

**Notes**:
- Ball is created with zero initial velocity
- Ball properties (friction, stiffness) inherit from contact models
- Use `pfc_execute_command` for batch ball creation

---

## Simulation Control

### pfc_run_cycles

Run PFC simulation for a specified number of timesteps.

**Purpose**: Advance the simulation by executing calculation cycles.

**Parameters**:
- `steps` (int, required): Number of calculation cycles to execute

**Returns**:
- JSON string containing `ToolResult`
- On success: `message` confirms cycles completed

**Example Usage**:

```python
# Run short simulation
result = await pfc_run_cycles(steps=100)

# Run longer simulation
result = await pfc_run_cycles(steps=10000)

# Run to equilibrium (may require monitoring)
result = await pfc_run_cycles(steps=50000)
```

**Typical Step Counts**:
- **100-1000**: Quick settling
- **1000-10000**: Moderate simulation
- **10000-100000**: Long simulation or complex behavior

**Notes**:
- Execution time depends on model complexity and step count
- Large step counts may cause timeouts (default: 30s)
- Monitor unbalanced force ratio to check equilibrium
- Currently synchronous (blocks until complete)

---

## Model Queries

### pfc_query_balls

Query information about balls (particles) in the model.

**Purpose**: Retrieve ball properties for analysis or verification.

**Parameters**:
- `filter_expr` (str, optional): Filter expression to select specific balls
  - Example: `"radius > 0.5"`, `"id < 100"`

**Returns**:
- JSON string containing `ToolResult`
- On success: `data` contains list of balls with properties

**Example Usage**:

```python
# Get all balls
result = await pfc_query_balls()

# Get large balls only
result = await pfc_query_balls(filter_expr="radius > 0.5")

# Get balls in range
result = await pfc_query_balls(filter_expr="id < 100")
```

**Returned Properties** (typical):
- `id`: Ball ID number
- `radius`: Ball radius
- `position`: [x, y, z] coordinates
- `velocity`: [vx, vy, vz] velocity components
- `force`: [fx, fy, fz] force components
- `density`: Material density

**Notes**:
- Property availability depends on PFC version and model state
- Large models may return substantial data
- Filter expressions use PFC FISH syntax

---

## State Management

### pfc_save_state

Save current PFC model state to a file.

**Purpose**: Persist model state for later restoration or analysis.

**Parameters**:
- `filename` (str, required): Output filename for saved state
  - Typically `.sav` extension
  - Relative to PFC working directory

**Returns**:
- JSON string containing `ToolResult`
- On success: `message` confirms file saved

**Example Usage**:

```python
# Save with timestamp
result = await pfc_save_state(filename="model_initial.sav")

# Save checkpoint
result = await pfc_save_state(filename="checkpoint_1000.sav")

# Save with full path
result = await pfc_save_state(filename="C:/simulations/final_state.sav")
```

**Save File Contents**:
- Complete model geometry
- All ball and contact properties
- Model state and history
- Custom variables and groups

**Notes**:
- Save files can be large for complex models
- Path handling depends on OS (use forward slashes or raw strings)
- Overwrite behavior depends on PFC settings

---

### pfc_load_state

Load PFC model state from a previously saved file.

**Purpose**: Restore model state from a `.sav` file.

**Parameters**:
- `filename` (str, required): Input filename of saved state
  - Must exist and be a valid PFC save file
  - Relative to PFC working directory

**Returns**:
- JSON string containing `ToolResult`
- On success: `message` confirms file loaded

**Example Usage**:

```python
# Load initial state
result = await pfc_load_state(filename="model_initial.sav")

# Load checkpoint
result = await pfc_load_state(filename="checkpoint_1000.sav")

# Load from full path
result = await pfc_load_state(filename="C:/simulations/final_state.sav")
```

**Effects**:
- Replaces current model with saved state
- All current model data is discarded
- Restores geometry, properties, and history

**Notes**:
- Loading may take time for large files
- File must be compatible with current PFC version
- Use absolute paths to avoid ambiguity

---

## Error Handling

All tools return standardized `ToolResult` objects:

### Success Response
```json
{
  "status": "success",
  "message": "Command executed successfully",
  "llm_content": "Human-readable description",
  "data": {
    // Tool-specific result data
  }
}
```

### Error Response
```json
{
  "status": "error",
  "message": "Brief error description",
  "error": "Detailed error message",
  "data": {
    "command": "failed_command"
  }
}
```

## Common Error Types

1. **Connection Errors**
   - `"PFC server not connected"`
   - **Solution**: Ensure PFC server is running in PFC GUI

2. **Command Not Found**
   - `"Command 'xyz' not found in ITASCA SDK"`
   - **Solution**: Check command spelling and SDK documentation

3. **Invalid Parameters**
   - `"Invalid parameters JSON"`
   - **Solution**: Verify JSON syntax and parameter names

4. **Execution Timeout**
   - `"Command timed out after 30s"`
   - **Solution**: Reduce step count or increase timeout

## Tool Combinations

### Workflow Example

```python
# 1. Create a ball
await pfc_create_ball(radius=0.5, x=0, y=0, z=5, density=2500)

# 2. Set gravity
await pfc_execute_command("set.gravity", '{"z": -9.81}')

# 3. Run simulation
await pfc_run_cycles(steps=1000)

# 4. Query result
await pfc_query_balls()

# 5. Save state
await pfc_save_state(filename="dropped_ball.sav")
```

## Advanced Usage

### Custom FISH Commands

```python
# Define FISH function
await pfc_execute_command(
    command="fish.define",
    params='{"name": "my_func", "code": "return ball.num"}'
)

# Call FISH function
await pfc_execute_command(
    command="fish.eval",
    params='{"expression": "my_func"}'
)
```

### Batch Operations

For creating many entities, use loops or FISH scripts:

```python
# Loop in Python (slower - multiple WebSocket calls)
for i in range(10):
    await pfc_create_ball(radius=0.5, x=i, y=0, z=0)

# Better: Use FISH script (single WebSocket call)
await pfc_execute_command(
    command="fish.exec",
    params='{
        "script": "loop i (1, 10) \n command \n ball create radius 0.5 position [i,0,0] \n endcommand \n endloop"
    }'
)
```

## Further Reading

- [ITASCA PFC Documentation](https://www.itascacg.com/software/pfc)
- [PFC FISH Scripting Guide](https://www.itascacg.com/)
- [aiNagisa PFC Quick Start](QUICKSTART.md)
