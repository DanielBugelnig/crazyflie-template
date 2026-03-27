from pathlib import Path
import sys, time
from threading import Thread, Lock
import numpy as np
import rerun as rr

sys.path.append(str(Path(__file__).resolve().parents[1]))

from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor
from crazyflie.constants import MOCAP_TX_RATE_HZ

UPDATE_RATE = 10  # Hz
ID = 15
pos = None
lock = Lock()


def get_average_position(monitor, rigid_body_id, update_rate=UPDATE_RATE):
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

    if count > 0:
        return (sum_x / count, sum_y / count, sum_z / count)
    else:
        return None


def object_tracking(monitor, rigid_body_id, update_rate):
    print(f"Starting object tracking for rigid body ID {rigid_body_id}")
    global pos
    while True:
        current_pos = get_average_position(monitor, rigid_body_id, update_rate=update_rate)
        if current_pos is not None:
            with lock:
                pos = current_pos


# rerun setup
rr.init("marker_tracker", spawn=True)

# ideal figure-8 waypoints
t = np.linspace(0, 2 * np.pi, 100)
A = 1.0  # width in meters
B = 2.0  # length in meters
Z0 = 1.0  # height in meters

ideal_points = np.column_stack((A * np.sin(t), B * np.sin(t) * np.cos(t), np.ones_like(t) * Z0))

#draw ideal trajectory
rr.log("world/ideal_path", rr.LineStrips3D(ideal_points, colors=[176, 196, 222]))

actual_trajectory = []

monitor = NatNetRigidBodyMonitor()
monitor.start()
time.sleep(5)

# daemon=True -> stop thread while stopping the script
object_tracker_thread = Thread(target=object_tracking, args=(monitor, ID, UPDATE_RATE))
object_tracker_thread.daemon = True
object_tracker_thread.start()

print("Tracking started. Move your marker!")

# visualisation
try:
    while True:
        with lock:
            p = pos

        if p is not None:
            marker_x, marker_y, marker_z = p[0], p[1], p[2]
            current_marker_pos = [marker_x, marker_y, marker_z]

            actual_trajectory.append(current_marker_pos)

            # keep last 2500 points
            if len(actual_trajectory) > 2500:
                actual_trajectory.pop(0)

            # Log to Rerun
            rr.log("world/marker", rr.Points3D(current_marker_pos, colors=[255, 0, 0], radii=0.05))
            rr.log("world/actual_path", rr.LineStrips3D(actual_trajectory, colors=[255, 0, 0]))

        time.sleep(1.0 / UPDATE_RATE)

except KeyboardInterrupt:
    print("\nStopping tracker...")