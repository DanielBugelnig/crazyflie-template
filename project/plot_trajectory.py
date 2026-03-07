"""
Script that plots trajectory + an option to filter points and smooth them afterward
Possible to try on two recorded trajectories:
    filename = Path(__file__).resolve().parents[0] / 'trajectories' / 'test_trajectory.csv'
    filename = Path(__file__).resolve().parents[0] / 'trajectories' / 'test_trajectory_2.csv'
"""

import numpy as np
from matplotlib import pyplot as plt
import pandas as pd

from pathlib import Path


def visualise_planned_path_3D(trajectories):
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


def main():
    filename = Path(__file__).resolve().parents[0] / 'trajectories' / 'test_trajectory_2.csv'
    #plot_trajectory(filename)

    # Load raw trajectory
    trajectory_points = pd.read_csv(filename)[['x','y','z']].to_numpy()
    # Filter trajectory + optimise # of points
    trajectory_filtered = filter_points(trajectory_points, threshold=0.1)
    trajectory_smoothed = smooth_path(trajectory_filtered)

    plot_trajectory(trajectory=[trajectory_points, trajectory_filtered])
    plot_trajectory(trajectory=[trajectory_filtered, trajectory_smoothed])

    print(f'Old # of points: {len(trajectory_points)}, new filtered: {len(trajectory_filtered)}, new filtered + smoothed: {len(trajectory_smoothed)}')


if __name__ == '__main__':
    main()