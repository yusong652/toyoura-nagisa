# Experimental Task Design for Paper Evaluation

## Design Principles

1. **Reproducibility**: Clear, unambiguous task descriptions
2. **Physical Validity**: Tasks with known correct outcomes
3. **Complexity Gradient**: Progressive difficulty from syntax to workflow
4. **DEM Relevance**: Classic problems familiar to domain experts

---

## Task Levels Overview

| Level | Category | Core Challenge | Est. Particles | Est. Duration |
|-------|----------|----------------|----------------|---------------|
| L1 | Basic Syntax | Command/API usage | 1-10 | < 10s |
| L2 | Simple Simulation | Parameter configuration | 10-100 | < 1 min |
| L3 | Standard Problem | Boundary conditions, monitoring | 100-500 | 1-10 min |
| L4 | Complex Geometry | Multi-step modeling | 500-2000 | 10-30 min |
| L5 | Iterative Workflow | Autonomous optimization | 100-500 | Multiple runs |

---

## Level 1: Basic Syntax (L1)

### L1-1: Single Ball Creation

**Task Prompt (English)**:
> Create a single ball at position (0, 0, 0) with radius 0.5 and density 2650.

**Validation Criteria**:
- [ ] Script executes without syntax error
- [ ] Ball count equals 1
- [ ] Ball position is (0, 0, 0) ± 0.001
- [ ] Ball radius is 0.5
- [ ] Ball density is 2650

**Expected Tool Usage**:
- `pfc_query_command("create ball")` or `pfc_query_python_api("ball create")`
- `pfc_browse_commands("ball create")` or `pfc_browse_python_api("itasca.ball.create")`
- `pfc_execute_task` (foreground, short)

**Physical Reasoning**: None required - pure syntax test

---

### L1-2: Wall Definition

**Task Prompt (English)**:
> Create a rectangular box using 6 walls: x from -1 to 1, y from -1 to 1, z from 0 to 2.

**Validation Criteria**:
- [ ] Script executes without error
- [ ] 6 walls created (or equivalent facets)
- [ ] Box dimensions match specification
- [ ] Walls are properly oriented (normals pointing inward)

**Expected Tool Usage**:
- Documentation query for wall creation
- `pfc_execute_task`

---

### L1-3: Contact Model Assignment

**Task Prompt (English)**:
> Assign the linear contact model to all ball-ball contacts with friction coefficient 0.5.

**Validation Criteria**:
- [ ] Contact model type is "linear"
- [ ] Friction coefficient is 0.5
- [ ] Assignment applies to correct contact type

---

## Level 2: Simple Simulation (L2)

### L2-1: Gravity Settling

**Task Prompt (English)**:
> Create 50 balls randomly distributed in a box (1m × 1m × 2m), apply gravity (9.81 m/s² downward), and let them settle until the system reaches equilibrium. The balls should have radius 0.05m and density 2650 kg/m³.

**Validation Criteria**:
- [ ] 50 balls created within specified volume
- [ ] Gravity direction is -z (or -y depending on convention)
- [ ] Simulation reaches equilibrium (unbalanced force ratio < 1e-5)
- [ ] All balls remain within the box
- [ ] Final configuration is physically reasonable (pile at bottom)

**Expected Tool Usage**:
- Multiple documentation queries (ball generation, gravity, cycling)
- `pfc_execute_task` (background for cycling)
- `pfc_check_task_status` for progress monitoring

**Physical Reasoning**:
- Understanding gravity direction convention
- Recognizing equilibrium criteria

---

### L2-2: Clump Generation

**Task Prompt (English)**:
> Create 30 elongated clumps to represent non-spherical particles:
> 1. Each clump should consist of 3 overlapping spheres (pebbles) arranged linearly
> 2. Pebble radius: 0.02m, overlap ratio: 0.3 (30% overlap between adjacent pebbles)
> 3. Place clumps randomly in a box (0.5m × 0.5m × 1m)
> 4. Let them settle under gravity

**Validation Criteria**:
- [ ] 30 clumps created (not individual balls)
- [ ] Each clump has 3 pebbles
- [ ] Clump geometry shows elongated shape
- [ ] Clumps settle without excessive interpenetration
- [ ] Final pile shows more complex fabric than spherical particles

**Expected Tool Usage**:
- `pfc_query_command("clump")` or `pfc_query_python_api("clump template")`
- `pfc_browse_commands("clump template")` for template definition
- `pfc_execute_task` for generation and settling

**Physical Reasoning**:
- Understanding clump vs ball distinction
- Template-based clump generation
- Non-spherical particle behavior

---

### L2-3: Particle Size Distribution

**Task Prompt (English)**:
> Generate 100 balls with a uniform particle size distribution: radii ranging from 0.03m to 0.07m. Place them randomly in a cubic domain of side length 1m.

**Validation Criteria**:
- [ ] 100 balls created
- [ ] Minimum radius ≈ 0.03m
- [ ] Maximum radius ≈ 0.07m
- [ ] Distribution is approximately uniform (visual inspection)
- [ ] No balls overlap excessively

---

## Level 3: Standard DEM Problems (L3)

### L3-1: Triaxial Compression Test

**Task Prompt (English)**:
> Simulate a triaxial compression test on a granular sample:
> 1. Create a cylindrical sample with approximately 200 balls (radius 0.5-1.0 mm)
> 2. Apply confining pressure of 100 kPa using servo-controlled walls
> 3. Compress axially at strain rate 0.1/s until 20% axial strain
> 4. Record the stress-strain curve (deviatoric stress vs axial strain)

**Validation Criteria**:
- [ ] Sample geometry is approximately cylindrical
- [ ] Particle count is 150-250
- [ ] Confining pressure is maintained at 100 kPa ± 10%
- [ ] Stress-strain curve shows typical DEM response:
  - Initial linear elastic region
  - Peak strength reached
  - Post-peak softening (if applicable)
- [ ] Deviatoric stress is positive and reasonable magnitude

**Expected Tool Usage**:
- Multiple documentation queries
- Iterative script development (sample creation → compression)
- `pfc_capture_plot` for visual verification
- `pfc_check_task_status` for long-running compression

**Physical Reasoning**:
- Understanding triaxial test mechanics
- Servo-control for constant pressure
- Stress calculation from wall forces

---

### L3-2: Angle of Repose

**Task Prompt (English)**:
> Measure the angle of repose of a granular material:
> 1. Create 300 balls (radius 2-4 mm, density 2650 kg/m³) in a rectangular hopper
> 2. Open the bottom of the hopper and let particles flow out onto a flat surface
> 3. Measure the angle of repose of the resulting pile

**Validation Criteria**:
- [ ] Particles flow out of hopper
- [ ] Stable pile forms on the surface
- [ ] Angle of repose is measured and reported
- [ ] Angle is in physically reasonable range (25-40° for typical granular materials)

**Physical Reasoning**:
- Understanding angle of repose concept
- Flow initiation mechanics

---

### L3-3: Direct Shear Test

**Task Prompt (English)**:
> Perform a direct shear test:
> 1. Create a rectangular sample (50mm × 50mm × 20mm) with ~150 balls
> 2. Apply normal stress of 50 kPa on top
> 3. Shear the upper half horizontally at constant velocity
> 4. Record shear stress vs shear displacement

**Validation Criteria**:
- [ ] Sample geometry matches specification
- [ ] Normal stress is applied correctly
- [ ] Shear displacement is applied to upper portion
- [ ] Shear stress vs displacement curve is recorded
- [ ] Peak shear stress is in reasonable range

---

### L3-4: Undrained Triaxial Test

**Task Prompt (English)**:
> Simulate an undrained triaxial compression test on a saturated granular sample:
> 1. Create a cylindrical sample with ~200 balls (radius 0.5-1.0 mm)
> 2. Apply initial isotropic confining pressure of 100 kPa
> 3. Implement constant volume constraint by servo-controlling all boundary walls
> 4. Compress axially until 15% strain while maintaining constant volume
> 5. Output numerical data: mean effective stress p', deviatoric stress q, volumetric strain at each recording interval
> 6. Verify the undrained condition by checking that volumetric strain remains < 0.5%

**Validation Criteria**:
- [ ] Volumetric strain remains below 0.5% throughout shearing (numerical check)
- [ ] Mean effective stress p' and deviatoric stress q are correctly calculated from wall forces
- [ ] Data output includes: axial strain, p', q at regular intervals
- [ ] Agent analyzes the p'-q relationship from numerical data (not visual inspection)
- [ ] Agent identifies whether sample is contractive or dilative based on p' trend

**Expected Tool Usage**:
- Multiple documentation queries for servo-control and stress measurement
- `pfc_execute_task` with data output to file
- Script reads output file and performs numerical analysis
- Agent reasons about stress path from data values

**Physical Reasoning**:
- Understanding drained vs undrained conditions
- Volume constraint implementation via servo-controlled walls
- Effective stress calculation: p' = (σ1' + 2σ3')/3, q = σ1' - σ3'
- Contractive vs dilative behavior interpretation

**Key Difference from L3-1**:
This task tests the agent's ability to implement complex boundary conditions (constant volume) and perform quantitative data analysis, rather than just running a simulation.

---

## Level 4: Complex Geometry Problems (L4)

### L4-1: Slope Stability Analysis

**Task Prompt (English)**:
> Model a granular slope and analyze its stability:
> 1. Create a slope with angle 35° using ~1000 balls
> 2. Apply gravity and allow initial settling
> 3. Gradually steepen the slope (or reduce friction) until failure
> 4. Identify the failure surface and failure mode

**Validation Criteria**:
- [ ] Slope geometry is correctly constructed
- [ ] Initial configuration is stable
- [ ] Failure occurs when stability limit is exceeded
- [ ] Failure surface can be identified (visual or displacement field)

**Expected Tool Usage**:
- Complex geometry construction
- `pfc_capture_plot` for failure visualization
- Possibly invoke PFC Diagnostic SubAgent

**Physical Reasoning**:
- Slope stability concepts
- Failure mechanism identification

---

### L4-2: Drum Mixer Simulation

**Task Prompt (English)**:
> Simulate a rotating drum mixer:
> 1. Create a cylindrical drum (diameter 0.5m, length 0.3m)
> 2. Fill with 500 balls of two colors (250 each, same size)
> 3. Rotate drum at 30 RPM
> 4. Observe mixing pattern after 10 rotations

**Validation Criteria**:
- [ ] Drum geometry is correct
- [ ] Rotation velocity is correct (30 RPM)
- [ ] Two particle types are distinguishable
- [ ] Mixing pattern is visible after 10 rotations

---

### L4-3: Silo Discharge

**Task Prompt (English)**:
> Model silo discharge:
> 1. Create a silo with funnel bottom (total height 2m, cylinder diameter 0.5m)
> 2. Fill with 800 balls (radius 10-15mm)
> 3. Open bottom orifice (diameter 100mm)
> 4. Measure discharge rate (balls per second)

**Validation Criteria**:
- [ ] Silo geometry matches specification
- [ ] Flow initiates when orifice opens
- [ ] Discharge rate is measured
- [ ] Flow pattern is reasonable (funnel or mass flow)

---

## Level 5: Iterative Workflow (L5)

### L5-1: Friction Coefficient Calibration

**Task Prompt (English)**:
> Calibrate the friction coefficient to match a target angle of repose of 30°:
> 1. Start with initial friction coefficient μ = 0.3
> 2. Run angle of repose test
> 3. Measure the resulting angle
> 4. Adjust friction coefficient based on the difference
> 5. Iterate until the measured angle is within ±2° of target

**Validation Criteria**:
- [ ] Iterative process is executed (not single attempt)
- [ ] Each iteration correctly measures angle of repose
- [ ] Parameter adjustment direction is reasonable
- [ ] Final angle is within ±2° of 30°
- [ ] Number of iterations is reasonable (< 10)

**Expected Tool Usage**:
- Multiple `pfc_execute_task` calls
- `pfc_capture_plot` for visual verification
- Autonomous decision-making between iterations
- Possibly PFC Diagnostic SubAgent for angle measurement

**Physical Reasoning**:
- Understanding friction-repose relationship
- Iterative optimization strategy

---

### L5-2: Packing Density Optimization

**Task Prompt (English)**:
> Optimize the packing density of a granular assembly:
> 1. Target: achieve packing density (solid fraction) > 0.60
> 2. Start with random generation of 200 balls in a 0.1m × 0.1m × 0.1m box
> 3. Apply isotropic compression and vibration cycles
> 4. Measure packing density after each cycle
> 5. Continue until target is reached or maximum 5 cycles

**Validation Criteria**:
- [ ] Packing density is correctly calculated
- [ ] Compression/vibration strategy is reasonable
- [ ] Progress is tracked across iterations
- [ ] Final packing density ≥ 0.60 (or justified why not achievable)

---

### L5-3: Multi-Parameter Sensitivity Study

**Task Prompt (English)**:
> Conduct a sensitivity study for triaxial test:
> 1. Base parameters: friction=0.5, stiffness=1e8 N/m, confining=100kPa
> 2. Vary friction: 0.3, 0.5, 0.7
> 3. For each friction value, run triaxial test and record peak strength
> 4. Report the sensitivity of peak strength to friction coefficient

**Validation Criteria**:
- [ ] Three simulations are run with different friction values
- [ ] Peak strength is recorded for each
- [ ] Sensitivity analysis is presented (table or plot)
- [ ] Results show expected trend (higher friction → higher strength)

---

## Summary Table

| Task ID | Level | Key Challenge | Est. Tool Calls | Documentation Dependency |
|---------|-------|---------------|-----------------|-------------------------|
| L1-1 | L1 | Single ball syntax | 3-5 | High |
| L1-2 | L1 | Wall geometry | 3-5 | High |
| L1-3 | L1 | Contact model | 3-5 | High |
| L2-1 | L2 | Equilibrium detection | 5-10 | Medium |
| L2-2 | L2 | Clump generation | 5-10 | High |
| L2-3 | L2 | Size distribution | 5-8 | Medium |
| L3-1 | L3 | Servo control, stress | 10-20 | High |
| L3-2 | L3 | Flow simulation | 8-15 | Medium |
| L3-3 | L3 | Shear mechanics | 10-18 | High |
| L3-4 | L3 | Undrained + data analysis | 12-22 | High |
| L4-1 | L4 | Complex geometry | 15-25 | Medium |
| L4-2 | L4 | Rotating boundary | 12-20 | Medium |
| L4-3 | L4 | Orifice flow | 12-20 | Medium |
| L5-1 | L5 | Iterative calibration | 20-40 | Low (after learning) |
| L5-2 | L5 | Optimization loop | 20-35 | Low |
| L5-3 | L5 | Batch execution | 25-45 | Low |

---

## Notes for Experiment Execution

### Baseline Configuration (No Documentation)
For -Doc ablation: Remove `pfc_query_*` and `pfc_browse_*` tools from the main agent tool list. LLM must rely on training knowledge only.

### Execution Protocol
1. Each task run with fresh session (no memory carryover)
2. Record all tool calls and LLM responses
3. Timeout: L1=2min, L2=5min, L3=15min, L4=30min, L5=60min per iteration
4. Human intervention: Record timestamp and content, mark as partial success

### Success Classification
- **Full Success**: All validation criteria met autonomously
- **Partial Success**: Task completed with human intervention
- **Failure**: Task not completed or physically incorrect results
