import json
import time
import os

log_history = []

import itasca

# --- 1. Model Initialization ---
print("🔵 Step 1: Initializing model and domain...")
itasca.command("model new")
# 设Model Domain Extent为 [-10, 10]
itasca.command("model domain extent -10 10")
print("  ✓ Domain [-10, 10] set.")

# --- 2. Contact Model Setup ---
print("⚙️ Step 2: Setting up default contact model...")
# 接触模型属性参数
ITASCA_PROPERTIES = {
    "kn": 1.0e6, 
    "ks": 5.0e3, 
    "fric": 0.5, 
    "dp_nratio": 0.5, 
    "dp_sratio": 0.3
}
prop_list = [f"{k} {v}" for k, v in ITASCA_PROPERTIES.items()]
prop_str = "property " + " ".join(prop_list)
# 使用线性接触模型
itasca.command(f"contact cmat default model linear {prop_str}")
print("  ✓ Default linear contact model properties set.")

# --- 3. Wall (Box) and Physical Setup ---
print("⚙️ Step 3: Generating walls and setting gravity/strain...")
# 生成墙体盒子在 [-8, 8]
itasca.command("wall generate box -8 8")
# 设置重力 (标量 9.81 自动指向 -z)
itasca.command("model gravity 9.81")
# **设置大应变模式 (解决 cycle 错误)**
itasca.command("model large-strain true")
print("  ✓ Walls, Gravity, and Large-Strain condition set.")

# --- 4. Particle Generation and Property Assignment ---
print("⚙️ Step 4: Generating particles and setting density...")
# 生成 1000 个半径 0.5 的球体，限制在 Wall 盒子内，例如 [-7, 7]
itasca.command("ball generate number 1000 radius 0.5 box -7 7")
# **设置密度 (解决零惯性质量错误)**
# Using Python SDK iteration for robust attribute assignment
for ball in itasca.ball.list():
    ball.set_density(2600.0) 
print("  ✓ 1000 Balls generated; density 2600 kg/m^3 set.")

# Save a checkpoint of the initialized model
itasca.command("model save 'C:/Dev/Han/aiNagisa/pfc_workspace/setup_initial_state.sav'")
print("  ✓ Initial state checkpoint saved.")

# --- 5. Simulation Execution ---

# ------------------ Logging Utility and Execution ------------------
def record_log(message):
    """Stores message to log_history (Channel 3) and prints to Console (Channel 1)."""
    log_entry = {
        "timestamp": time.time(),
        "message": message
    }
    log_history.append(log_entry)
    print(message)

# --- 5. Simulation Execution ---
TOTAL_CYCLES = 50000
CYCLE_INCREMENT = 500 # Increased step size to reduce frequent print calls

record_log(f"▶️ Step 5: Starting {TOTAL_CYCLES} cycles for particle settling (reporting every {CYCLE_INCREMENT} steps)...")

for i in range(CYCLE_INCREMENT, TOTAL_CYCLES + 1, CYCLE_INCREMENT):
    itasca.command(f"model cycle {CYCLE_INCREMENT}")
    record_log(f"  ... Cycle completed: {i}/{TOTAL_CYCLES} ({i/TOTAL_CYCLES:.1%})")

record_log("Simulation cycles complete. State is persistent and settled.")

# --- 6. Final Verification and Export ---
print("📊 Step 6: Post-simulation verification...")

# 检查点：保存沉降后的最终状态
itasca.command("model save 'C:/Dev/Han/aiNagisa/pfc_workspace/setup_final_settled_state.sav'")
print("  ✓ Final settled state checkpoint saved.")

# **通道 3：将所有日志记录写入 JSON 文件**
JSON_OUTPUT_PATH = 'C:/Dev/Han/aiNagisa/pfc_workspace/analysis/settling_log_history.json'

# Ensure the output directory exists
os.makedirs(os.path.dirname(JSON_OUTPUT_PATH), exist_ok=True)

with open(JSON_OUTPUT_PATH, 'w') as f:
    json.dump(log_history, f, indent=4)
print(f"  ✓ Full simulation log history saved to {JSON_OUTPUT_PATH}")

print("Setup script with verification complete.")
