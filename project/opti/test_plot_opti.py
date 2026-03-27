from pathlib import Path
import sys, time
from threading import Thread, Lock
import numpy as np
import rerun as rr

sys.path.append(str(Path(__file__).resolve().parents[1]))

from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor

VISUALIZATION_RATE = 60  # Hz (Smooth 60 FPS rendering)
POLL_RATE = 100  # Hz (How fast we ask OptiTrack for data)
ID = 15
pos = None
lock = Lock()


def object_tracking(monitor, rigid_body_id):
    """Fetches the latest position from OptiTrack as fast as possible without averaging delay."""
    print(f"Starting high-speed object tracking for rigid body ID {rigid_body_id}")
    global pos
    while True:
        current_pos = monitor.get_position(rigid_body_id)
        if current_pos is not None:
            with lock:
                pos = current_pos

        # Poll at 100Hz
        time.sleep(1.0 / POLL_RATE)


# rerun setup
rr.init("marker_tracker", spawn=True)

# ideal figure-8 waypoints
t = np.linspace(0, 2 * np.pi, 100)
A = 1.0  # width in meters
B = 2.0  # length in meters
Z0 = 1.0  # height in meters

ideal_points = np.column_stack((A * np.sin(t), B * np.sin(t) * np.cos(t), np.ones_like(t) * Z0))

# draw ideal trajectory
rr.log("world/ideal_path", rr.LineStrips3D(ideal_points, colors=[176, 196, 222]))

actual_trajectory = []

monitor = NatNetRigidBodyMonitor()
monitor.start()
time.sleep(5)

# daemon=True -> stop thread while stopping the script
object_tracker_thread = Thread(target=object_tracking, args=(monitor, ID))
object_tracker_thread.daemon = True
object_tracker_thread.start()

print("Tracking started. Move your marker!")

# visualisation
try:
    while True:
        with lock:
            p = pos

        if p is not None:
            current_marker_pos = [p[0], p[1], p[2]]

            actual_trajectory.append(current_marker_pos)

            # keep last 500 points (At 60Hz, 500 points = ~8 seconds of trail)
            if len(actual_trajectory) > 500:
                actual_trajectory.pop(0)

            # Log to Rerun
            rr.log("world/marker", rr.Points3D(current_marker_pos, colors=[255, 0, 0], radii=0.05))
            rr.log("world/actual_path", rr.LineStrips3D(actual_trajectory, colors=[255, 0, 0]))

        time.sleep(1.0 / VISUALIZATION_RATE)

except KeyboardInterrupt:
    print("\nStopping tracker...")