import itasca
import os

# 1. モデルの初期化とドメイン設定
print("[STEP 1] Initializing model and setting domain...")
itasca.command("model new")
# ドメインを立方体 (-1, 1) x (-1, 1) x (-1, 1) に設定
itasca.command("model domain extent -1 1 -1 1 -1 1")

# 2. ボール生成
print("[STEP 2] Generating balls...")
num_balls = 100
radius_low = 0.05
radius_high = 0.1
# ドメイン全体に100個のボールをランダムに生成
itasca.command(f"ball generate number {num_balls} radius {radius_low} {radius_high} box -1 1 -1 1 -1 1")

# 3. 検証
ball_count = itasca.ball.count()
print(f"[STEP 3] Verification: Total balls generated: {ball_count}")

if ball_count == num_balls:
    print("[RESULT] Test successful: The expected number of balls were created.")
else:
    print(f"[ERROR] Test failed: Expected {num_balls} balls, but found {ball_count}.")

# 4. モデル保存 (オプション: 状態を確認したい場合)
# itasca.command("model save '/Users/hanyusong/aiNagisa/pfc_workspace/initial_state.sav'")
