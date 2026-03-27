from pathlib import Path
import sys, time
from collections import deque
import numpy as np
import rerun as rr

sys.path.append(str(Path(__file__).resolve().parents[2]))

from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor

ID = 44

rr.init("marker_tracker", spawn=True)
#rr.serve()

# Draw Ideal Path
t = np.linspace(0, 2 * np.pi, 100)
A, B, Z0 = 1.0, 2.0, 1.0
ideal_points = np.column_stack((A * np.sin(t), B * np.sin(t) * np.cos(t), np.ones_like(t) * Z0))
rr.log("world/ideal_path", rr.LineStrips3D(ideal_points, colors=[176, 196, 222]))


actual_trajectory = deque(maxlen=50)


monitor = NatNetRigidBodyMonitor()
monitor.start()
time.sleep(2) 
print("Tracking started. Move your marker!")


original_callback = monitor._client.rigid_body_listener
threshold =0.01
def fast_rerun_callback(rigid_body_id, position, rotation):
  
    original_callback(rigid_body_id, position, rotation)
  
    if rigid_body_id == ID:

        current_pos = [position[0], position[1], position[2]]
       
        #if actual_trajectory[-1] is None or np.linalg.norm(current_pos - actual_trajectory[-1]) >= threshold:
                
        actual_trajectory.append(current_pos)
        rr.log("world/marker", rr.Points3D(current_pos, colors=[255, 0, 0], radii=0.05))
        rr.log("world/actual_path", rr.LineStrips3D(list(actual_trajectory), colors=[255, 0, 0]))


monitor._client.rigid_body_listener = fast_rerun_callback

try:
    while True:
        time.sleep(1) # This loop does zero work.
except KeyboardInterrupt:
    print("\nStopping tracker...")
    print(actual_trajectory)
