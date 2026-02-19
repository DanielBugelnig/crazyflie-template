from pathlib import Path
import sys, time

from evdev.ecodes import ID

sys.path.append(str(Path(__file__).resolve().parents[1]))

from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor
import crazyflie.core.base_utils as base
from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.core.shared_data import State


OFFSET_X = 1.5

def get_average_position(monitor, rigid_body_id, samples=100, interval=0.01):
    """
    Get the average position of a rigid body over multiple samples.
    
    Args:
        monitor: NatNetRigidBodyMonitor instance
        rigid_body_id: Rigid body ID to track
        samples: Number of samples to average (default: 100)
        interval: Time interval between samples in seconds (default: 0.01)
    
    Returns:
        tuple: (x, y, z) mean position, or None if no valid positions received
    """
    sum_x, sum_y, sum_z = 0.0, 0.0, 0.0
    count = 0
    
    for i in range(samples):
        pos = monitor.get_position(rigid_body_id)
        if pos is not None:
            sum_x += pos[0]
            sum_y += pos[1]
            sum_z += pos[2]
            count += 1
        #print(f"Position from NatNet RB {rigid_body_id}: {pos}, type {type(pos)}")
        time.sleep(interval)
    
    if count > 0:
        mean_pos = (sum_x / count, sum_y / count, sum_z / count)
        print(f"\nMean position over {count} samples: {mean_pos}")
        return mean_pos
    else:
        print("\nNo valid positions received")
        return None

ID = 15

# Natnet monitor setup
monitor = NatNetRigidBodyMonitor()
monitor.start()
time.sleep(5)
# Get average position
mean_pos = get_average_position(monitor, ID)






cf = CrazyFlie()
cf.logging(enable=True, file=True, level=base.LogLevel.debug)
cf.set_natnet_monitor(monitor)



cf.scan()
cf.connect(start_flying=True)
time.sleep(5)
while True:
    # update the follower position based on the mean position of the rigid body with offset
    mean_pos = (mean_pos[0], mean_pos[1], mean_pos[2])
    cf.fly(State(mean_pos[0] + OFFSET_X, mean_pos[1], mean_pos[2]))
    
