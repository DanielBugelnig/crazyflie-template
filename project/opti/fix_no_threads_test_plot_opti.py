from pathlib import Path
import sys, time, numpy as np, rerun as rr
from collections import deque
sys.path.append(str(Path(__file__).resolve().parents[2]))
from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor


#marker initialization
ID = 44
actual_trajectory = deque(maxlen=500)
threshold = 0.01
rr.init("marker_tracker", spawn=True)

#ideal trajectory generation
t = np.linspace(0, 2 * np.pi, 100)
A, B, Z0 = 1.0, 2.0, 1.0
ideal_points = np.column_stack((A * np.sin(t), B * np.sin(t) * np.cos(t), np.ones_like(t) * Z0))
rr.log("world/ideal_path", rr.LineStrips3D(ideal_points, colors=[176, 196, 222]))

#start optitrack
monitor = NatNetRigidBodyMonitor()
monitor.start()
time.sleep(2)
print("Tracking started. Move your marker!")

try:
    while True:
        pos = monitor.get_position(ID)

        if pos is not None and np.linalg.norm(np.array(pos) - np.array(actual_trajectory[-1])) >= threshold: #pos != last_pos
            current_marker_pos = [pos[0], pos[1], pos[2]]
            actual_trajectory.append(current_marker_pos)

            rr.log("world/marker", rr.Points3D(current_marker_pos, colors=[255, 0, 0], radii=0.05))
            rr.log("world/actual_path", rr.LineStrips3D(list(actual_trajectory), colors=[255, 0, 0]))

        time.sleep(0.005)

except KeyboardInterrupt:
    print("\nStopping tracker...")