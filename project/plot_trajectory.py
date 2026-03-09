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
""" -> remove repeated and close points"""
def filter_points(trajectory, threshold=0.001):
    new_trajectory = [trajectory[0]]
    for point in trajectory[1:]:
        prev = new_trajectory[-1]
        if np.linalg.norm(prev - point) >= threshold:  # keep only far enough points
            new_trajectory.append(point)
    return np.array(new_trajectory)

""" -> smooth by moving average"""
def smooth_path(trajectory, window_size=3):
    smoothed = np.copy(trajectory)
    for i in range(trajectory.shape[0]):
        start = max(0, i - window_size + 1)
        smoothed[i] = np.mean(trajectory[start:i + 1], axis=0)
    return smoothed

""" -> add yaw vector"""
def add_yaw(trajectory, smooth_window=8, min_dist=0.01,make_smooth=False) -> np.ndarray:
    dx = np.diff(trajectory[:, 0])
    dy = np.diff(trajectory[:, 1])

    yaw_rad = np.arctan2(dy, dx) #raw yaw in rad

    dist_2d = np.hypot(dx, dy)
    # remove noise at the beginning
    if dist_2d[0] < min_dist:   yaw_rad[0] = 0.0

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
    filename = Path(__file__).resolve().parents[0] / 'trajectories' / 'test_trajectory.csv'
    #plot_trajectory(filename)

    # Load raw trajectory
    trajectory_points = pd.read_csv(filename)[['x','y','z']].to_numpy()
    # Filter trajectory + optimise # of points
    trajectory_filtered = filter_points(trajectory_points, threshold=0.1)
    trajectory_smoothed = smooth_path(trajectory_filtered)

    plot_trajectory(trajectory=[trajectory_points, trajectory_filtered])
    plot_trajectory(trajectory=[trajectory_filtered, trajectory_smoothed])

    print(f'Old # of points: {len(trajectory_points)}, new filtered: {len(trajectory_filtered)}, new filtered + smoothed: {len(trajectory_smoothed)}')

    #check new func to add yaw
    traj_yaw = add_yaw(trajectory_smoothed)
    plot_trajectory(trajectory=[ traj_yaw,add_yaw(trajectory_smoothed,make_smooth=True)])

if __name__ == '__main__':
    main()