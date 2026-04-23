"""
This script is the final step to fly a trajectory recorded and processed by the
previous scripts (s01, s02, s03). It loads a trajectory, prepares it for flight,
and commands a Crazyflie drone to execute it

Usage -> run after 's01_recording.py'!
"""

import sys, time, numpy as np
from pathlib import Path

# Modifying system path to import 'crazyflie' package
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from crazyflie import bitcraze
import crazyflie.core.base_utils as base
from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor
from crazyflie.bitcraze.trajectory import Trajectory

from s03_processing import filter_waypoints, add_yaw                                        #Processes the raw trajectory data to prepare it for flight. This includes filtering, smoothing, and adding yaw information
from utils import plot_waypoints, load_waypoints, save_waypoints, VirtualCage               #Contains utility functions for plotting, file I/O, and other common tasks

#----------- CONFIG BEFORE USAGE --------------
cage = VirtualCage(x_bounds=(-1.0, 1.0), y_bounds=(-1.0, 1.0), z_bounds=(0.2, 1.0))
#----------------------------------------------

#URI = 'radio://0/100/2M/E7E7E7E704'  # URI of the Crazyflie drone to connect to
#ID = 14                              # Rigid body ID of the drone in the OptiTrack system

save_dir = Path(__file__).resolve().parent / 'data'/ 'recorded_trajectories'
processed_dir = Path(__file__).resolve().parent / 'data' / 'processed_trajectories'

def main():
    """
    Main function to handle trajectory loading, processing, and flight execution.
    """
    print("\n--- Trajectory Flight Initializer ---")
    
    # LOAD OR PROCESS TRAJECTORY
    file_name = input("Enter the filename to fly (e.g., 'circle1'): ").strip().replace('.csv', '')
    raw_path = save_dir / f"{file_name}.csv"
    proc_path = processed_dir / f"{file_name}.csv"

    # Check if a pre-processed version of the trajectory exists
    if proc_path.exists():
        print(f"[Mode] Found PROCESSED version: {proc_path.name}")
        enhanced_waypoints = load_waypoints(proc_path)

    # If not, check for a raw file and process it on-the-fly
    elif raw_path.exists():
        print(f"[Mode] Processed not found. Processing RAW file: {raw_path.name}")
        raw_waypoints = load_waypoints(raw_path)

        # Process the raw data: filter, smooth, add yaw, and apply cage constraints
        enhanced_waypoints = add_yaw(filter_waypoints(raw_waypoints, min_height=0.2, cage=cage))
        plot_waypoints([raw_waypoints, enhanced_waypoints], labels=['Raw', 'Processed'])

        # Save the processed version for future use
        save_waypoints(enhanced_waypoints, proc_path)
        print(f"Saved processed version to: {processed_dir.name}")
    else:
        print(f"CRITICAL ERROR: File '{file_name}' not found in recorded or processed folders.")
        return

    # PREPARE FLIGHT STATES
    calculator = Trajectory()
    calculator.logging(enable=False, file=False, level=calculator.LogLevel.debug)
    calculator.set_count(1)

    positions = create_trajectory_objects(calculator, enhanced_waypoints)
    print(f"Loaded {len(positions)} setpoints. Initializing visualization...")

    # SAFETY VISUALIZATION AND CONFIRMATION
    plot_waypoints([positions], labels=['Flight Path'], calculator=calculator)

    # Require final user confirmation before arming the drone
    confirm = input("\nArm drone and start flight? (y/n): ").lower().strip()
    if confirm != 'y':
        print("Flight cancelled by user.")
        return

    # HARDWARE INITIALIZATION AND FLIGHT
    print("Connecting to OptiTrack...")
    monitor = NatNetRigidBodyMonitor()
    monitor.start()
    time.sleep(2)


    cf = CrazyFlie()
    cf.logging(enable=True, file=True, level=base.LogLevel.debug)
    cf.set_natnet_monitor(monitor)

    """
    cf = CrazyFlie()
    cf.logging(enable=True, file=True, level=base.LogLevel.debug)
    cf.set_natnet_monitor(monitor)
    """
    try:
        cf.scan()
        cf.connect(start_flying=True)

        for pos_state in positions:
            cf.fly(pos_state)
            while not cf.arrived(pos_state):
                time.sleep(0.1)
            time.sleep(0.2)

        cf.land()
    except (bitcraze.CrazyFlieError, KeyboardInterrupt):
        print("Flight interrupted.")
    finally:
        cf.disconnect()

"""
    try:
        print(f"Connecting to Crazyflie at {URI}...")
        cf.scan()
        cf.connect(start_flying=True)

        print("Flying trajectory...")
        for pos_state in positions:
            cf.fly(pos_state)
            while not cf.arrived(pos_state):
                time.sleep(0.1)  # Check arrival status at 20Hz
            time.sleep(0.2)

        print("Sequence complete. Landing...")
        cf.land()

    except (bitcraze.CrazyFlieError, KeyboardInterrupt) as e:
        print(f"\n[INTERRUPTED] Safety landing triggered: {e}")
        try:
            cf.land()
        except:
            pass
    finally:
        cf.disconnect()
        print("System shutdown complete.")
"""

# ------- ADDITIONAL -------
def create_trajectory_objects(calculator: Trajectory, list_of_pos: np.ndarray) -> list:
    """
    Converts a list of numpy coordinates into internal CrazyFlie state objects
    """
    return [
        calculator.get_position(
            x=item[0], y=item[1], z=item[2],
            yaw=(item[3] if len(item) > 3 else 0), # Use yaw if available, otherwise default to 0
            pitch=0, roll=0
        ) for item in list_of_pos
    ]
# --------------------------


if __name__ == '__main__':
    main()