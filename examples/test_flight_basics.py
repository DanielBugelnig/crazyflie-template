"""
Test script for basic flight operations (requires Optitrack or similar localization).

WARNING: This test involves actual flight! 
- Ensure the flight area is clear
- Immediate control by pressing CTRL + ALT + q(stop motors), CTRL + ALT + l(land)
- Have the drone on a flat surface
- Ensure localization system is active (for opitrack, the natnet montor must be initialized)

This script demonstrates:
- Taking off to hover position
- Flying to waypoints
- Checking arrival at positions
- Landing safely

Author: Daniel Bugelnig (daniel.bugelnig@aau.at)
Date: 2026
"""

import sys
from pathlib import Path
from time import sleep

sys.path.insert(0, str(Path(__file__).parent.parent))

from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.core.base_utils import LogLevel
from crazyflie.core.shared_data import State
from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor


def test_hover(address=None, hover_height=0.5, duration=10):
    """Test simple hover at specified height."""
    cf = CrazyFlie(address if address else "")
    cf.logging(enable=True, file=False, level=LogLevel.info)
    
    cf.print("=" * 60, cf.LogLevel.message)
    cf.print("TEST: Basic Hover", cf.LogLevel.message)
    cf.print("WARNING: DRONE WILL FLY!", cf.LogLevel.warning)
    cf.print("=" * 60, cf.LogLevel.message)
    
    input("Press ENTER to continue or Ctrl+C to abort...")
    
    try:
        cf.print("\n[Setup] Connecting...", cf.LogLevel.info)
        if address:
            cf.scan(specific=address)
        else:
            cf.scan()
        
        # only needed for flying with optitrack localization
        monitor = NatNetRigidBodyMonitor()
        cf.set_natnet_monitor(monitor)
        
        cf.print("[Setup] Connecting to drone with Optitrack localization...", cf.LogLevel.info)
        cf.connect(start_flying=True, localization_mode="Optitrack")
        sleep(3)
        
        # Get initial position
        cf.print("\n[Test 1] Reading initial position...", cf.LogLevel.info)
        initial_pos = cf.get_state()
        cf.print(f"Start position: ({initial_pos.x:.2f}, {initial_pos.y:.2f}, {initial_pos.z:.2f})", cf.LogLevel.info)
        # Verify if the coordinates are reasonable
        
        # Create hover position
        cf.print(f"\n[Test 2] Taking off to {hover_height}m...", cf.LogLevel.info)
        hover_pos = State()
        hover_pos.x = initial_pos.x
        hover_pos.y = initial_pos.y
        hover_pos.z = hover_height
        hover_pos.yaw = initial_pos.yaw
        
        cf.fly(hover_pos)
        
        # Wait for arrival
        cf.print("Waiting for arrival...", cf.LogLevel.info)
        timeout = 30
        elapsed = 0
        while not cf.arrived(hover_pos, fine=True) and elapsed < timeout:
            sleep(0.2)
            elapsed += 0.2
            current = cf.get_state()
            cf.print(f"  Height: {current.z:.3f}m / {hover_height}m", cf.LogLevel.debug)
        
        if elapsed >= timeout:
            cf.print("Timeout waiting for arrival, landing...", cf.LogLevel.warning)
        else:
            cf.print(f"Arrived at hover position in {elapsed:.1f}s", cf.LogLevel.info)
            
            # Hover for specified duration
            cf.print(f"\n[Test 3] Hovering for {duration} seconds...", cf.LogLevel.info)
            for i in range(duration):
                sleep(1)
                state = cf.get_state()
                cf.print(f"  [{i+1}/{duration}] Pos: ({state.x:.2f}, {state.y:.2f}, {state.z:.2f}), "
                      f"Battery: {state.battery:.2f}V", cf.LogLevel.info)
        
        # Land
        cf.print("\n[Test 4] Landing...", cf.LogLevel.info)
        cf.land()
        
        # Wait for landing
        sleep(5)
        final_pos = cf.get_state()
        cf.print(f"Landed at height: {final_pos.z:.3f}m", cf.LogLevel.info)
        
        cf.disconnect()
        cf.print("\nTest completed successfully", cf.LogLevel.message)
        
    except KeyboardInterrupt:
        cf.print("\nTest interrupted! Emergency landing...", cf.LogLevel.warning)
        try:
            cf.land()
            sleep(3)
            cf.disconnect()
        except:
            pass
    except Exception as e:
        cf.print(f"\nTEST FAILED: {e}", cf.LogLevel.error)
        try:
            cf.land()
            sleep(3)
            cf.disconnect()
        except:
            pass
        raise


def test_waypoint_flight(address=None):
    """Test flying to multiple waypoints."""
    cf = CrazyFlie(address if address else "")
    cf.logging(enable=True, file=True, level=LogLevel.debug)
    
    cf.print("=" * 60, cf.LogLevel.message)
    cf.print("TEST: Waypoint Flight", cf.LogLevel.message)
    cf.print("WARNING: DRONE WILL FLY!", cf.LogLevel.warning)
    cf.print("=" * 60, cf.LogLevel.message)
    
    input("Press ENTER to continue or Ctrl+C to abort...")
    
    try:
        cf.print("\n[Setup] Connecting...", cf.LogLevel.info)
        if address:
            cf.scan(specific=address)
        else:
            cf.scan()
        
        monitor = NatNetRigidBodyMonitor()
        cf.set_natnet_monitor(monitor)
        
        cf.connect(start_flying=True, localization_mode="Optitrack")
        sleep(3)
        
        # Get initial position
        initial_pos = cf.get_state()
        cf.print(f"Initial position: ({initial_pos.x:.2f}, {initial_pos.y:.2f}, {initial_pos.z:.2f})", cf.LogLevel.info)
        
        # Define waypoints (relative to start)
        waypoints = [
            State(x=initial_pos.x, y=initial_pos.y, z=0.5, yaw=0),  # Takeoff
            State(x=initial_pos.x + 0.3, y=initial_pos.y, z=0.5, yaw=0),  # Forward
            State(x=initial_pos.x + 0.3, y=initial_pos.y + 0.3, z=0.5, yaw=90),  # Right + rotate
            State(x=initial_pos.x, y=initial_pos.y + 0.3, z=0.5, yaw=180),  # Back + rotate
            State(x=initial_pos.x, y=initial_pos.y, z=0.5, yaw=0),  # Return to start
        ]
        
        cf.print(f"\n[Test] Flying through {len(waypoints)} waypoints...", cf.LogLevel.info)
        
        for i, wp in enumerate(waypoints, 1):
            cf.print(f"\n--- Waypoint {i}/{len(waypoints)} ---", cf.LogLevel.info)
            cf.print(f"Target: ({wp.x:.2f}, {wp.y:.2f}, {wp.z:.2f}), yaw={wp.yaw:.0f}°", cf.LogLevel.info)
            
            cf.fly(wp)
            
            # Wait for arrival
            timeout = 30
            elapsed = 0
            while not cf.arrived(wp, fine=True) and elapsed < timeout:
                sleep(0.1)
                elapsed += 0.1
                if elapsed % 5 == 0:  # Print every 2 seconds
                    current = cf.get_state()
                    cf.print(f"  Current: ({current.x:.2f}, {current.y:.2f}, {current.z:.2f})", cf.LogLevel.debug)
            
            if elapsed >= timeout:
                cf.print("Timeout, moving to next waypoint...", cf.LogLevel.warning)
            else:
                cf.print(f"Arrived in {elapsed:.1f}s", cf.LogLevel.info)
                sleep(2)  # Pause at waypoint
        
        # Land
        cf.print("\n[Cleanup] Landing...", cf.LogLevel.info)
        cf.land()
        sleep(5)
        
        cf.disconnect()
        cf.print("\nTest completed successfully", cf.LogLevel.message)
        
    except KeyboardInterrupt:
        cf.print("\nTest interrupted! Emergency landing...", cf.LogLevel.warning)
        try:
            cf.land()
            sleep(3)
            cf.disconnect()
        except:
            pass
    except Exception as e:
        cf.print(f"\nTEST FAILED: {e}", cf.LogLevel.error)
        try:
            cf.land()
            sleep(3)
            cf.disconnect()
        except:
            pass
        raise



if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test CrazyFlie flight operations")
    parser.add_argument("--address", type=str, help="Drone URI")
    parser.add_argument("--test", type=str, choices=["hover", "waypoints"],
                       default="hover", help="Which test to run")
    parser.add_argument("--optitrack-server", type=str, default="127.0.0.1",
                       help="Optitrack server IP")
    parser.add_argument("--hover-height", type=float, default=0.5,
                       help="Hover height in meters")
    parser.add_argument("--hover-duration", type=int, default=10,
                       help="Hover duration in seconds")
    
    args = parser.parse_args()
    
    if args.test == "hover":
        test_hover(args.address, args.hover_height, args.hover_duration)
    elif args.test == "waypoints":
        test_waypoint_flight(args.address)

