import numpy as np, pandas as pd, csv, os
from math import sin, cos, radians, pi
from matplotlib import pyplot as plt
from pathlib import Path

from project.drafts.test_plot_trajectory import add_yaw
from safety_scoring import VirtualCage

#OFFLINE PLANNING
class TrajectoryPlanner:
    """Handles the offline generation of ideal flight paths"""
    def __init__(self, altitude, sample_rate=50):
        self.altitude = altitude
        self.sample_rate = sample_rate

    def _calculate_yaw(self, x, y):
        dx = np.diff(x)
        dy = np.diff(y)
        yaw_rad = np.arctan2(dy, dx)
        yaw_deg = np.degrees(yaw_rad)
        yaw_deg = np.append(yaw_deg, yaw_deg[-1]) #to match array size
        return yaw_deg

    def generate_circle(self, radius):
        t = np.linspace(0, 2 * pi, self.sample_rate)
        x = radius * np.cos(t)
        y = radius * np.sin(t)
        z = np.full_like(x, self.altitude)
        yaw = self._calculate_yaw(x, y)
        return np.column_stack((x, y, z, yaw))



#REAL TRAJECTORY FILTERING
def filter_waypoints(trajectory, threshold=0.1, window_size=3, min_height=0.2, cage:VirtualCage=None):
    trajectory = np.asarray(trajectory)
    if len(trajectory) == 0: return trajectory

    #remove points that are too close
    filtered = [trajectory[0]]
    for p in trajectory[1:]:
        if np.linalg.norm(p - filtered[-1]) >= threshold:
            filtered.append(p)
    filtered = np.array(filtered)
    print(f'Filtered {len(trajectory) - len(filtered)} points')

    #smoothing by moving average
    smoothed = np.copy(filtered)
    half_w = window_size // 2
    for i in range(len(filtered)):
        start = max(0, i - half_w)
        end = min(len(filtered), i + half_w + 1)
        smoothed[i] = np.mean(filtered[start:end], axis=0)

    #enforce min height
    current_min_z = np.min(smoothed[:, 2])
    if current_min_z < min_height:
        z_offset = min_height - current_min_z
        smoothed[:, 2] += z_offset #lift entire trajectory

    #safe cage
    if cage is not None:
        smoothed[:, 0] = np.clip(smoothed[:, 0], cage.x_min, cage.x_max)  #Left/Right limits
        smoothed[:, 1] = np.clip(smoothed[:, 1], cage.y_min, cage.y_max)  #Forward/Back limits
        smoothed[:, 2] = np.clip(smoothed[:, 2], min_height, cage.z_max)  #Min/Max height limits
    return smoothed


def add_yaw(trajectory, smooth_window=8, min_dist=0.01, make_smooth=False) -> np.ndarray:
    dx = np.diff(trajectory[:, 0])
    dy = np.diff(trajectory[:, 1])
    yaw_rad = np.arctan2(dy, dx)

    #fix yaw in vertical parts
    dist_2d = np.hypot(dx, dy)
    for i in range(1, len(yaw_rad)):
        if dist_2d[i] < min_dist: yaw_rad[i] = yaw_rad[i - 1]

    yaw_rad = np.unwrap(yaw_rad) #fix angles
    #smooth yaw
    if make_smooth and smooth_window > 1:
        pad = smooth_window // 2
        padded_yaw = np.pad(yaw_rad, (pad, pad), mode='edge')
        window_filter = np.ones(smooth_window) / smooth_window
        yaw_rad = np.convolve(padded_yaw, window_filter, mode='valid')

    yaw_deg = np.degrees(yaw_rad)
    yaw_deg = np.append(yaw_deg, yaw_deg[-1])
    return np.column_stack((trajectory, yaw_deg[:len(trajectory)]))


#PLOTTING
def _planned_path(trajectories: list[np.ndarray], labels) -> None:
    plt.figure(figsize=(10, 8))
    ax = plt.axes(projection="3d")
    ax.set_xlabel("X [m]");
    ax.set_ylabel("Y [m]");
    ax.set_zlabel("Z [m]")

    n = len(trajectories)
    labels = [f"Trajectory {i + 1}" for i in range(n)] if labels is None else labels
    cmap = plt.get_cmap('tab10')
    colors = [cmap(i % 10) for i in range(n)]

    for i, traj in enumerate(trajectories):
        ax.plot(traj[:, 0], traj[:, 1], traj[:, 2], '-o', markersize=3, color=colors[i], label=labels[i])
        ax.scatter(traj[:, 0], traj[:, 1], traj[:, 2], color=colors[i], s=10, alpha=0.3)
        if traj.shape[1] >= 4:
            for j in range(0, len(traj[:, 0]), 1):
                u = 0.1 * cos(radians(traj[:, 3][j]))
                v = 0.1 * sin(radians(traj[:, 3][j]))
                ax.quiver(traj[:, 0][j], traj[:, 1][j], traj[:, 2][j], u, v, 0, color=colors[i], length=0.1,
                          normalize=True)
    ax.legend()
    plt.show()


def _before_flying(positions):
    plt.figure(figsize=(10, 8))
    ax = plt.axes(projection="3d")
    ax.set_xlabel("X [m]");
    ax.set_ylabel("Y [m]");
    ax.set_zlabel("Z [m]")
    xs = [s.x for s in positions];
    ys = [s.y for s in positions]
    zs = [s.z for s in positions];
    yaws = [s.yaw for s in positions]
    ax.plot(xs, ys, zs, color='lightsteelblue', linewidth=1)
    ax.scatter(xs, ys, zs, color='cyan', s=10, alpha=0.6)

    for i in range(0, len(xs), 2):
        u = 0.1 * cos(radians(yaws[i]))
        v = 0.1 * sin(radians(yaws[i]))
        ax.quiver(xs[i], ys[i], zs[i], u, v, 0, color='crimson', length=0.1, normalize=True)
    plt.show()


def plot_waypoints(trajectory, calculator=None, labels=None):
    if calculator is not None:
        _before_flying(trajectory)
    else:
        _planned_path(trajectory, labels)


#FILE I/O
def load_waypoints(filename):
    filepath = Path(filename)
    if not filepath.parent or filepath.parent == Path('.'):
        filepath = Path(__file__).resolve().parents[0] / 'trajectories' / filepath
    if not filepath.exists(): raise FileNotFoundError(f"Waypoint file not found: {filepath}")

    df = pd.read_csv(filepath)
    for col in ['x', 'y', 'z']:
        if col not in df.columns: raise ValueError(f"Missing column: {col}")
    return df[['x', 'y', 'z']].to_numpy()


def save_waypoints(waypoints, filename):
    if len(waypoints) == 0:
        print("No trajectory to save")
        return
    directory = os.path.dirname(str(filename))
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        is_4d = isinstance(waypoints[0], np.ndarray) and waypoints[0].shape[0] >= 4
        writer.writerow(["x", "y", "z", "yaw"] if is_4d else ["x", "y", "z"])
        for p in waypoints:
            writer.writerow(p)
    print(f"\nTrajectory saved to {filename}")

if __name__ == '__main__':
    #check ideal pre-defined trajectories
    trajectory = TrajectoryPlanner(0.8)
    circle = trajectory.generate_circle(1.0)
    plot_waypoints([circle])
    save_waypoints(circle,'ideal_trajectories/circle.csv')

    #filter real time trajectories
    real_trajectory = load_waypoints('trajectories/test_trajectory.csv')

    cage = VirtualCage(
        x_bounds=(-1.5, 1.5),
        y_bounds=(-1.0, 1.0),
        z_bounds=(0.1, 2.0)
    )
    processed_trajectory = add_yaw(filter_waypoints(real_trajectory,cage=cage))
    plot_waypoints([real_trajectory, processed_trajectory], labels=['real','processed'])
    save_waypoints(processed_trajectory,'trajectories/test_trajectory_processed.csv')