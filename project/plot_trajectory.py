"""
Script that plots trajectory + an option to filter points and smooth them afterward
Possible to try on two recorded trajectories:
    filename = Path(__file__).resolve().parents[0] / 'trajectories' / 'test_trajectory.csv'
    filename = Path(__file__).resolve().parents[0] / 'trajectories' / 'test_trajectory_2.csv'
"""

import numpy as np
from matplotlib import pyplot as plt
import pandas as pd
from math import sin,cos,radians

from pathlib import Path


def visualise_planned_path_3D(trajectories:list[np.ndarray]) -> None:
    plt.figure(figsize=(10, 8))

    ax = plt.axes(projection="3d")
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.set_zlabel("Z [m]")

    n = len(trajectories)
    labels = [f"Trajectory {i + 1}" for i in range(n)]

    cmap = plt.get_cmap('tab10')
    colors = [cmap(i % 10) for i in range(n)]

    for i, traj in enumerate(trajectories):

        traj = add_yaw(filter_waypoints(traj))
       
        ax.plot(traj[:, 0], traj[:, 1], traj[:, 2], '-o', markersize=3, color=colors[i], label=labels[i])
        ax.scatter(traj[:, 0], traj[:, 1], traj[:, 2], color=colors[i], s=10, alpha=0.3)

        #for plotting yaw
        if traj.shape[1] >= 4:
            skip_step = 1#2
            for j in range(0, len(traj[:, 0]), skip_step):
                u = 0.1 * cos(radians(traj[:, 3][j]))
                v = 0.1 * sin(radians(traj[:, 3][j]))
                ax.quiver(traj[:, 0][j], traj[:, 1][j], traj[:, 2][j], u, v, 0, color=colors[i], length=0.1, normalize=True)

    ax.legend()
    plt.show()


def plot_trajectory(filename=None, trajectory=None):
    if trajectory is None: trajectory = [pd.read_csv(filename)[['x','y','z']].to_numpy()]
    visualise_planned_path_3D(trajectory)


#to smooth trajectory
def filter_waypoints(trajectory, threshold=0.1, window_size=3, min_height=0.2):
    trajectory = np.asarray(trajectory)
    if len(trajectory) == 0:
        return trajectory

    # close points
    filtered = [trajectory[0]]
    for p in trajectory[1:]:
        if np.linalg.norm(p - filtered[-1]) >= threshold:
            filtered.append(p)
    filtered = np.array(filtered)

    # smooth 
    smoothed = np.copy(filtered)
    half_w = window_size // 2

    for i in range(len(filtered)):
        start = max(0, i - half_w)
        end = min(len(filtered), i + half_w + 1)
        smoothed[i] = np.mean(filtered[start:end], axis=0)

    # height handling
    smoothed[:, 2] = np.maximum(smoothed[:, 2], min_height)
    smoothed[0, 2] = min_height
    return smoothed

""" -> add yaw vector"""
def add_yaw(trajectory, smooth_window=8, min_dist=0.01,make_smooth=False, min_height=0.4) -> np.ndarray:
    dx = np.diff(trajectory[:, 0])
    dy = np.diff(trajectory[:, 1])

    yaw_rad = np.arctan2(dy, dx) #raw yaw in rad
    dist_2d = np.hypot(dx, dy)

    # fix vertical drops
    for i in range(1, len(yaw_rad)):
        if dist_2d[i] < min_dist:   yaw_rad[i] = yaw_rad[i - 1] #if movement really tiny -> take previous yaw

    # fix possible 360-degree jumps
    yaw_rad = np.unwrap(yaw_rad)

    # ADDITIONAL SMOOTHNESS
    if make_smooth and smooth_window > 1:
        pad = smooth_window // 2
        padded_yaw = np.pad(yaw_rad, (pad, pad), mode='edge') #prevent crashing at the boundaries
        window_filter = np.ones(smooth_window) / smooth_window # create kernel/window, if smooth_window 5 then 1D array size 1 multiplied by 1/5 = 20%
        yaw_rad = np.convolve(padded_yaw, window_filter, mode='valid') #sliding window + actual convolution

    yaw_deg = np.degrees(yaw_rad)
    yaw_deg = np.append(yaw_deg, yaw_deg[-1])

    traj_with_yaw = np.column_stack((trajectory, yaw_deg[:len(trajectory)])) #add as additional column
    return traj_with_yaw


def main():
    filename = Path(__file__).resolve().parents[0] / 'trajectories' / 'testing.csv'
    #plot_trajectory(filename)

    # Load raw trajectory
    trajectory_points = pd.read_csv(filename)[['x','y','z']].to_numpy()

    plot_trajectory(trajectory=[trajectory_points])
 

if __name__ == '__main__':
    main()