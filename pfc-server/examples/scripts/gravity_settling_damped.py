import itasca
import time

# --- INITIALIZATION AND SETUP ---
# 1. Reset Model
itasca.command("model new")

# 1.1 Set model domain extent to contain the wall box and particles
itasca.command("model domain extent -8 8 -8 8 -8 8")

# 2. Enable Large Strain mode for large displacement simulation
itasca.command("model large-strain true")

# 3. Set Global Gravity
itasca.command("model gravity 0 0 -9.81")

# 4. Set Contact Model and Properties (Linear Model)
# Set stiffness (kn/ks=1.0e6) and Damping (dn=0.5, ds=0.3)
itasca.command(
    "contact cmat default model linear "
    "property kn 1.0e6 ks 1.0e6 "
    "dp_nratio 0.5 dp_sratio 0.3"
)

# 5. Create Box Wall Container (-8 to 8)
itasca.command("wall generate box -8 8")

# 6. Create Balls
ball_count = 500
ball_radius = 0.5
ball_density = 2600
itasca.command(
    f"ball generate number {ball_count} radius {ball_radius} box -6 6"
)
itasca.command(f"ball attribute density {ball_density}")

print(f"Model Setup Complete. Created {ball_count} balls (R={ball_radius}) inside box [-8, 8].")


# --- SIMULATION EXECUTION ---
# Total cycles based on our successful test runs
total_cycles = 40000 
print(f"Starting gravity settling simulation for {total_cycles} cycles...")
start_time = time.time()

# Run the cycles
itasca.command(f"model cycle {total_cycles}")

end_time = time.time()
print(f"Simulation completed in {end_time - start_time:.2f} seconds.")


# --- QUERY AND OUTPUT RESULTS ---
# Check final ball count and the average z-position of settled balls
final_count = itasca.ball.count()
# Get all ball positions and calculate mean z-position for settlement analysis
try:
    ball_z_pos = itasca.ball.list().pos().z
    avg_z = ball_z_pos.mean()
    result = {
        "final_ball_count": final_count,
        "total_cycles_run": itasca.model.cycle(),
        "average_settled_z": avg_z
    }
    print(f"Final Ball Count: {final_count}")
    print(f"Average Settled Z-Position: {avg_z:.4f}")
    
except AttributeError:
    # Handles case where no balls are present for list() operation
    result = {"error": "Could not retrieve ball data."}
