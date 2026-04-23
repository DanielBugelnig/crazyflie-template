"""
Handles the recording of trajectories using the OptiTrack system

Usage:
'u' - update filename
's' - start recording
'e' - stop recording & save
'q' - exit
"""

# Standard libraries import
import os, sys, time, traceback
from pathlib import Path
from threading import Lock, Thread

# Frameworks (!needs to be installed)
import numpy as np
from pynput import keyboard
from pynput.keyboard import Key

# Modifying system path to import 'crazyflie' package
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:   sys.path.insert(0, str(ROOT))

# Specific imports for OptiTrack usage
from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor
from crazyflie.constants import MOCAP_TX_RATE_HZ

# Local modules imports
from s02_scoring import AccuracyEvaluator, resample_trajectory              #Evaluates the accuracy of a recorded trajectory against a predefined ideal path
from utils import plot_waypoints, save_waypoints, prompt_for_filename       #Contains utility functions for plotting, file I/O, and other common tasks


#----------- CONFIG BEFORE USAGE --------------
UPDATE_RATE = 10                    #Hz for averaging
ID = 44                             #wand rigid body ID
MIN_RECORDING_DIST = 0.05           #controls dist between points that will be recorded (prev-current) -> set 0 to store all points from Optitrack

#formula for ideal trajectory
t = np.linspace(0, 2 * np.pi, 100)
A, B, Z0 = 1.0, 2.0, 0.0
ideal_trajectory = np.column_stack((A * np.sin(t), B * np.sin(t) * np.cos(t), np.ones_like(t) * Z0))

#for evaluation
scale = 0.5             #e.g. score=50% exactly at scale 0.5 m
alpha = 0.5             #a higher value gives more weight to the current raw score
#----------------------------------------------


# Setup - - - - - - - - - - - - - - - - -
# >>> Directories
#to save raw recorded trajectories
save_dir = Path(__file__).resolve().parent / 'data'/ 'recorded_trajectories'
processed_dir = Path(__file__).resolve().parent / 'data' / 'processed_trajectories'

os.makedirs(save_dir, exist_ok=True)
os.makedirs(processed_dir, exist_ok=True)

save_filename = None # !includes file extension '.csv'

# >>> Constants
pos, current_waypoints = None, []
lock = Lock()   #for safe storing/accessing waypoints in threads
monitor = NatNetRigidBodyMonitor()

# >>> Flags
is_typing, shutdown_flag, recording = False, False, False

# >>> Accuracy scoring
evaluator = AccuracyEvaluator(ideal_trajectory=ideal_trajectory, scale=scale, alpha=alpha)
# - - - - - - - - - - - - - - - - - - - - - - -


def main():
    global is_typing, save_filename

    # Setup OptiTrack
    monitor.start()

    # Setup tracking thread
    tracker = Thread(target=object_tracking, args=(monitor, ID), daemon=True)
    tracker.start()
    time.sleep(2)

    # Ask user for trajectory name
    save_filename = prompt_for_filename(save_dir, processed_dir)

    # Setup keyboard listener
    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    print("\n- - - - - - Demo A Started - - - - - -")
    print("Controls: [s]tart recording, [e]nd/save, [u]pdate filename, [q]uit")
    try:
        while not shutdown_flag:
            if is_typing: #to take input from user out of keyboard listener thread
                save_filename = prompt_for_filename(save_dir, processed_dir)
                is_typing = False
            time.sleep(0.1) #refresh time

    except KeyboardInterrupt:
        print("\nExiting program...")

    except Exception as e:
        print(f"\n[ERROR] An unexpected mistake occurred: {e}")
        print("\nDetailed breakdown:")
        traceback.print_exc()

    finally:
        print('Pressed "q" -> exit')
        listener.stop()
        print("Demo A has been shut down.")


def on_press(key:Key):
    """Handles all keyboard inputs during operation"""
    global recording, current_waypoints, is_typing, shutdown_flag

    if is_typing:   return

    try:
        if key.char == 'u': is_typing = True

        elif key.char == 's':
            if save_filename is None:
                print('\nEnter save_filename first and then press "s" again!')
                is_typing = True
            else:
                print("\nSTART recording")
                with lock:
                    current_waypoints.clear()
                    recording = True

        elif key.char == 'e':
            if not recording:
                print('Press "s" to start recording')
            else:
                print("\nSTOP recording")

                with lock:
                    recording = False
                    waypoints_copy = current_waypoints.copy()

                # In case of invalid trajectory
                if not waypoints_copy:
                    print('Error: No waypoints were recorded!')
                    return

                print('Saving...')
                save_waypoints(waypoints_copy, save_dir / save_filename)

                # Plot of raw trajectory from optitrack
                plot_waypoints([np.array(waypoints_copy)], labels=['Raw trajectory'])

                #- - - - Accuracy - - - - - - - - - - -
                print('Evaluating accuracy...')
                #Process the whole trajectory at once
                avg_dist, final_score, scores, new_recorded_points = evaluator.evaluate_full_trajectory(resample_trajectory(waypoints_copy))
                print(f"\n- - - - - - FLIGHT SUMMARY - - - - - -")
                print(f"Average Distance Error: {avg_dist:.3f} meters")
                print(f"Final Accuracy Score:   {final_score:.2f}%")
                print(f"- - - - - - - - - - - - - - - - - - - \n")

                # Plot the results in 3D with the scores
                evaluator.plot_results(new_recorded_points, scores, final_score)
                #- - - - - - - - - - - - - - -

        elif key.char =='q':
            shutdown_flag = True
            return False

    except AttributeError:
        pass


#------- OPTITRACK LOCATION
def get_average_position(monitor:NatNetRigidBodyMonitor, rigid_body_id:int, update_rate:int=UPDATE_RATE):
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


def object_tracking(monitor:NatNetRigidBodyMonitor, rigid_body_id:int):
    """Background thread for tracking, cage checks"""
    global pos, current_waypoints, recording
    while True:
        current_pos = get_average_position(monitor, rigid_body_id)
        if current_pos is not None:
            with lock:
                pos = current_pos
                if recording:
                    #If list is empty, OR distance threshold is met
                    if not current_waypoints or np.linalg.norm(
                            np.array(current_pos) - np.array(current_waypoints[-1])) >= MIN_RECORDING_DIST:
                        current_waypoints.append(current_pos)
                        # Accuracy scoring
                        raw, smooth, dist_err, closest = evaluator.get_instantaneous_accuracy(current_pos)
                        print(f"Point {len(current_waypoints)} | Score: {smooth:.1f}% | Error: {dist_err:.2f}m")


if __name__ == '__main__':
    main()