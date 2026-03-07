"""
This script reads trajectories from OptiTrack

Usage:
1. Enter a trajectory name
2. Press 's' to start recording the trajectory
3. Press 'e' to stop recording
4. Press 'p' to save the recorded trajectory to a CSV file
5. Press 'm' to plot the trajectory in 3D
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
from crazyflie.core.shared_data import State
from crazyflie.constants import MOCAP_TX_RATE_HZ

#two custom functions for plotting
from plot_trajectory import visualise_planned_path_3D, plot_trajectory

# Paths
base_path = Path(__file__).resolve().parents[0]
save_dir = base_path / 'trajectories'
os.makedirs(save_dir, exist_ok=True)
filename = ''

# Constants
OFFSET_X = 1  # m
UPDATE_RATE = 10  # Hz
ID = 13
pos = None
trajectory_way_points = []
user = ''

recording = False
lock = Lock()


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
    global pos, trajectory_way_points, recording

    while True:
        current_pos = get_average_position(monitor, rigid_body_id)

        if current_pos is not None:
            with lock:
                pos = current_pos
                if recording:
                    trajectory_way_points.append(current_pos)
                    print("Recorded:", current_pos)


def on_press(key):
    global recording, trajectory_way_points, user
    try:
        if key.char == 's':
            print("START recording")
            trajectory_way_points = []
            recording = True

        if key.char == 'e':
            recording = False
            print("STOP recording")
            print("Trajectory:", trajectory_way_points)

        elif key.char == 'p':
            save_trajectory()
        elif key.char == 'm':
            plot_trajectory(filename)

    except AttributeError:
        pass


def save_trajectory():
    global trajectory_way_points

    if len(trajectory_way_points) == 0:
        print("No trajectory to save")
        return

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["x", "y", "z"])
        for p in trajectory_way_points:
            writer.writerow(p)

    print(f"Trajectory saved to {filename}")


def main():
    global user, filename
    monitor = NatNetRigidBodyMonitor()
    monitor.start()

    time.sleep(5)
    user = input('\nFilename: ').lower().strip().replace(' ', '_')
    filename = save_dir / f'{user}.csv'

    tracker = Thread(target=object_tracking, args=(monitor, ID), daemon=True)
    tracker.start()

    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    listener.join()


if __name__ == '__main__':
    main()
    #plot_trajectory('project/trajectories/test_trajectory.csv')