"""
This module provides a robust tool for comparing and scoring trajectories, specifically tailored for Maneuver A using the Longest Common Sub-Sequence (LCSS) metric
"""
import numpy as np, sys, matplotlib.pyplot as plt
from pathlib import Path
from tslearn.metrics import lcss,dtw
sys.path.append(str(Path(__file__).resolve().parent.parent / 'working09.03'))
from utility_functions import load_waypoints, plot_waypoints

def trim_trajectory(ideal_traj, recorded_traj, threshold=0.3):
    """
    Trims the recorded trajectory to start and end when it is near the 
    ideal trajectory's start and end points.
    """
    start_point = ideal_traj[0]
    end_point = ideal_traj[-1]

    # Calculate Euclidean distances from the start and end points
    dist_to_start = np.linalg.norm(recorded_traj - start_point, axis=1)
    dist_to_end = np.linalg.norm(recorded_traj - end_point, axis=1)

    # Find the first index where we are close to the start
    start_indices = np.where(dist_to_start < threshold)[0]
    # Find the last index where we were close to the end
    end_indices = np.where(dist_to_end < threshold)[0]

    if len(start_indices) == 0 or len(end_indices) == 0:
        print("Warning: Could not find points within threshold. Returning original.")
        return recorded_traj

    first_idx = start_indices[0]
    last_idx = end_indices[-1]


    #filter
    trajectory = np.asarray(recorded_traj[first_idx : last_idx + 1])
    if len(trajectory) == 0:    return trajectory

    # remove points that are too close together
    filtered = [trajectory[0]]
    for p in trajectory[1:]:
        if np.linalg.norm(p - filtered[-1]) >= 0.1:
            filtered.append(p)
    filtered = np.array(filtered)
    return filtered


class TrajectoryComparator:
    """A class to compare an ideal trajectory with a recorded one using LCSS"""

    def calculate_dtw_score(self, ideal_traj: np.ndarray, recorded_traj: np.ndarray) -> float:
        """
        Calculates the DTW distance between two trajectories.
        Note: DTW returns a distance (lower is better), not a percentage.
        """
        if ideal_traj is None or recorded_traj is None or len(ideal_traj) == 0:
            return 0.0
        distance = dtw(ideal_traj, recorded_traj)
        score = 100 * np.exp(-distance / 10.0)
        return score

    def calculate_lcss_score(self, ideal_traj: np.ndarray, recorded_traj: np.ndarray, epsilon: float) -> float:
        """
        Calculates the LCSS-based similarity score between two trajectories

        Args:
            ideal_traj (np.ndarray): The reference trajectory.
            recorded_traj (np.ndarray): The trajectory to be scored.
            epsilon (float): The matching tolerance in meters. Points are considered a match
                             if their Euclidean distance is less than this value.

        Returns:
            float: A similarity score from 0 to 100, where 100 is a perfect match.
        """
        if ideal_traj is None or recorded_traj is None or len(ideal_traj) == 0:
            return 0.0

        similarity_ratio = lcss(ideal_traj, recorded_traj, eps=epsilon) #it measures the ratio of the length of the common subsequence to the length of the longer sequence
        return similarity_ratio * 100

    def plot_comparison(self, ideal_traj: np.ndarray, recorded_traj: np.ndarray, score: float):
        plt.figure(figsize=(12, 9))
        ax = plt.axes(projection="3d")
        ax.set_xlabel("X [m]")
        ax.set_ylabel("Y [m]")
        ax.set_zlabel("Z [m]")
        ax.set_title(f"Trajectory Comparison (Accuracy Score: {score:.2f}%)")

        # Plot Ideal Trajectory
        ax.plot(ideal_traj[:, 0], ideal_traj[:, 1], ideal_traj[:, 2],
                'g-o', markersize=3, label='Ideal Trajectory')

        # Plot Recorded Trajectory
        ax.plot(recorded_traj[:, 0], recorded_traj[:, 1], recorded_traj[:, 2],
                'r-o', markersize=3, label='Recorded Trajectory')

        ax.legend()
        plt.show()


def path():
    """Main function to demonstrate and test the TrajectoryComparator."""
    MATCHING_EPSILON = 0.10  # meters
    NOISE_LEVEL = 0.05  # 5cm standard deviation

    try:
        # Assumes 'test1.csv' is in the 'trajectories' folder within the 'working09.03' directory
        base_dir = Path(__file__).resolve().parent.parent / 'maneuver_a' / 'trajectories'
        file_to_load = base_dir / 'test1.csv'
        ideal_trajectory = load_waypoints(file_to_load)
        if ideal_trajectory is None:
            raise FileNotFoundError
    except FileNotFoundError:
        print(f"Error: Could not find or load the trajectory file. Using a dummy trajectory.")
        ideal_trajectory = np.array([[0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1], [0, 0, 1]])

    recorded_trajectory = ideal_trajectory.copy()
    noise = np.random.normal(loc=0.0, scale=NOISE_LEVEL, size=recorded_trajectory.shape)
    recorded_trajectory += noise
    print(f"\nCreated a noisy test trajectory with a noise level of {NOISE_LEVEL * 100:.1f} cm.")

    print(f"Original recorded trajectory length: {len(recorded_trajectory)}")
    trimmed_recorded_trajectory = trim_trajectory(ideal_trajectory, recorded_trajectory)
    print(f"Trimmed recorded trajectory length: {len(trimmed_recorded_trajectory)}")

    comparator = TrajectoryComparator()
    accuracy_score = comparator.calculate_lcss_score(
        ideal_traj=ideal_trajectory,
        recorded_traj=trimmed_recorded_trajectory,
        epsilon=MATCHING_EPSILON
    )

    print(f"\nTrajectory Accuracy Score: {accuracy_score:.2f}%")
    print(f"(Calculated with an epsilon of {MATCHING_EPSILON * 100:.1f} cm)")
    comparator.plot_comparison(ideal_trajectory, trimmed_recorded_trajectory, accuracy_score)


def main():
    MATCHING_EPSILON = 0.10  # meters
    try:
        # Assumes 'test1.csv' is in the 'trajectories' folder within the 'working09.03' directory
        base_dir = Path(__file__).resolve().parent.parent / 'maneuver_a' / 'trajectories'
        file_to_load = base_dir / 'traj_8_recorded.csv'
        recorded_trajectory = load_waypoints(file_to_load)
        if recorded_trajectory is None:
            raise FileNotFoundError

        for pos in recorded_trajectory:
            pos[2]=0.0
        # ideal traj generation
        t = np.linspace(0, 2 * np.pi, 100)
        A, B, Z0 = 1.0, 2.0, 0.0
        ideal_trajectory = np.column_stack((A * np.sin(t), B * np.sin(t) * np.cos(t), np.ones_like(t) * Z0))
    except FileNotFoundError:
        print(f"Error: Could not find or load the trajectory file")

        sys.exit()

    print(f"Original recorded trajectory length: {len(recorded_trajectory)}")
    trimmed_recorded_trajectory = trim_trajectory(ideal_trajectory, recorded_trajectory)
    print(f"Trimmed recorded trajectory length: {len(trimmed_recorded_trajectory)}")

    comparator = TrajectoryComparator()
    accuracy_score = comparator.calculate_dtw_score(
        ideal_traj=ideal_trajectory,
        recorded_traj=trimmed_recorded_trajectory
    )
    accuracy_score2 = comparator.calculate_lcss_score(
        ideal_traj=ideal_trajectory,
        recorded_traj=trimmed_recorded_trajectory,
        epsilon=MATCHING_EPSILON
    )

    print(f"\nTrajectory Accuracy Score: {accuracy_score:.2f}%")
    print(f"(Calculated with an epsilon of {MATCHING_EPSILON * 100:.1f} cm)")
    comparator.plot_comparison(ideal_trajectory, trimmed_recorded_trajectory, accuracy_score)
    comparator.plot_comparison(ideal_trajectory, trimmed_recorded_trajectory, accuracy_score2)
if __name__ == "__main__":
    main()