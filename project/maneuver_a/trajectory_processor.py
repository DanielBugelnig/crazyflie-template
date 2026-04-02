import numpy as np


class TrajectoryProcessor:
    """Encapsulates the logic for cleaning and enhancing a raw trajectory"""
    def __init__(self, filter_threshold=0.05, smooth_window=5, min_height=0.15, yaw_smooth_window=7):
        self.filter_threshold = filter_threshold #how much close points will blend together
        self.smooth_window = smooth_window #how strong will be averaging upon points after filtering
        self.min_height = min_height
        self.yaw_smooth_window = yaw_smooth_window #how strong will be averaging for yaw


    def filter_and_smooth(self, trajectory: np.ndarray) -> np.ndarray:
        """Filters out close points and smooths the path using a moving average"""
        trajectory = np.asarray(trajectory)
        if len(trajectory) == 0:    return trajectory

        #remove points that are too close together
        filtered = [trajectory[0]]
        for p in trajectory[1:]:
            if np.linalg.norm(p - filtered[-1]) >= self.filter_threshold:
                filtered.append(p)
        filtered = np.array(filtered)

        #check for case not enough points to smooth
        if len(filtered) < self.smooth_window:  return filtered

        #smooth the trajectory using a moving average
        smoothed = np.copy(filtered)
        half_w = self.smooth_window // 2
        for i in range(len(filtered)):
            start = max(0, i - half_w)
            end = min(len(filtered), i + half_w + 1)
            smoothed[i] = np.mean(filtered[start:end], axis=0)

        #enforce minimum height
        smoothed[:, 2] = np.maximum(smoothed[:, 2], self.min_height)
        smoothed[0, 2] = self.min_height  #ensure start is at min height
        return smoothed


    def add_yaw(self, trajectory: np.ndarray) -> np.ndarray:
        """Calculates and appends a yaw angle for each point"""
        if len(trajectory) < 2: return np.column_stack((trajectory, np.zeros(len(trajectory))))

        dx, dy = np.diff(trajectory[:, 0]), np.diff(trajectory[:, 1])
        yaw_rad = np.arctan2(dy, dx)

        dist_2d = np.hypot(dx, dy)
        for i in range(1, len(yaw_rad)):
            if dist_2d[i - 1] < 0.01:
                yaw_rad[i] = yaw_rad[i - 1]

        yaw_rad = np.unwrap(yaw_rad)

        #additional smoothing of yaw
        if 1 < self.yaw_smooth_window < len(yaw_rad):
            pad = self.yaw_smooth_window // 2
            padded_yaw = np.pad(yaw_rad, (pad, pad), mode='edge')
            window_filter = np.ones(self.yaw_smooth_window) / self.yaw_smooth_window
            yaw_rad = np.convolve(padded_yaw, window_filter, mode='valid')

        yaw_rad = np.append(yaw_rad, yaw_rad[-1])
        yaw_deg = np.degrees(yaw_rad)
        return np.column_stack((trajectory, yaw_deg))


    def process(self, raw_trajectory: np.ndarray) -> np.ndarray:
        """Runs the full processing pipeline on a raw trajectory"""
        smoothed = self.filter_and_smooth(raw_trajectory)
        final_trajectory = self.add_yaw(smoothed)
        return final_trajectory