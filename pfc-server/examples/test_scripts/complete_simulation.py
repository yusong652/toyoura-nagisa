#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Complete PFC Simulation Script - Test for Script Execution Tool

This script demonstrates a complete DEM simulation workflow using PFC Python SDK.
It includes all stages from domain setup to long-running calculation.

Workflow:
    1. Domain initialization
    2. Material property setup (large-strain, gravity)
    3. Geometry generation (walls, particles)
    4. Contact model configuration (thread-sensitive operation)
    5. Long-running calculation with progress tracking

Usage:
    This script is designed to be executed via pfc_execute_script tool,
    demonstrating non-blocking script execution and task management.

Expected execution time: 30-60 seconds (depending on hardware)
"""

import time

try:
    import itasca

    # Track simulation start time
    start_time = time.time()

    print("=" * 70, flush=True)
    print("PFC Complete Simulation Script", flush=True)
    print("=" * 70, flush=True)

    # Step 1: Domain Setup
    print("\n[Step 1/7] Setting up domain extent...", flush=True)
    itasca.command("model domain extent -10 10 -10 10 -10 10")
    print("✓ Domain extent configured: -10 to 10 in all directions", flush=True)

    # Step 2: Enable Large-Strain Mode
    print("\n[Step 2/7] Enabling large-strain mode...", flush=True)
    itasca.command("model large-strain on")
    print("✓ Large-strain mode enabled", flush=True)

    # Step 3: Set Gravity
    print("\n[Step 3/7] Setting gravity...", flush=True)
    itasca.command("model gravity (0, 0, -9.81)")
    print("✓ Gravity set to (0, 0, -9.81) m/s²", flush=True)

    # Step 4: Create Boundary Walls
    print("\n[Step 4/7] Creating boundary walls...", flush=True)
    itasca.command("wall generate box -8 8")
    wall_count = itasca.wall.count()
    print(f"✓ Boundary walls created (count: {wall_count})", flush=True)

    # Step 5: Generate Balls
    print("\n[Step 5/7] Generating 500 balls...", flush=True)
    itasca.command("ball generate number 500 radius 0.5 box -7 7")
    ball_count = itasca.ball.count()
    print(f"✓ Balls generated (count: {ball_count})", flush=True)

    # Set ball density to avoid zero mass
    print("   Setting ball density to 2500 kg/m³...", flush=True)
    itasca.command("ball attribute density 2500.0")
    print("✓ Ball density configured", flush=True)

    # Step 6: Setup Contact Model (CRITICAL - MAIN THREAD)
    print("\n[Step 6/7] Setting up contact model (thread-sensitive)...", flush=True)
    itasca.command(
        "contact cmat default model linear "
        "property kn 1.0e6 fric 0.5 dp_nratio 0.5 dp_sratio 0.3"
    )
    print("✓ Contact model configured with linear properties", flush=True)
    print("   - Normal stiffness (kn): 1.0e6 N/m", flush=True)
    print("   - Friction coefficient: 0.5", flush=True)
    print("   - Normal damping ratio: 0.5", flush=True)
    print("   - Shear damping ratio: 0.3", flush=True)

    # Step 7: Long-Running Calculation
    print("\n[Step 7/7] Running long calculation (80000 cycles)...", flush=True)
    print("   This will take approximately 30-60 seconds...", flush=True)
    print("   Progress checkpoints:", flush=True)

    # Break calculation into segments for progress tracking
    total_cycles = 80000
    checkpoint_interval = 20000

    for checkpoint in range(0, total_cycles, checkpoint_interval):
        cycles_to_run = min(checkpoint_interval, total_cycles - checkpoint)
        itasca.command(f"model solve cycle {cycles_to_run}")

        current_cycle = checkpoint + cycles_to_run
        progress = (current_cycle / total_cycles) * 100
        elapsed = time.time() - start_time

        print(f"   ├─ Cycle {current_cycle}/{total_cycles} ({progress:.1f}%) "
              f"- Elapsed: {elapsed:.1f}s", flush=True)

    print("✓ Calculation completed", flush=True)

    # Gather final results
    total_time = time.time() - start_time
    final_ball_count = itasca.ball.count()
    final_wall_count = itasca.wall.count()

    print("\n" + "=" * 70, flush=True)
    print("Simulation Summary", flush=True)
    print("=" * 70, flush=True)
    print(f"Total execution time: {total_time:.2f} seconds", flush=True)
    print(f"Final ball count: {final_ball_count}", flush=True)
    print(f"Final wall count: {final_wall_count}", flush=True)
    print(f"Cycles completed: {total_cycles}", flush=True)
    print("=" * 70, flush=True)

    # Set result for return
    result = {
        "status": "success",
        "total_time": round(total_time, 2),
        "ball_count": final_ball_count,
        "wall_count": final_wall_count,
        "cycles_completed": total_cycles,
        "message": f"Simulation completed successfully in {total_time:.2f}s"
    }

    print("\n✓ Script execution successful", flush=True)

except ImportError:
    result = {
        "status": "error",
        "message": "itasca module not available - must run in PFC environment",
        "error": "ImportError"
    }
    print("❌ Error: itasca module not available", flush=True)

except Exception as e:
    result = {
        "status": "error",
        "message": f"Simulation failed: {str(e)}",
        "error": type(e).__name__,
        "error_details": str(e)
    }
    print(f"❌ Error during simulation: {e}", flush=True)
    import traceback
    traceback.print_exc()
