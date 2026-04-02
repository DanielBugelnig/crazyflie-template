"""
Main execution script for OptiTrack tracking, recording, and flying
Includes real-time safety bounds (Virtual Cage)

Usage:
'u' - update filename
's' - start recording
'e' - stop recording & save
'm' - plot the trajectory in 3D
'q' - smooth recorded trajectory, add yaw, and save
'f' - fly a loaded trajectory
"""

import os, sys, time, threading
from pathlib import Path
from threading import Lock, Thread
from pynput import keyboard

sys.path.append(str(Path(__file__).resolve().parents[2])) #?1
from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor
import crazyflie.core.base_utils as base
from crazyflie import bitcraze
from crazyflie.bitcraze.trajectory import Trajectory
from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.constants import MOCAP_TX_RATE_HZ

from trajectory_math import TrajectoryPlanner, plot_waypoints, filter_waypoints, load_waypoints, add_yaw, save_waypoints
from safety_scoring import VirtualCage

# Paths
base_path = Path(__file__).resolve().parents[0]
save_dir = base_path / 'trajectories'
processed_dir = base_path / 'processed_waypoints' #to store processed trajectories
os.makedirs(save_dir, exist_ok=True)
os.makedirs(processed_dir, exist_ok=True)
filename = None

# Constants & Globals
UPDATE_RATE = 10  # Hz
ID = 38
URI = 'radio://0/100/2M/E7E7E7E704'
pos = None
current_waypoints = []
recording = False
lock = Lock()
monitor = NatNetRigidBodyMonitor()

#for pynput
is_typing = False
require_input = threading.Event()

# SETUP PLANNING
print("\n--- Initializing Flight Systems ---")
planner = TrajectoryPlanner(altitude=1.0, sample_rate=100)
ideal_trajectory = planner.generate_circle(radius=1.5)
reference_file = save_dir / 'ideal_circle_reference.csv'
#planner.export_to_csv(ideal_trajectory, reference_file)
# place for future evaluator
cage = VirtualCage(x_bounds=(-3.0, 3.0), y_bounds=(-3.0, 3.0), z_bounds=(0.0, 3.0))
print("--- Systems Ready ---\n")
# ---------------------------------------------

def get_average_position(monitor, rigid_body_id, update_rate=UPDATE_RATE):
    """Gets the average position of a rigid body over multiple samples"""
    sum_x, sum_y, sum_z = 0.0, 0.0, 0.0
    count = 0
    start_time = time.time()

    while time.time() - start_time < 1.0 / update_rate:
        sample = monitor.get_position(rigid_body_id)
        if sample is not None:
            sum_x += sample[0]
            sum_y += sample[1]
            sum_z += sample[2]
            count += 1
        time.sleep(1.0 / MOCAP_TX_RATE_HZ)

    if count > 0:
        return (sum_x / count, sum_y / count, sum_z / count)
    return None


def object_tracking(monitor, rigid_body_id):
    """Background thread for tracking, cage checks"""
    global pos, current_waypoints, recording

    while True:
        current_pos = get_average_position(monitor, rigid_body_id)
        if current_pos is not None:
            #accuracy check e.g. score = evaluator.evaluate(current_pos)
            with lock:
                pos = current_pos
                if recording:
                    current_waypoints.append(current_pos)
                    print(f"Recorded: {current_pos}")


def create_trajectory(calculator: Trajectory, list_of_pos, no_yaw=False) -> list:
    """Converts numpy coordinates to state objects"""
    return [
        calculator.get_position(
            x=item[0], y=item[1], z=item[2],
            yaw=(item[3] if len(item) > 3 and not no_yaw else 0),
            pitch=0, roll=0
        ) for item in list_of_pos
    ]


def update_filename_path():
    """Prompts user to update the active filename"""
    global filename, is_typing
    is_typing = True
    save_filename = input('\nFilename: ').lower().strip().replace(' ', '_')
    if save_filename != '':
        filename = save_dir / f'{save_filename}.csv'
    else:
        filename = None
        print('Error setting filename.')

    is_typing = False

def get_input(text):
    """Prompts user to update the active filename"""
    global is_typing
    is_typing = True
    try:
        user = input(f'\n{text}: ').lower().strip()
    finally:
        is_typing = False
    return user

def on_press(key):
    """Handles all keyboard inputs during operation"""
    global recording, filename, current_waypoints, monitor,is_typing

    if is_typing:   return

    try:
        if key.char == 'u':
            require_input.set()

        elif key.char == 's':
            if filename is None: update_filename_path()
            print("\nSTART recording")
            current_waypoints = []
            recording = True if filename is not None else False

        elif key.char == 'e':
            if recording:
                recording = False
                print("\nSTOP recording")
                print('Saving...')
                save_waypoints(current_waypoints, filename)

        elif key.char == 'm':
            if filename is None: update_filename_path()
            plot_waypoints([load_waypoints(filename)])

        elif key.char == 'q':
            if filename is None: update_filename_path()

            raw = load_waypoints(filename)
            traj_yaw = add_yaw(filter_waypoints(raw,threshold=0.2,min_height=0.5), make_smooth=True)
            print(f'\nOld # of points: {len(raw)}, new filtered: {len(traj_yaw)}')
            processed_file = processed_dir / filename.name
            save_waypoints(traj_yaw, processed_file)
            plot_waypoints(trajectory=[raw, traj_yaw], labels=['raw','with yaw'])

        elif key.char == 'f':
            if filename is None or not filename.exists():
                update_filename_path()
                processed_file = processed_dir / filename.name

                if processed_file.exists():
                    print(f"\nLoading from: {processed_file}")
                    file_to_load = processed_file
                elif filename.exists():
                    print(f"\nLoading raw original from: {filename}")
                    file_to_load = filename
                else:
                    print(f"\nError: Could not find {filename.name}")
                    return
            else: file_to_load=filename
            # LOADING TRAJECTORY ------------
            print(f"\nLoading trajectory from: {file_to_load.name}")
            raw_waypoints = load_waypoints(file_to_load)

            if raw_waypoints.shape[1] >= 4:
                print("Trajectory is already processed (has yaw). Skipping filter.")
                enhanced_waypoints = raw_waypoints
            else:
                print("Processing raw trajectory for flight...")
                enhanced_waypoints = add_yaw(filter_waypoints(raw_waypoints, cage=cage), make_smooth=True)

            print(f"Total Trajectory points: {len(enhanced_waypoints)}")

            # CHECK TRAJECTORY BEFORE FLYING -----------
            calculator = Trajectory()
            calculator.logging(enable=False, file=False, level=calculator.LogLevel.debug)
            calculator.set_count(1)

            positions = create_trajectory(calculator, enhanced_waypoints.tolist(), no_yaw=False)
            
            plot_waypoints(positions, calculator=calculator)
         

            # FLYING LOOP -----------
            #toFly = get_input('Check trajectory. Enter "y" to continue: ')
            # toFly = input('\nCheck trajectory. Enter "y" to continue: ').lower().strip()

            # if toFly == 'y':
            #     is_typing = True
            #     print('Starting flight...')

            cf = CrazyFlie()
            cf.logging(enable=True, file=True, level=base.LogLevel.debug)
            cf.set_natnet_monitor(monitor)

            try:
                cf.scan(specific=URI)
                cf.connect(start_flying=True)
                for pos_state in positions:
                    cf.fly(pos_state)
                    while not cf.arrived(pos_state):
                        time.sleep(0.1)
                    time.sleep(0.2)
                cf.land()
            except (bitcraze.CrazyFlieError, KeyboardInterrupt):
                print("\nFlight interrupted.")
            finally:
                cf.disconnect()
                is_typing = False

    except AttributeError:
        pass


def main():
    global monitor
    monitor.start()

    tracker = Thread(target=object_tracking, args=(monitor, ID), daemon=True)
    tracker.start()

    time.sleep(2)
    update_filename_path()

    print("""
    LISTENING FOR KEYBOARD COMMANDS:
      [u] - Update filename (Pauses hotkeys to type)
      [s] - Start recording trajectory
      [e] - Stop recording & save to CSV
      [m] - Map/Plot the trajectory in 3D
      [q] - Smooth recorded trajectory, add yaw & save
      [f] - Fly the currently loaded trajectory
    """)
    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    try:
        while True:
            if require_input.is_set():
                update_filename_path()
                require_input.clear()

            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nExiting program...")


if __name__ == '__main__':
    main()