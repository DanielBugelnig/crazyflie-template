"""
Evaluates the accuracy of a recorded trajectory against a predefined ideal path

Usage -> run with 's01_recording.py' or separately by specifying trajectory filename
"""

import traceback, numpy as np, matplotlib.pyplot as plt
from numpy import ndarray
from scipy.interpolate import interp1d


class AccuracyEvaluator:
    """
    Calculates the accuracy of a recorded trajectory compared to an ideal path
    -> can calculate instantaneous accuracy at each point
    -> can evaluate the entire trajectory and visualize the results
    """

    def __init__(
            self,
            ideal_trajectory: ndarray,
            scale=0.5,  # what distance error is acceptable
            alpha=0.5,  # exponential moving average -> to remove jitter
    ):
        """
        ideal_trajectory (ndarray): A NumPy array of (x, y, z)
        scale (float): A scaling factor for the distance error in the scoring formula -> a smaller value makes the scoring stricter -> e.g. score=50% exactly at scale 0.5 m
        alpha (float): The smoothing factor for the exponential moving average of the score -> a higher value gives more weight to the current raw score
        """
        self.trajectory = resample_trajectory(ideal_trajectory, N=100)
        self.height = ideal_trajectory[0, 2]
        self.scale = scale
        self.alpha = alpha
        self.smooth_score = None
        self.last_completion_ratio = 0.0
        self.last_base_accuracy = 0.0

    def _point_to_segment_distance(self, P:ndarray, A:ndarray, B:ndarray):
        """
        Compute the shortest distance from a point P to a line segment AB.

        Returns:
            - The distance from P to the closest point on the segment
            - The coordinates of the closest point on the segment
            - A parameter 't' indicating where the closest point lies on the line defined by A and B
              >> t=0 corresponds to A, t=1 to B. Values outside [0, 1] mean the closest point is A or B
        """
        ap = P - A  # vector from A to P
        ab = B - A

        denum = np.dot(ab, ab)
        if denum == 0:  # if A B are same point
            return np.linalg.norm(P - A), A

        t = np.dot(ap, ab) / denum
        t_clamped = np.clip(t, 0.0, 1.0)

        closest = A + t_clamped * ab
        return np.linalg.norm(P - closest), closest, t

    def get_instantaneous_accuracy(self, current_point:ndarray):
        """
        Calculates the accuracy of a single point against the ideal trajectory.

        Returns:
            - The raw score (0-100) for the current point
            - The smoothed score, updated with the current raw score
            - The distance from the point to the ideal trajectory
            - The closest point on the ideal trajectory
        """
        P = np.array(current_point)
        P[2] = self.height  # force height from 2D ideal traj

        best_dist = float('inf')
        best_closest = None

        for i in range(len(self.trajectory) - 1):
            A = self.trajectory[i]
            B = self.trajectory[i + 1]
            dist, closest, t = self._point_to_segment_distance(P, A, B)

            # find best clothest point
            if dist < best_dist:
                best_dist = dist
                best_closest = closest

        # Scoring & Smoothing
        raw_score = 100 / (1 + best_dist / self.scale)
        if self.smooth_score is None:
            self.smooth_score = raw_score
        else:
            self.smooth_score = self.alpha * raw_score + (1 - self.alpha) * self.smooth_score

        return raw_score, self.smooth_score, best_dist, best_closest

    def evaluate_full_trajectory(self, recorded_points:ndarray, threshold=0.05, coverage_threshold=None):
        """
        Processes a full array of points, calculates overall accuracy, and applies a
        completion-ratio penalty so incomplete trajectories score lower.

        Completion ratio is based on how much of the ideal trajectory is actually
        covered by recorded points (not only how far along the path the flight reached).

        Returns:
            - The average distance error
            - The final accuracy score
            - A list of instantaneous scores for each point
            - The filtered list of recorded points
        """
        # Reset state for a fresh run
        self.smooth_score = None
        self.last_completion_ratio = 0.0
        self.last_base_accuracy = 0.0

        recorded_points = np.array(recorded_points)
        if recorded_points.size == 0:
            return 0.0, 0.0, [], []

        if recorded_points.ndim != 2 or recorded_points.shape[0] == 0:
            return 0.0, 0.0, [], []

        recorded_points[:, 2] = self.height  # force height from 2D ideal traj

        # trim closest points
        filtered = [recorded_points[0]]
        for p in recorded_points[1:]:
            if np.linalg.norm(p - filtered[-1]) >= threshold:
                filtered.append(p)

        distances, scores = [], []

        for pt in filtered:
            raw, smooth, dist, closest = self.get_instantaneous_accuracy(pt)
            distances.append(dist)
            scores.append(smooth)

        if not distances:
            return 0.0, 0.0, [], []

        avg_dist = float(np.mean(distances))
        base_accuracy = float(np.mean(scores))

        # Completion ratio from ideal-point coverage:
        # percentage of ideal trajectory points that have at least one recorded
        # point within a distance threshold.
        rec_xy = np.array(filtered)[:, :2]
        ideal_xy = self.trajectory[:, :2]

        if coverage_threshold is None:
            coverage_threshold = max(0.05, self.scale)

        # Pairwise distances (ideal_points x recorded_points)
        dxy = ideal_xy[:, None, :] - rec_xy[None, :, :]
        pairwise_dist = np.linalg.norm(dxy, axis=2)

        min_dist_per_ideal_point = np.min(pairwise_dist, axis=1)
        covered_points = np.sum(min_dist_per_ideal_point <= coverage_threshold)
        completion_ratio = float(np.clip(covered_points / len(ideal_xy), 0.0, 1.0))

        # Penalize incomplete trajectories (linear penalty)
        final_accuracy = base_accuracy * completion_ratio

        self.last_base_accuracy = base_accuracy
        self.last_completion_ratio = completion_ratio

        return avg_dist, final_accuracy, scores, filtered

    def plot_results(self, recorded_points:ndarray, scores_list:list, final_accuracy=None):
        """
        Visualizes the ideal and recorded trajectories, with scores represented by color
        """

        if len(recorded_points) == 0:
            print("No recorded path available to plot.")
            return

        if len(scores_list) == 0:
            print("No score history found to plot.")
            return

        recorded_np = np.array(recorded_points)
        scores_np = np.array(scores_list)

        # Safety check
        if len(recorded_np) != len(scores_np):
            print("Mismatch between path and score lengths, recorded:", len(recorded_np), "scores:", len(scores_np))
            return

        fig = plt.figure(figsize=(10, 7))
        ax = fig.add_subplot(111, projection='3d')

        # Ideal Path Plotting
        ax.scatter(
            self.trajectory[:, 0],
            self.trajectory[:, 1],
            self.trajectory[:, 2],
            label="Ideal Path",
            linewidth=2,
            alpha=0.6
        )

        # Recorded Path Scatter
        sc = ax.scatter(
            recorded_np[:, 0],
            recorded_np[:, 1],
            recorded_np[:, 2],
            c=scores_np,
            cmap='RdYlGn',
            s=25
        )
        ax.plot(
            recorded_np[:, 0],
            recorded_np[:, 1],
            recorded_np[:, 2],
            color='gray',
            alpha=0.3
        )

        cbar = plt.colorbar(sc, ax=ax)
        cbar.set_label("Instantaneous Score (%)")

        display_score = final_accuracy if final_accuracy is not None else np.mean(scores_np)

        ax.set_title(f"Trajectory Analysis - Final Score: {display_score:.2f}%")
        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")

        ax.legend()
        plt.tight_layout()
        plt.show()


# ------- ADDITIONAL -------
def resample_trajectory(trajectory:ndarray, N=100):
    """
    Resamples a trajectory to have a specified number of evenly spaced points.
    """
    trajectory = np.array(trajectory)

    # compute segment lengths
    dists = np.linalg.norm(np.diff(trajectory, axis=0), axis=1)

    # cumulative arc length
    cumdist = np.insert(np.cumsum(dists), 0, 0)

    # handle edge case (all points identical)
    if cumdist[-1] == 0:
        return trajectory

    # uniform spacing
    uniform_d = np.linspace(0, cumdist[-1], N)
    # interpolate
    interp_func = interp1d(cumdist, trajectory, axis=0)
    new_traj = interp_func(uniform_d)

    return new_traj
# --------------------------


def main():
    from utils import load_waypoints
    from pathlib import Path
    from utils import prompt_for_filename
    save_dir = Path(__file__).resolve().parent / 'data' / 'recorded_trajectories'
    processed_dir = Path(__file__).resolve().parent / 'data' / 'processed_trajectories'

    try:
        print("Generating ideal trajectory...")
        t = np.linspace(0, 2 * np.pi, 100)
        A, B, Z0 = 1.0, 2.0, 0.0
        ideal_points = np.column_stack((A * np.sin(t), B * np.sin(t) * np.cos(t), np.ones_like(t) * Z0))

        evaluator = AccuracyEvaluator(ideal_trajectory=ideal_points, scale=0.5, alpha=0.5)  # strict 0.2
        save_filename = prompt_for_filename(save_dir, processed_dir, purpose='load')

        print("Loading recorded flight data...")
        test_points = load_waypoints(save_dir / f"{save_filename}")
        test_points[:, 2] = Z0  # Force height to match ideal

        test_points = resample_trajectory(test_points, N=100)
        print("Evaluating trajectory...")
        avg_dist, final_score, scores, rec = evaluator.evaluate_full_trajectory(np.array(test_points))
        completion_ratio = evaluator.last_completion_ratio
        base_accuracy = evaluator.last_base_accuracy

        for i, pt in enumerate(test_points[:5]):
            print(f"Point {i}: Dist: {avg_dist:.3f}m | Instant Score: {scores[i]:.2f}%")
        print("...")

        print("\n--- FLIGHT SUMMARY ---")
        print(f"Points evaluated:       {len(test_points)} (Ideal was {len(ideal_points)})")
        print(f"Average Distance Error: {avg_dist:.3f} meters")
        print(f"Base Accuracy:          {base_accuracy:.2f}%")
        print(f"Completion Ratio:       {completion_ratio:.2%}")
        print(f"Final Accuracy (w/ penalty): {final_score:.2f}%")
        print("----------------------\n")

        evaluator.plot_results(
            recorded_points=rec,
            scores_list=scores,
            final_accuracy=final_score
        )

    except Exception as e:
        traceback.print_exc()


if __name__ == '__main__':
    main()