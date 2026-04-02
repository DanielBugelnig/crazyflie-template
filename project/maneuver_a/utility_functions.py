"""
This module provides utility functions for plotting, saving and loading trajectories for the Maneuvers A
"""

import csv, numpy as np, pandas as pd
from pathlib import Path
from matplotlib import pyplot as plt
from math import sin, cos, radians


def plot_waypoints(trajectory: list[np.ndarray], labels: list[str] = None):
    """
    Generates a 3D plot for one or more trajectories

    Args:
        trajectory (list[np.ndarray]): A list of numpy arrays, each representing a trajectory
        labels (list[str], optional): A list of labels for the legend
    """
    plt.figure(figsize=(10, 8))
    ax = plt.axes(projection="3d")
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.set_zlabel("Z [m]")

    #handle labels
    num_trajectories = len(trajectory)
    if labels is None:
        labels = [f"Trajectory {i + 1}" for i in range(num_trajectories)]

    #handle colors
    cmap = plt.get_cmap('tab10')
    colors = [cmap(i % 10) for i in range(num_trajectories)]

    for i, traj in enumerate(trajectory):
        if traj is None or traj.shape[0] == 0:  continue

        #plot trajectory
        ax.plot(traj[:, 0], traj[:, 1], traj[:, 2], '-o', markersize=3, color=colors[i], label=labels[i])
        ax.scatter(traj[0, 0], traj[0, 1], traj[0, 2], color='green', s=100, label=f'Start {labels[i]}')
        ax.scatter(traj[-1, 0], traj[-1, 1], traj[-1, 2], color='red', s=100, label=f'End {labels[i]}')

        #plot yaw
        if traj.shape[1] >= 4:
            for j in range(0, len(traj), 5):  # Skip points for clarity
                u = 0.1 * cos(radians(traj[j, 3]))
                v = 0.1 * sin(radians(traj[j, 3]))
                ax.quiver(traj[j, 0], traj[j, 1], traj[j, 2], u, v, 0, color=colors[i], length=0.1, normalize=True)
    ax.legend()
    plt.show()


def load_waypoints(filename: Path) -> np.ndarray | None:
    """
    Loads a trajectory from a CSV file

    Args:
        filename (Path): The absolute path to the CSV file

    Returns:
        np.ndarray: The loaded trajectory as a numpy array, or None if loading fails
    """
    if not filename.exists():
        print(f"File not found: {filename}")
        return None
    try:
        df = pd.read_csv(filename)
        required_cols = ['x', 'y', 'z']

        #check if valid trajectory
        if not all(col in df.columns for col in required_cols):
            print(f"CSV file {filename} is missing one of the required columns: {required_cols}")
            return None
        return df[required_cols].to_numpy()
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return None


def save_waypoints(trajectory: np.ndarray, filename: Path):
    """
    Saves a trajectory to a CSV file

    Args:
        trajectory (np.ndarray): The trajectory data to save.
        filename (Path): The absolute path where the file should be saved.
    """
    if trajectory is None or len(trajectory) == 0:
        print("No trajectory data to save.")
        return

    filename.parent.mkdir(parents=True, exist_ok=True)

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        #handle heading for raw trajectory and enhanced one
        header = ["x", "y", "z", "yaw"] if trajectory.shape[1] >= 4 else ["x", "y", "z"]
        writer.writerow(header)
        writer.writerows(trajectory)

    print(f"Trajectory successfully saved to {filename}")


if __name__ == "__main__":
    traj_8 = load_waypoints(Path(__file__).parent / "trajectories" / "traj_8_recorded.csv") 
    for pos in traj_8:
        pos[2]=0

    plot_waypoints([traj_8])