"""
Processes the raw trajectory data to prepare it for flight. This includes filtering, smoothing, and adding yaw information

Usage -> run after 's01_recording.py' or automatically before 's04_flying.py'
"""

import numpy as np
from numpy import ndarray
from utils import plot_waypoints, VirtualCage, save_waypoints          #Contains utility functions for plotting, file I/O, and other common tasks

# --- REAL TRAJECTORY FILTERING ---
def filter_waypoints(trajectory:ndarray, threshold=0.1, window_size=7, min_height=0.2, cage:VirtualCage=None):
    """
    Filters and smooths a raw trajectory

    Args:
        trajectory (ndarray): The input trajectory as a NumPy array of (x, y, z)
        threshold (float): The minimum distance between consecutive points. Points closer than this are removed
        window_size (int): The size of the moving average window for smoothing
        min_height (float): The minimum allowed height (z-coordinate)
        cage (VirtualCage, optional): A virtual cage to constrain the trajectory within safe boundaries
    """
    trajectory = np.asarray(trajectory)
    if len(trajectory) == 0:
        return trajectory

    #remove points that are too close
    filtered = [trajectory[0]]
    for p in trajectory[1:]:
        if np.linalg.norm(p - filtered[-1]) >= threshold:
            filtered.append(p)
    filtered = np.array(filtered)
    print(f'\nOriginal: {len(trajectory)} points, filtered: {len(filtered)}')
    print(f'Removed {len(trajectory) - len(filtered)} points')

    #smoothing by moving average
    smoothed = np.copy(filtered)
    half_w = window_size // 2
    for i in range(len(filtered)):
        # Define the window for averaging, handling edges
        start = max(0, i - half_w)
        end = min(len(filtered), i + half_w + 1)
        smoothed[i] = np.mean(filtered[start:end], axis=0)

    #enforce min height
    smoothed[:, 2] = np.maximum(smoothed[:, 2], min_height)

    #apply virtual cage constraints if provided.
    if cage is not None:
        smoothed[:, 0] = np.clip(smoothed[:, 0], cage.x_min, cage.x_max)  # Left/Right limits
        smoothed[:, 1] = np.clip(smoothed[:, 1], cage.y_min, cage.y_max)  # Forward/Back limits
        smoothed[:, 2] = np.clip(smoothed[:, 2], cage.z_min, cage.z_max)  # Min/Max height limits

    #check for point spacing !
    smoothed_filtered = [smoothed[0]]
    for p in smoothed[1:]:
        if np.linalg.norm(p - smoothed_filtered[-1]) >= threshold:
            smoothed_filtered.append(p)
    smoothed_filtered = np.array(smoothed_filtered)
    return smoothed_filtered


def add_yaw(trajectory:ndarray, look_ahead=5, smooth_window=15):
    """
    Calculates and adds a smoothed yaw angle to the trajectory.
    The yaw is determined by the direction of travel.

    Args:
        trajectory (ndarray): The input trajectory (x, y, z).
        look_ahead (int): The number of points to look ahead to determine the direction of movement -> ignore local noise
        smooth_window (int): The size of the moving average window for smoothing the yaw angles
    """
    n = len(trajectory)
    yaw_rad = np.zeros(n)

    # Calculate the initial yaw angles based on the direction vector
    for i in range(n):
        target_idx = min(i + look_ahead, n - 1) #target point

        #direction vector (dx, dy)
        dx = trajectory[target_idx, 0] - trajectory[i, 0]
        dy = trajectory[target_idx, 1] - trajectory[i, 1]

        #if the drone is nearly stationary, keep the previous yaw to avoid spinning
        if np.hypot(dx, dy) < 0.02 and i > 0:
            yaw_rad[i] = yaw_rad[i - 1]
        else:
            #calculate the yaw angle from the direction vector
            yaw_rad[i] = np.arctan2(dy, dx)

    yaw_rad = np.unwrap(yaw_rad) #unwrap the yaw angles to prevent large jumps (e.g., from 359 to 1 degree)

    #Smooth the yaw angles using a moving average filter
    kernel = np.ones(smooth_window) / smooth_window
    #Pad the array at the edges to handle boundaries during convolution.
    yaw_rad_padded = np.pad(yaw_rad, (smooth_window // 2, smooth_window // 2), mode='edge')
    yaw_rad_smoothed = np.convolve(yaw_rad_padded, kernel, mode='valid')[:n]

    return np.column_stack((trajectory, np.degrees(yaw_rad_smoothed)))


def main():
    from utils import load_waypoints
    from pathlib import Path
    from utils import prompt_for_filename

    # --- Setup Directories ---
    save_dir = Path(__file__).resolve().parent / 'data' / 'recorded_trajectories'
    processed_dir = Path(__file__).resolve().parent / 'data' / 'processed_trajectories'
    
    # --- Load Data ---
    save_filename = prompt_for_filename(save_dir, processed_dir, purpose='load')

    raw_trajectory = load_waypoints(save_dir/save_filename)
    
    # --- Processing ---
    cage = VirtualCage(x_bounds=(-1.0, 1.0), y_bounds=(-1.0, 1.0), z_bounds=(0.2, 1.0))

    print("Applying filters and cage constraints...")
    filtered_traj = filter_waypoints(raw_trajectory, min_height=0.2, cage=cage)

    print("Calculating and smoothing Yaw...")
    final_traj: ndarray = add_yaw(filtered_traj)

    print("\n--- Validation Results ---")
    print(f"Raw shape: {raw_trajectory.shape}")
    print(f"Final shape (with yaw): {final_traj.shape}")

    # --- Plotting ---
    try:
        # Plot both raw and final trajectories for comparison
        plot_waypoints(trajectory=[raw_trajectory, final_traj[:, :3]], labels=['Raw/Noisy', 'Filtered & Smoothed'])
        print("\nPlot successfully generated. Close the plot window to continue.")
    except Exception as e:
        print(f"\nPlotting skipped/failed: {e}")

    # Plot the final trajectory with yaw (if supported by the plotter)
    plot_waypoints(trajectory=[final_traj], labels=['Filtered & Smoothed'])
    save_waypoints(final_traj, processed_dir / save_filename)  # Save the processed trajectory for future use


# Example utility function to check all trajectories in a directory
# def check_all_trajectories():
#     base_path = Path(__file__).resolve().parents[0]
#     save_dir = base_path / 'trajectories'
#     os.makedirs(save_dir, exist_ok=True)
#
#     for file in os.listdir(save_dir):
#         if os.path.isfile(os.path.join(save_dir, file)):
#             print(file)
#             traj = load_waypoints(save_dir/ f'{file}')
#             plot_waypoints([traj], labels=[file])


if __name__ == '__main__':
    main()