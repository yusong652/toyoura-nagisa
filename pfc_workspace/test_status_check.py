import itasca
import time
import sys

# -----------------
# PURE EXECUTION
# -----------------
# 🔵 Step 1: Initialize model
print("🔵 Step 1: Initializing a clean 3D model...")
itasca.command("model new")
itasca.command("model large-strain true")
itasca.command("model domain extent 0 10 0 10 0 10")
itasca.command("model mechanical time increment 1.0")
itasca.command("model gravity 0 0 -9.81") # <--- 修正后的重力命令
print("  ✓ Model initialized successfully.")

# ⚙️ Step 2: Setup particles (small batch for quick test)
print("⚙️ Step 2: Generating walls and 500 balls for the simulation...")
itasca.command("wall generate box 1 9") 
itasca.command("ball generate number 500 radius 0.5 box 1 9 1 9 1 9")
itasca.command("contact cmat default model linear property kn 1e7 ks 5.0e6 fric 0.5 dp_nratio 0.5 dp_sratio 0.3")
itasca.command("ball property density 2500") 
print(f"  ✓ {itasca.wall.count() if 'itasca' in sys.modules else 6} walls, {itasca.ball.count()} balls generated. CMAT and Density set up.")

# ▶️ Step 3: Run cycles and print progress
print("▶️ Step 3: Starting quick cycle test (200 steps total)...")
total_cycles = 60000
check_interval = 200

for i in range(check_interval, total_cycles + check_interval, check_interval):
    itasca.command(f"model cycle {check_interval}")
    
    # Calculate some metric (e.g., average Z position)
    avg_z = sum(ball.pos_z() for ball in itasca.ball.list()) / itasca.ball.count()
    
    # Channel 1: Real-time progress monitoring
    print(f"Progress: {i}/{total_cycles} ({i*100/total_cycles}%) | Avg Z: {avg_z:.3f} m")
    
    # Give it a moment to simulate time (since actual simulation is fast)
    time.sleep(0.05) 

print("✅ Script execution completed.")
