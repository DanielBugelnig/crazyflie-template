from pathlib import Path
import sys, time
from threading import Thread, Lock

from evdev.ecodes import ID

sys.path.append(str(Path(__file__).resolve().parents[1]))

from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor
import crazyflie.core.base_utils as base
from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.core.shared_data import State
from crazyflie.constants import MOCAP_TX_RATE_HZ


OFFSET_X = 1 # m
UPDATE_RATE = 10  # Hz
ID = 15
pos = None
lock = Lock()

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
        #print(f"Position from NatNet RB {rigid_body_id}: {pos}, type {type(pos)}")
    
    if count > 0:
        mean_pos = (sum_x / count, sum_y / count, sum_z / count)
        #print(f"\nMean position over {count} samples: {mean_pos}")
        return mean_pos
    else:
        print("\nNo valid positions received")
        return None

def object_tracking(monitor, rigid_body_id, update_rate):
    print(f"Starting object tracking for rigid body ID {rigid_body_id}")
    global pos 
    while True:
            current_pos = get_average_position(monitor, rigid_body_id, update_rate=update_rate)
            if current_pos is not None:
                with lock:
                    pos = current_pos
            


# Natnet monitor setup
monitor = NatNetRigidBodyMonitor()
monitor.start()
time.sleep(5)
# Get average position


object_tracker_thread = Thread(target=object_tracking, args=(monitor, ID, UPDATE_RATE))
object_tracker_thread.start()



cf = CrazyFlie()
cf.logging(enable=True, file=True, level=base.LogLevel.debug)
cf.set_natnet_monitor(monitor)



cf.scan()
cf.connect(start_flying=True)
time.sleep(5)
while True:
    # update the follower position based on the mean position of the rigid body with offset
    with lock:
        p = pos  
    if p is not None:
        cf.fly(State(p[0] + OFFSET_X, p[1], p[2]))
    time.sleep(1.0 / UPDATE_RATE)
