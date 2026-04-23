import numpy as np, csv, os, pandas as pd
from math import sin, cos, radians, pi
from matplotlib import pyplot as plt
from pathlib import Path

# additional class to store OptiTrack constraints
class VirtualCage:
    def __init__(self, x_bounds, y_bounds, z_bounds):
        self.x_min, self.x_max = x_bounds
        self.y_min, self.y_max = y_bounds
        self.z_min, self.z_max = z_bounds

# functions for plotting
def plot_waypoints(trajectory:list, calculator=None, labels=None):
    #Standardize the input format for the plotter
    if calculator is not None:
        # Extract x, y, z, yaw into a single numpy array
        traj_data = np.array([[s.x, s.y, s.z, s.yaw] for s in trajectory[0]])
        _draw_3d_stage([traj_data], ["Pre-flight Path"], is_preflight=True)
    else:
        _draw_3d_stage(trajectory, labels)


def _draw_3d_stage(trajectories: list[np.ndarray], labels=None, is_preflight=False) -> None:
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")

    # Set labels once
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.set_zlabel("Z [m]")

    if labels is None:
        labels = [f"Trajectory {i + 1}" for i in range(len(trajectories))]

    cmap = plt.get_cmap('tab10')

    for i, traj in enumerate(trajectories):
        color = 'lightsteelblue' if is_preflight else cmap(i % 10)

        # 1. Plot the main line
        ax.plot(traj[:, 0], traj[:, 1], traj[:, 2], '-o', markersize=3, color=color, label=labels[i])

        # 2. Highlight the Start Point
        ax.scatter(traj[0, 0], traj[0, 1], traj[0, 2], color='red', s=100, alpha=0.5, label=f'Start {labels[i]}')

        # 3. Vectorized Quiver (The Optimization)
        # Instead of a loop, we calculate all U and V components at once
        if traj.shape[1] >= 4:
            # Only plot every 2nd or 5th arrow to avoid clutter in the demo
            step = 2 if is_preflight else 1
            t_slice = traj[::step]

            rads = np.radians(t_slice[:, 3])
            u = 0.1 * np.cos(rads)
            v = 0.1 * np.sin(rads)
            w = np.zeros_like(u)  # No vertical change for yaw arrows

            ax.quiver(t_slice[:, 0], t_slice[:, 1], t_slice[:, 2], u, v, w,
                      color='crimson' if is_preflight else color,
                      length=0.1, normalize=True)

    ax.legend()
    plt.tight_layout()
    plt.show()

#FILE I/O
def load_waypoints(filename):
    filepath = Path(filename)
    if not filepath.parent or filepath.parent == Path('../../maneuver_a'):
        filepath = Path(__file__).resolve().parents[0] / 'trajectories' / filepath
    if not filepath.exists(): raise FileNotFoundError(f"Waypoint file not found: {filepath}")

    df = pd.read_csv(filepath)
    for col in ['x', 'y', 'z']:
        if col not in df.columns: raise ValueError(f"Missing column: {col}")
    if 'yaw' in df.columns:
        return df[['x', 'y', 'z','yaw']].to_numpy()

    return df[['x', 'y', 'z']].to_numpy()


def save_waypoints(waypoints, filename):
    #!'filename' -> here is complete path

    if len(waypoints) == 0:
        print("No trajectory to save")
        return

    file_path,directory = Path(filename), Path(filename).parent
    # in case path is invalid
    if not directory.exists():
        print(f"Creating missing directory: {directory}")  # Added notification
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Error creating directory {directory}: {e}")
            return

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        is_4d = isinstance(waypoints[0], np.ndarray) and waypoints[0].shape[0] >= 4
        writer.writerow(["x", "y", "z", "yaw"] if is_4d else ["x", "y", "z"])
        for p in waypoints:
            writer.writerow(p)
    print(f"\nTrajectory saved to {filename}")


def prompt_for_filename(save_dir, processed_dir, purpose='save'):
    """Prompts user to update the active filename"""
    while True:
        input_name = input('\nFilename: ').lower().strip().replace(' ', '_').replace('.csv','')
        if input_name != '' or not input_name:
            potential_save_filename = f'{input_name}.csv'
            potential_full_path_recorded, potential_full_path_processed = save_dir / potential_save_filename, processed_dir / potential_save_filename

            if purpose == 'save':
                #Check if the file already exists
                if potential_full_path_recorded.exists() or potential_full_path_processed.exists():

                    overwrite = input(f"File '{potential_save_filename}' already exists in recorded or processed. Overwrite? (y/n): ").lower().strip()
                    if overwrite == 'y':
                        recorded_file = save_dir / potential_save_filename
                        processed_file = processed_dir / potential_save_filename

                        recorded_file.unlink(missing_ok=True)
                        processed_file.unlink(missing_ok=True)

                        print(f"Cleared old data for '{potential_save_filename}' in recorded and processed folders.")
                        return potential_save_filename
                    else:
                        print("Please enter a different filename.")
                        continue
                else:
                    # File doesn't exist, safe to use
                    return potential_save_filename

            elif purpose == 'load':
                if potential_full_path_recorded.exists() or potential_full_path_processed.exists():
                    return potential_save_filename
                else:
                    print('Given filename for trajectory does not exist')
                    continue

        else:
            print('Error with filename. Input cannot be empty.')
            return None