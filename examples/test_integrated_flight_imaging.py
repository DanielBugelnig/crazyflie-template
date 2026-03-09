"""
Test script for integrated Crazyflie flight control with AI Deck image capture.

This script demonstrates:
  1. Connecting to a single Crazyflie drone
  2. Connecting to its paired AI Deck
  3. Flying a simple square pattern
  4. Capturing and saving images during flight
  5. Landing safely

Prerequisites:
  - A Crazyflie and AI Deck must be powered and discoverable
  - OptiTrack system must be running for localization
  - AI Deck must be on the configured Wi-Fi network

Author:
  Generated for testing purposes
"""

from pathlib import Path
import sys
import time
from threading import Thread, Event

sys.path.append(str(Path(__file__).resolve().parents[1]))

from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.bitcraze.ai_deck import AI_Deck
from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor
import crazyflie.core.base_utils as base
from crazyflie.core.shared_data import State
from crazyflie.constants import MAC_LOOKUP


# Configuration
FLIGHT_HEIGHT = 0.5  # meters
FLIGHT_SPEED = 1.0  # seconds to reach each waypoint

# Simple square flight pattern (relative to starting position)
WAYPOINTS = [
    (0.0, 0.0, FLIGHT_HEIGHT),    # Start position
    (1.0, 0.0, FLIGHT_HEIGHT),    # Right
    (1.0, 1.0, FLIGHT_HEIGHT),    # Forward-Right
    (0.0, 1.0, FLIGHT_HEIGHT),    # Forward
    (0.0, 0.0, FLIGHT_HEIGHT),    # Back to start
]


def image_streaming_thread(ai_deck, stop_event):
    """Background thread to continuously stream and save images.
    
    Args:
        ai_deck: AI_Deck instance
        stop_event: Threading event to signal thread to stop
    """
    print("Image streaming thread started")
    image_count = 0
    try:
        while not stop_event.is_set():
            try:
                if ai_deck.save_image():
                    image_count += 1
                    # Only print every 5th image to reduce spam
                    if image_count % 5 == 0:
                        print(f"  [Streaming] Captured {image_count} images total")
            except Exception as e:
                print(f"  [Streaming] Error saving image: {e}")
            time.sleep(0.05)  # Small delay to avoid CPU spinning
    except Exception as e:
        print(f"  [Streaming] Thread error: {e}")
    print(f"Image streaming complete - total images: {image_count}")


def main():
    print("=" * 70)
    print("Crazyflie + AI Deck Integrated Test")
    print("=" * 70)
    
    # Initialize logging
    print("\n[1/6] Initializing logging...")
    
    # Initialize Crazyflie
    print("\n[2/6] Initializing Crazyflie...")
    cf = CrazyFlie()
    cf.logging(enable=True, file=True, level=base.LogLevel.info)
    
    # Initialize OptiTrack for localization
    print("\n[3/6] Initializing OptiTrack monitor...")
    try:
        monitor = NatNetRigidBodyMonitor()
        monitor.start()
        cf.set_natnet_monitor(monitor)
        time.sleep(2)
        print("  OptiTrack monitor started")
    except Exception as e:
        print(f"  Warning: OptiTrack initialization failed: {e}")
        print("  Continuing without localization...")
        monitor = None
    
    # Scan and connect to Crazyflie
    print("\n[4/6] Scanning and connecting to Crazyflie...")
    try:
        cf.scan()
        cf.connect(start_flying=True, localization_mode="Optitrack")
        print(f"  Connected to: {cf._name}")
        time.sleep(2)
    except Exception as e:
        print(f"  ERROR: Failed to connect to Crazyflie: {e}")
        return
    
    # Get starting position
    print("\n[5/6] Getting initial position...")
    try:
        starting_pos = cf.get_state()
        print(f"  Starting position: x={starting_pos.get_x():.2f}, y={starting_pos.get_y():.2f}, z={starting_pos.get_z():.2f}")
    except Exception as e:
        print(f"  Warning: Could not get initial position: {e}")
        starting_pos = State(0, 0, 0, 0)
    
    # Initialize and connect AI Deck
    print("\n[6/6] Initializing and connecting AI Deck...")
    ai_deck = None
    image_thread = None
    stop_streaming = Event()
    
    try:
        # Try to find AI Deck paired with this Crazyflie
        ai_mac = MAC_LOOKUP.get(cf._address, "")
        print(f"  Looking for AI Deck with MAC: {ai_mac}")
        
        ai_deck = AI_Deck(mac=ai_mac)
        ai_deck.logging(enable=True, file=True, level=base.LogLevel.info)
        ai_deck.set_display(True)  # Display images if possible
        ai_deck.set_delay(0.1)
        
        # Scan for AI Deck on network
        ai_deck.scan()
        print(f"  AI Deck found at: {ai_deck._ip}")
        
        # Connect to AI Deck
        ai_deck.connect()
        print(f"  Connected to AI Deck")
        
        # Start continuous image streaming thread
        image_thread = Thread(
            target=image_streaming_thread,
            args=(ai_deck, stop_streaming),
            daemon=False
        )
        image_thread.start()
        
    except Exception as e:
        print(f"  Warning: AI Deck connection failed: {e}")
        print(f"  Continuing with flight test only...")
        ai_deck = None
    
    # Perform flight test
    print("\n" + "=" * 70)
    print("FLIGHT TEST: Square Pattern")
    print("=" * 70)
    
    try:
        # Arm the drone
        print("\n[FLIGHT] Arming drone...")
        time.sleep(1)
        
        # Fly waypoints
        for idx, (x_offset, y_offset, z) in enumerate(WAYPOINTS):
            target = State(
                x=starting_pos.get_x() + x_offset,
                y=starting_pos.get_y() + y_offset,
                z=z,
                yaw=0.0
            )
            
            print(f"\n[FLIGHT] Waypoint {idx+1}/{len(WAYPOINTS)}: Flying to ({x_offset:.1f}, {y_offset:.1f}, {z:.1f})")
            cf.fly(target)
            
            # Wait for drone to arrive (with timeout)
            start_time = time.time()
            timeout = 30  # seconds
            while not cf.arrived(target, fine=False):
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    print(f"  Timeout waiting for arrival (elapsed: {elapsed:.1f}s)")
                    break
                
                current_pos = cf.get_state()
                dist = ((current_pos.get_x() - target.get_x())**2 + 
                       (current_pos.get_y() - target.get_y())**2 + 
                       (current_pos.get_z() - target.get_z())**2) ** 0.5
                
                print(f"  Current: ({current_pos.get_x():.2f}, {current_pos.get_y():.2f}, {current_pos.get_z():.2f}) | Distance: {dist:.2f}m", end='\r')
                time.sleep(0.5)
            
            print(f"  Arrived at waypoint {idx+1}")
            time.sleep(1)
        
        # Land
        print("\n[FLIGHT] Landing drone...")
        cf.land()
        time.sleep(3)
        print("  Drone landed")
        
    except Exception as e:
        print(f"\nERROR during flight: {e}")
        print("Attempting emergency landing...")
        try:
            cf.land()
        except:
            pass
    
    # Cleanup
    print("\n" + "=" * 70)
    print("CLEANUP")
    print("=" * 70)
    
    # Stop image streaming
    print("\nStopping image streaming...")
    stop_streaming.set()
    
    # Wait for image thread to finish
    if image_thread:
        image_thread.join(timeout=5)
        if ai_deck:
            print(f"Total images captured: {ai_deck.get_image_count()}")
    
    # Disconnect
    print("\nDisconnecting...")
    try:
        cf.disconnect()
        print("  Crazyflie disconnected")
    except:
        pass
    
    if ai_deck:
        try:
            ai_deck.disconnect()
            print("  AI Deck disconnected")
        except:
            pass
    
    if monitor:
        try:
            monitor.stop()
            print("  OptiTrack monitor stopped")
        except:
            pass
    
    print("\nTest complete!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
