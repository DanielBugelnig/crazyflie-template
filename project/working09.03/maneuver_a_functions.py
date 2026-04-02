"""
Script that plots trajectory + an option to filter points and smooth them afterward
Possible to try on two recorded trajectories:
    filename = Path(__file__).resolve().parents[0] / 'trajectories' / 'test_trajectory.csv'
    filename = Path(__file__).resolve().parents[0] / 'trajectories' / 'test_trajectory_2.csv'
"""

import numpy as np, csv
from matplotlib import pyplot as plt
import pandas as pd,os
from math import sin,cos,radians

from pathlib import Path
#from draw_trajectory_in_the_air import update_filename_path,filename,save_dir

def _planned_path(trajectories:list[np.ndarray],labels) -> None:
    plt.figure(figsize=(10, 8))

    ax = plt.axes(projection="3d")
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.set_zlabel("Z [m]")

    n = len(trajectories)
    labels = [f"Trajectory {i + 1}" for i in range(n)] if labels is None else labels

    cmap = plt.get_cmap('tab10')
    colors = [cmap(i % 10) for i in range(n)]

    for i, traj in enumerate(trajectories):
        ax.plot(traj[:, 0], traj[:, 1], traj[:, 2], '-o', markersize=3, color=colors[i], label=labels[i])
        ax.scatter(traj[:, 0], traj[:, 1], traj[:, 2], color=colors[i], s=10, alpha=0.3)

        #for plotting yaw
        if traj.shape[1] >= 4:
            skip_step = 1 #2
            for j in range(0, len(traj[:, 0]), skip_step):
                u = 0.1 * cos(radians(traj[:, 3][j]))
                v = 0.1 * sin(radians(traj[:, 3][j]))
                ax.quiver(traj[:, 0][j], traj[:, 1][j], traj[:, 2][j], u, v, 0, color=colors[i], length=0.1, normalize=True)

    ax.legend()
    plt.show()


# from final project
def _before_flying(positions):
    """Generates 3D graph of trajectory (list[State]) where yaw is shown by vectors

    Args:
        positions (list[State]): trajectory
    """
    plt.figure(figsize=(10, 8))
    ax = plt.axes(projection="3d")
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.set_zlabel("Z [m]")

    # Handle both raw lists and State objects
    xs = [s.x for s in positions]
    ys = [s.y for s in positions]
    zs = [s.z for s in positions]
    yaws = [s.yaw for s in positions]
    
    ax.plot(xs, ys, zs, color='lightsteelblue', linewidth=1)
    ax.scatter(xs, ys, zs, color='cyan', s=10, alpha=0.6)

    skip_step = 2
    for i in range(0, len(xs), skip_step):
        u = 0.1 * cos(radians(yaws[i]))
        v = 0.1 * sin(radians(yaws[i]))
        ax.quiver(xs[i], ys[i], zs[i], u, v, 0, color='crimson', length=0.1, normalize=True)

    plt.show()


def plot_waypoints(filename=None, trajectory=None, calculator=None, labels=None):
    if calculator is not None: _before_flying(trajectory)

    elif trajectory is None: 
        trajectory = [pd.read_csv(filename)[['x','y','z']].to_numpy()]
    
    _planned_path(trajectory, labels)


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

    # z = smoothed[:, 2]
    # off_ground = np.where(z > min_height)[0]

    # if len(off_ground) > 0:
    #     first = off_ground[0]
    #     last = off_ground[-1]

    #     z[:first] = min_height
    #     z[last + 1:] = min_height
    # else:
    #     smoothed[:] = 0.0
    #     return smoothed

    # smoothed[:, 2] = np.maximum(min_height, z)
    # smoothed[0, 2] = min_height
    #smoothed[-1, 2] = min_height

    return smoothed

#to add yaw vector
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



def load_waypoints(filename):
   # Ensure filename is a Path object
    filepath = Path(filename)

    # If only a name is given (no parent), assume it's in 'trajectories' folder
    if not filepath.parent or filepath.parent == Path('.'):
        base_dir = Path(__file__).resolve().parents[0] / 'trajectories'
        filepath = base_dir / filepath

    # Make sure the file exists
    if not filepath.exists():
        raise FileNotFoundError(f"Waypoint file not found: {filepath}")

    # Load CSV and return x,y,z as numpy array
    df = pd.read_csv(filepath)

    # Ensure the CSV has required columns
    for col in ['x', 'y', 'z']:
        if col not in df.columns:
            raise ValueError(f"CSV file missing required column: {col}")

    return df[['x', 'y', 'z']].to_numpy()


def update_filename_path():
    global filename

    save_filename = input('\nFilename: ').lower().strip().replace(' ', '_')
    if save_filename != '':
        filename = save_dir / f'{save_filename}.csv'
    else:
        filename=None
        print('Error')



# # Paths
base_path = Path(__file__).resolve().parents[0]
save_dir = base_path / 'trajectories'
os.makedirs(save_dir, exist_ok=True)
# filename = None

def save_waypoints_2(trajectory_way_points,filename=None):
    
    if len(trajectory_way_points) == 0:
        print("No trajectory to save")
        return
    
    elif filename is None:
        save_filename = input('\nFilename: ').lower().strip().replace(' ', '_')
        if save_filename != '':
            filename = save_dir / f'{save_filename}.csv'
        else:
            filename=None
            print('Error')

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)

        writer.writerow(["x", "y", "z","yaw"] if trajectory_way_points.shape[1] >= 4 else ["x", "y", "z"])


        for p in trajectory_way_points:
            writer.writerow(p)

    print(f"Trajectory saved to {filename}")
import time
from crazyflie.constants import MOCAP_TX_RATE_HZ
from test_draw_trajectory_in_the_air import UPDATE_RATE

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


from crazyflie.bitcraze.trajectory import Trajectory
from crazyflie.bitcraze.crazyflie import CrazyFlie
##
def create_trajectory(calculator, list_of_pos, no_yaw=False) -> list:
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

def main():
    user=input('What to load: ')
    raw = load_waypoints(user)
   
    trajectory_smoothed = filter_waypoints(raw)
    traj_yaw = add_yaw(trajectory_smoothed)

    print(f'Old # of points: {len(raw)}, new filtered: {len(traj_yaw)}')
    plot_waypoints(trajectory=[traj_yaw], labels=['with yaw'])
    save_waypoints_2(traj_yaw, 'test_traj_save.csv')

if __name__ == '__main__':
    main()