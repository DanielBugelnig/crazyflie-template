"""
Test script for basic CrazyFlie connection and disconnection.

This script demonstrates:
- Scanning for available drones
- Connecting to a drone
- Reading connection state
- Getting current state (position, battery)
- Disconnecting safely

Author: Daniel Bugelnig (daniel.bugelnig@aau.at)
Date: 2026
"""

import sys
from pathlib import Path
from time import sleep

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.core.base_utils import LogLevel


def test_basic_connection(address=None):
    """Test basic connection and disconnection."""
    # Initialize CrazyFlie object first
    cf = CrazyFlie(address if address else "")
    cf.logging(enable=True, file=False, level=LogLevel.info)
    
    cf.print("=" * 60, cf.LogLevel.message)
    cf.print("TEST: Basic Connection", cf.LogLevel.message)
    cf.print("=" * 60, cf.LogLevel.message)
    
    try:
        # Test 1: Scan for drones
        cf.print("\n[Test 1] Scanning for drones...", cf.LogLevel.info)
        if address:
            cf.scan(specific=address)
        else:
            cf.scan()
        cf.print(f"Found drone at: {cf._address}", cf.LogLevel.info)
        
        # Test 2: Check connection state before connecting
        cf.print("\n[Test 2] Checking initial connection state...", cf.LogLevel.info)
        state = cf.get_connection_state()
        cf.print(f"Connection state: {state}", cf.LogLevel.info)
        assert state == "not initialized", "Expected 'not initialized' state"
        
        # Test 3: Enable test mode (no flight)
        cf.print("\n[Test 3] Enabling test mode...", cf.LogLevel.info)
        cf.test_mode(True)
        cf.print("Test mode enabled (flight disabled)", cf.LogLevel.info)
        
        # Test 4: Connect to drone
        cf.print("\n[Test 4] Connecting to drone...", cf.LogLevel.info)
        cf.connect(start_flying=False)
        sleep(2)  # Allow connection to stabilize
        state = cf.get_connection_state()
        cf.print(f"Connected! State: {state}", cf.LogLevel.info)
        
        # Test 5: Get current state
        cf.print("\n[Test 5] Reading drone state...", cf.LogLevel.info)
        drone_state = cf.get_state()
        cf.print(f"Position: x={drone_state.x:.2f}, y={drone_state.y:.2f}, z={drone_state.z:.2f}", cf.LogLevel.info)
        cf.print(f"Attitude: roll={drone_state.roll:.2f}, pitch={drone_state.pitch:.2f}, yaw={drone_state.yaw:.2f}", cf.LogLevel.info)
        cf.print(f"Battery: {drone_state.battery:.2f}V", cf.LogLevel.info)
        
        # Test 6: Wait for state updates
        cf.print("\n[Test 6] Monitoring state updates for 5 seconds...", cf.LogLevel.info)
        for i in range(5):
            sleep(1)
            state = cf.get_state()
            cf.print(f"  [{i+1}/5] Battery: {state.battery:.2f}V, Z: {state.z:.3f}m", cf.LogLevel.info)
        cf.print("State monitoring complete", cf.LogLevel.info)
        
        # Test 7: Disconnect
        cf.print("\n[Test 7] Disconnecting...", cf.LogLevel.info)
        cf.disconnect()
        sleep(1)
        state = cf.get_connection_state()
        cf.print(f"Disconnected! State: {state}", cf.LogLevel.info)
        
        cf.print("\n" + "=" * 60, cf.LogLevel.message)
        cf.print("ALL TESTS PASSED!", cf.LogLevel.message)
        cf.print("=" * 60, cf.LogLevel.message)
        
    except Exception as e:
        cf.print(f"\nTEST FAILED: {e}", cf.LogLevel.error)
        try:
            cf.disconnect()
        except:
            pass
        raise


if __name__ == "__main__":
    # You can specify a drone address or let it scan
    # test_basic_connection("radio://0/90/2M/E7E7E7E701")
    test_basic_connection()
