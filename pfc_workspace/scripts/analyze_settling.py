import itasca
import numpy as np

# Use itasca SDK to get the list of balls
ball_list = itasca.ball.list()

# Check if there are any balls
if ball_list:
    # Get the Z coordinates (index 2 for Z in [x, y, z])
    z_coords = [b.pos(2) for b in ball_list]
    avg_z = np.mean(z_coords)
    min_z = np.min(z_coords)
else:
    avg_z = 0.0
    min_z = 0.0

# The 'result' variable will be returned by pfc_execute_script
result = {
    "ball_count": itasca.ball.count(),
    "average_z": float(avg_z),
    "min_z": float(min_z),
    "simulation_status": "Settled after 100000 cycles"
}