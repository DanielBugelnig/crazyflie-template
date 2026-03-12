"""
This script reads trajectories from OptiTrack

Usage:
1. Enter a trajectory name
2. Press 's' to start recording the trajectory
3. Press 'e' to stop recording
4. Press 'p' to save the recorded trajectory to a CSV file
5. Press 'm' to plot the trajectory in 3D
'u' enter filepath
'f' fly
"""

import csv, os, sys, time
from pathlib import Path
from threading import Lock, Thread

import pandas as pd
from matplotlib import pyplot as plt
from pynput import keyboard

sys.path.append(str(Path(__file__).resolve().parents[1]))

from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor
import crazyflie.core.base_utils as base
from crazyflie import bitcraze
from crazyflie.bitcraze.trajectory import Trajectory
from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.constants import MOCAP_TX_RATE_HZ

from test_plot_trajectory import plot_waypoints, filter_waypoints, load_waypoints,add_yaw,save_waypoints_2
 

def save_waypoints():
    global current_waypoints,filename
    print(filename)

    

    if len(current_waypoints) == 0:
        print("No trajectory to save")
        return

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["x", "y", "z"])
        for p in current_waypoints:
            writer.writerow(p)

    print(f"Trajectory saved to {filename}")

    # if len(trajectory_way_points) == 0:
    #     print("No trajectory to save")
    #     return
    
    # elif filename is None:
    #     save_filename = input('\nFilename: ').lower().strip().replace(' ', '_')
    #     if save_filename != '':
    #         filename = save_dir / f'{save_filename}.csv'
    #     else:
    #         filename=None
    #         print('Error')

    # with open(filename, "w", newline="") as f:
    #     writer = csv.writer(f)
        

    #     if trajectory_way_points[1].shape ==4:
    #         writer.writerow(["x", "y", "z","yaw"])
    #     else:
    #         writer.writerow(["x", "y", "z"])
    #     for p in trajectory_way_points:
    #         writer.writerow(p)

    # print(f"Trajectory saved to {filename}")

# Paths
base_path = Path(__file__).resolve().parents[0]
save_dir = base_path / 'trajectories'
os.makedirs(save_dir, exist_ok=True)
filename = None

# Constants
OFFSET_X = 1  # m
UPDATE_RATE = 10  # Hz
ID = 38
pos = None
current_waypoints = []
user = ''

recording = False
lock = Lock()
monitor = NatNetRigidBodyMonitor()

def get_average_position(monitor, rigid_body_id, update_rate=UPDATE_RATE):
    """
    Get the average position of a rigid body over multiple samples.

    Args:
        monitor: NatNetRigidBodyMonitor instance
        rigid_body_id: Rigid body ID to track
        samples: Number of samples to average (default: 100)
        interval: Time interval between samples in seconds (default: 0.01)
        Update_Rate: Update rate in Hz (default: 10)

    Returns:
        tuple: (x, y, z) mean position, or None if no valid positions received
    """
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
        # print(f"Position from NatNet RB {rigid_body_id}: {pos}, type {type(pos)}")

    if count > 0:
        mean_pos = (sum_x / count, sum_y / count, sum_z / count)
        # print(f"\nMean position over {count} samples: {mean_pos}")
        return mean_pos
    else:
        print("\nNo valid positions received")
        return None


def object_tracking(monitor, rigid_body_id):
    global pos, current_waypoints, recording

    while True:
        current_pos = get_average_position(monitor, rigid_body_id)

        if current_pos is not None:
            with lock:
                pos = current_pos
                if recording:
                    current_waypoints.append(current_pos)
                    print("Recorded:", current_pos)


def create_trajectory(calculator: Trajectory, list_of_pos, no_yaw=False) -> list:
    return [
        calculator.get_position(
            x=item[0],
            y=item[1],
            z=item[2],
            yaw=(item[3] if len(item) > 3 and not no_yaw else 0),
            pitch=0,
            roll=0
        )
        for item in list_of_pos
    ]

def on_press(key):
    global recording, filename, current_waypoints, monitor

    try:
        if key.char == 'u':
            update_filename_path()

        elif key.char == 's':
            if filename is None: update_filename_path()

            print("START recording")
            current_waypoints = []
            recording = True if filename is not None else False

        if key.char == 'e':
            if recording == True:
                recording = False
                print("STOP recording")
                print("Trajectory:", current_waypoints)
                print('            Saving')
                save_waypoints()
                
        elif key.char == 'm':
            if filename is None:
                update_filename_path()
            plot_waypoints(filename=filename)

        elif key.char == 'q':
            if filename is None:
                update_filename_path()
            
            raw = load_waypoints(filename)
            print(raw)

            trajectory_smoothed = filter_waypoints(raw)
            traj_yaw = add_yaw(trajectory_smoothed)

            print(f'Old # of points: {len(raw)}, new filtered: {len(traj_yaw)}')
            
            save_waypoints_2(traj_yaw, 'test_traj_save.csv')
            plot_waypoints(trajectory=[traj_yaw], labels=['with yaw'])


        elif key.char == 'f':
         

            # Ask user for file if not set
            if filename is None or not filename.exists():
                update_filename_path()
                if filename is None or not filename.exists():
                    print("No valid trajectory file selected.")
                    return

            print(f"\nLoading trajectory from: {filename}")

            # Load, filter, and add yaw
            raw_waypoints = load_waypoints(filename)
            filtered_waypoints = filter_waypoints(raw_waypoints)
            enhanced_waypoints = add_yaw(filtered_waypoints, make_smooth=True)

            print(f"Trajectory points: {len(enhanced_waypoints)}")

            # Create Crazyflie objects
            cf = CrazyFlie()
            cf.logging(enable=True, file=True, level=base.LogLevel.debug)
            cf.set_natnet_monitor(monitor)

            calculator = Trajectory()
            calculator.logging(enable=False, file=False, level=calculator.LogLevel.message)
            calculator.set_count(1)

            # Create trajectory State objects
            positions = create_trajectory(calculator, enhanced_waypoints.tolist(), no_yaw=False)

            # Plot safely in main thread
            #Thread(target=plot_waypoints, kwargs={'trajectory': positions, 'calculator': calculator}).start()

            # Ask user if they want to fly
            # answer = input("Fly this trajectory? (y/n): ").strip().lower()
            # if answer != 'y':
            #     print("Trajectory not flown.")
            #     return

            # Fly trajectory
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
                    
        # elif key.char == 'f':
        #     if filename is None: update_filename_path()

        #     print(filename)
        #     raw_waypoints = load_waypoints(filename)
        #     enhanced_waypoints = add_yaw(filter_waypoints(raw_waypoints), make_smooth=True)

        #     #add for flying
        #     cf = CrazyFlie()
        #     cf.logging(enable=True, file=True, level=base.LogLevel.debug)
        #     cf.set_natnet_monitor(monitor)

        #     calculator = Trajectory()
        #     calculator.logging(enable=False, file=False, level=calculator.LogLevel.message)
        #     calculator.set_count(1)  # amount of CF

        #     positions = create_trajectory(calculator, enhanced_waypoints.tolist(),no_yaw=False)
        #     plot_waypoints(positions)

        #     if input('Check if continue Y or N: ').lower().strip() == 'y':
        #         try:
        #             cf.scan()  # scan for drones
        #             cf.connect(start_flying=True)
        #             for position in positions:
        #                 cf.fly(position)
        #                 while not cf.arrived(position):
        #                     time.sleep(0.1)
        #                 time.sleep(0.2)
        #             cf.land()
        #         except (bitcraze.CrazyFlieError, KeyboardInterrupt):
        #             pass
        #         cf.disconnect()

    except AttributeError:
        pass


def update_filename_path():
    global filename

    save_filename = input('\nFilename: ').lower().strip().replace(' ', '_')
    if save_filename != '':
        filename = save_dir / f'{save_filename}.csv'
    else:
        filename=None
        print('Error')


def main():
    global filename, monitor
    monitor.start()

    tracker = Thread(target=object_tracking, args=(monitor, ID), daemon=True)
    tracker.start()

    time.sleep(2)
    update_filename_path()

    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    listener.join()


if __name__ == '__main__':
    main()