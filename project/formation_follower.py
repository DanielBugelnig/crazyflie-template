from pathlib import Path
import sys, time
from threading import Thread, Lock

sys.path.append(str(Path(__file__).resolve().parents[1]))

from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor
import crazyflie.core.base_utils as base
from crazyflie.bitcraze.swarm import CrazySwarm
from crazyflie.core.shared_data import State
from crazyflie.constants import MOCAP_TX_RATE_HZ
from crazyflie.bitcraze.trajectory import Trajectory



# Configuration
TRACKED_RIGID_BODY_ID = 15  # ID of the rigid body to track
UPDATE_RATE = 10  # Hz

# Formation definition: offset positions (x, y, z) relative to tracked object
# Each entry is (x_offset, y_offset, z_offset) for each drone
FORMATION = [
    (0.8, 0.2, 0.0),   
    (0.8, -0.2, 0.0),   
]

# Global variables
tracked_position = None
position_lock = Lock()


def get_average_position(monitor, rigid_body_id, update_rate=UPDATE_RATE):
    """
    Get the average position of a rigid body over multiple samples.
    
    Args:
        monitor: NatNetRigidBodyMonitor instance
        rigid_body_id: Rigid body ID to track
        update_rate: Update rate in Hz (default: 10)
    
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
    
    if count > 0:
        mean_pos = (sum_x / count, sum_y / count, sum_z / count)
        return mean_pos
    else:
        return None


def object_tracking_thread(monitor, rigid_body_id, update_rate):
    """
    Continuously track the rigid body position in a separate thread.
    """
    print(f"Starting object tracking for rigid body ID {rigid_body_id}")
    global tracked_position
    
    while True:
        current_pos = get_average_position(monitor, rigid_body_id, update_rate=update_rate)
        if current_pos is not None:
            with position_lock:
                tracked_position = current_pos


def calculate_formation_positions(center_pos, formation_offsets):
    """
    Calculate target positions for all drones based on center position and formation offsets.
    
    Args:
        center_pos: (x, y, z) tuple of the tracked center position
        formation_offsets: List of (x, y, z) offset tuples for each drone
    
    Returns:
        List of State objects, one for each drone
    """
    if center_pos is None:
        return None
    
    target_states = []
    for offset in formation_offsets:
        x = center_pos[0] + offset[0]
        y = center_pos[1] + offset[1]
        z = center_pos[2] + offset[2]
        target_states.append(State(x, y, z))
    
    
    return target_states


def main():
    # Initialize NatNet monitor
    print("Initializing NatNet monitor...")
    monitor = NatNetRigidBodyMonitor()
    monitor.start()
    calculator = Trajectory()
    calculator.logging(enable=True, file=True, level=base.LogLevel.info)
    time.sleep(5)
    print("NatNet monitor started")
    
    # Start object tracking thread
    tracker_thread = Thread(target=object_tracking_thread, 
                           args=(monitor, TRACKED_RIGID_BODY_ID, UPDATE_RATE),
                           daemon=True)
    tracker_thread.start()
    
    # Wait for initial position
    print("Waiting for tracked object position...")
    timeout = 10
    start = time.time()
    while tracked_position is None and time.time() - start < timeout:
        time.sleep(0.1)
    
    if tracked_position is None:
        print(f"Error: Could not detect rigid body {TRACKED_RIGID_BODY_ID}")
        return
    
    print(f"Tracked object detected at: {tracked_position}")
    
    # Initialize swarm
    print("Initializing drone swarm...")
    swarm = CrazySwarm()
    swarm.set_delay(0.02)
    swarm.logging(enable=True, file=True, level=base.LogLevel.info)
    swarm.set_natnet_monitor(monitor)
    
    # Scan and connect to drones
    swarm.scan()
    num_drones = swarm.get_count()
    
    if num_drones == 0:
        print("Error: No drones found")
        return
    
    # Adjust formation size to match number of drones
    active_formation = FORMATION[:num_drones]
    print(f"Using formation with {len(active_formation)} positions for {num_drones} drones")
    
    swarm.start()
    swarm.arm()
    time.sleep(3)
    
    print("Starting formation flight...")
    print("Press Ctrl+C to land and exit")
    
    try:
        while True:
            fly = True
            # Get current tracked position
            with position_lock:
                current_center = tracked_position
            
            # Calculate target positions for formation
            target_states = calculate_formation_positions(current_center, active_formation)
            for target in target_states:
                if not calculator.validate_position(target):
                    fly = False
            
            if target_states is not None and fly:
                # Command all drones to their formation positions using swarm API
                swarm.fly(target_states, photo=False)
            
            time.sleep(1.0 / UPDATE_RATE)
            
    except KeyboardInterrupt:
        print("\nLanding drones...")
        swarm.land()
        print("Drones landed")
    
    finally:
        swarm.stop()
        monitor.stop()
        print("Cleanup complete")

if __name__ == "__main__":
    main()
