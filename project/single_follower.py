from pathlib import Path
import sys, time
from threading import Thread, Lock
from collections import deque
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import math

sys.path.append(str(Path(__file__).resolve().parents[1]))

from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor
import crazyflie.core.base_utils as base
from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.core.shared_data import State
from crazyflie.constants import MOCAP_TX_RATE_HZ


OFFSET_X = 1 # m
UPDATE_RATE = 10  # Hz
ID = 44
pos = None
lock = Lock()

def calculate_offset_position(target_pos, offset_distance):
    """
    Calculate drone position along the line from target through origin (0, 0).
    
    Args:
        target_pos: tuple (x, y, z) - wand/target position
        offset_distance: distance to offset from target toward origin
    
    Returns:
        tuple (x, y, z) - drone target position
    """
    tx, ty, tz = target_pos
    
    # Calculate direction from target toward origin in XY plane
    distance_to_origin = math.sqrt(tx**2 + ty**2)
    
    if distance_to_origin < 0.01:  # Target very close to origin
        return target_pos
    
    # Normalize direction vector from target toward origin
    dir_x = -tx / distance_to_origin
    dir_y = -ty / distance_to_origin
    
    # Position offset from target toward origin
    offset_x = tx + offset_distance * dir_x
    offset_y = ty + offset_distance * dir_y
    
    return (offset_x, offset_y, tz)

# Data tracking for plotting
MAX_HISTORY = 300  # Keep last 300 samples (~30 seconds at 10 Hz)
drone_positions = deque(maxlen=MAX_HISTORY)
target_positions = deque(maxlen=MAX_HISTORY)
timestamps = deque(maxlen=MAX_HISTORY)
data_lock = Lock()
start_time = time.time()
live_animation = None

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

def plot_live_data():
    """
    Create a live updating plot showing drone and target positions.
    """
    plt.style.use('seaborn-v0_8-darkgrid')
    fig = plt.figure(figsize=(15, 10))
    
    # 3D scatter plot
    ax1 = fig.add_subplot(2, 2, 1, projection='3d')
    # XY top-down view
    ax2 = fig.add_subplot(2, 2, 2)
    # XZ side view
    ax3 = fig.add_subplot(2, 2, 3)
    # YZ side view
    ax4 = fig.add_subplot(2, 2, 4)
    
    plt.tight_layout(pad=3.0)
    
    def update(frame):
        with data_lock:
            if not drone_positions or not target_positions:
                return
            
            drone_pos = list(drone_positions)
            target_pos = list(target_positions)
            
        # Extract coordinates
        if drone_pos:
            drone_x = [p[0] for p in drone_pos]
            drone_y = [p[1] for p in drone_pos]
            drone_z = [p[2] for p in drone_pos]
        else:
            drone_x = drone_y = drone_z = []
            
        if target_pos:
            target_x = [p[0] for p in target_pos]
            target_y = [p[1] for p in target_pos]
            target_z = [p[2] for p in target_pos]
        else:
            target_x = target_y = target_z = []
        
        # Clear previous plots
        ax1.clear()
        ax2.clear()
        ax3.clear()
        ax4.clear()
        
        # 3D scatter plot
        if drone_x:
            ax1.plot(drone_x, drone_y, drone_z, 'b-', label='Drone path', linewidth=2, alpha=0.7)
            ax1.scatter(drone_x[-1:], drone_y[-1:], drone_z[-1:], c='blue', s=100, marker='o', label='Drone')
        if target_x:
            ax1.plot(target_x, target_y, target_z, 'r-', label='Target path', linewidth=2, alpha=0.7)
            ax1.scatter(target_x[-1:], target_y[-1:], target_z[-1:], c='red', s=100, marker='s', label='Target')
        ax1.set_xlabel('X (m)')
        ax1.set_ylabel('Y (m)')
        ax1.set_zlabel('Z (m)')
        ax1.set_title('3D Position Tracking')
        ax1.legend()
        
        # XY top-down view
        if drone_x:
            ax2.plot(drone_x, drone_y, 'b-', label='Drone', linewidth=2, alpha=0.7)
            ax2.scatter(drone_x[-1:], drone_y[-1:], c='blue', s=100, marker='o')
        if target_x:
            ax2.plot(target_x, target_y, 'r-', label='Target', linewidth=2, alpha=0.7)
            ax2.scatter(target_x[-1:], target_y[-1:], c='red', s=100, marker='s')
        ax2.set_xlabel('X (m)')
        ax2.set_ylabel('Y (m)')
        ax2.set_title('Top-Down View (XY)')
        ax2.legend()
        ax2.grid(True)
        ax2.axis('equal')
        
        # XZ side view
        if drone_x:
            ax3.plot(drone_x, drone_z, 'b-', label='Drone', linewidth=2, alpha=0.7)
            ax3.scatter(drone_x[-1:], drone_z[-1:], c='blue', s=100, marker='o')
        if target_x:
            ax3.plot(target_x, target_z, 'r-', label='Target', linewidth=2, alpha=0.7)
            ax3.scatter(target_x[-1:], target_z[-1:], c='red', s=100, marker='s')
        ax3.set_xlabel('X (m)')
        ax3.set_ylabel('Z (m)')
        ax3.set_title('Side View (XZ)')
        ax3.legend()
        ax3.grid(True)
        
        # YZ side view
        if drone_y:
            ax4.plot(drone_y, drone_z, 'b-', label='Drone', linewidth=2, alpha=0.7)
            ax4.scatter(drone_y[-1:], drone_z[-1:], c='blue', s=100, marker='o')
        if target_y:
            ax4.plot(target_y, target_z, 'r-', label='Target', linewidth=2, alpha=0.7)
            ax4.scatter(target_y[-1:], target_z[-1:], c='red', s=100, marker='s')
        ax4.set_xlabel('Y (m)')
        ax4.set_ylabel('Z (m)')
        ax4.set_title('Side View (YZ)')
        ax4.legend()
        ax4.grid(True)
        
        plt.suptitle(f'Crazyflie Follower - Live Tracking ({time.time() - start_time:.1f}s)', fontsize=14, fontweight='bold')
    
    global live_animation
    live_animation = FuncAnimation(fig, update, interval=100, cache_frame_data=False)
    plt.show()

def object_tracking(monitor, rigid_body_id, update_rate):
    print(f"Starting object tracking for rigid body ID {rigid_body_id}")
    global pos 
    latest_pose = None
    while True:
            current_pos = get_average_position(monitor, rigid_body_id, update_rate=update_rate)
            if current_pos is not None:
                with lock:
                    pos = current_pos
                    latest_pose = current_pos
                with data_lock:
                    target_positions.append(current_pos)
            else:
                pos = latest_pose


def flight_control(cf, update_rate):
    while True:
        # update the follower position based on the mean position of the rigid body with offset
        with lock:
            p = pos
        if p is not None:
            #offset_pos = calculate_offset_position(p, OFFSET_X) # for circling around
            offset_pos = [p[0] + OFFSET_X, p[1], p[2]]
            target_pos = State(offset_pos[0], offset_pos[1], offset_pos[2])
            cf.fly(target_pos)
            # Track drone position
            with data_lock:
                drone_positions.append((target_pos.x, target_pos.y, target_pos.z))
        time.sleep(1.0 / update_rate)


# Natnet monitor setup
monitor = NatNetRigidBodyMonitor()
monitor.start()
time.sleep(5)
# Get average position


object_tracker_thread = Thread(target=object_tracking, args=(monitor, ID, UPDATE_RATE))
object_tracker_thread.daemon = True
object_tracker_thread.start()



cf = CrazyFlie()
cf.logging(enable=True, file=True, level=base.LogLevel.debug)
cf.set_natnet_monitor(monitor)



cf.scan()
cf.connect(start_flying=True)
time.sleep(5)

flight_thread = Thread(target=flight_control, args=(cf, UPDATE_RATE), daemon=True)
flight_thread.start()

# Run plotting on main thread (required by Matplotlib GUI backends)
#plot_live_data()
