"""
Test script for CrazyFlie localization mode selection.

This script demonstrates:
- Automatic localization mode selection based on detected decks
- Manual localization mode selection (Optitrack, Flow, Loco)
- EKF seeding with external position (Optitrack)
- External position streaming

Author: Daniel Bugelnig (daniel.bugelnig@aau.at)
Date: 2026
"""

import sys
from pathlib import Path
from time import sleep
import argparse


sys.path.insert(0, str(Path(__file__).parent.parent))

from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.core.base_utils import LogLevel
from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor
from crazyflie.constants import RIGID_BODY_ID_LOOKUP


def test_localization_auto(address=None):
    """Test automatic localization mode selection."""
    cf = CrazyFlie(address if address else "")
    cf.logging(enable=True, file=False, level=LogLevel.info)
    
    cf.print("=" * 60, cf.LogLevel.message)
    cf.print("TEST: Automatic Localization Mode", cf.LogLevel.message)
    cf.print("=" * 60, cf.LogLevel.message)
    
    try:
        cf.print("\n[Setup] Connecting...", cf.LogLevel.info)
        if address:
            cf.scan(specific=address)
        else:
            cf.scan()
        
        cf.test_mode(True)
        cf.connect(start_flying=False)
        sleep(2)
        
        cf.print("\n[Test 1] Testing automatic localization mode selection...", cf.LogLevel.info)
        cf.select_localization_mode(specific=None)
        cf.print(f"Selected mode: {cf.positioning_mode}", cf.LogLevel.info)
        
        cf.disconnect()
        cf.print("\nTest completed", cf.LogLevel.message)
        
    except Exception as e:
        cf.print(f"\nTEST FAILED: {e}", cf.LogLevel.error)
        try:
            cf.disconnect()
        except:
            pass
        raise


def test_localization_optitrack(address=None):
    """Test Optitrack localization mode."""
    cf = CrazyFlie(address if address else "")
    cf.logging(enable=True, file=False, level=LogLevel.info)
    
    cf.print("=" * 60, cf.LogLevel.message)
    cf.print("TEST: Optitrack Localization Mode", cf.LogLevel.message)
    cf.print("=" * 60, cf.LogLevel.message)
    
    try:
        cf.print("\n[Setup] Connecting...", cf.LogLevel.info)
        if address:
            cf.scan(specific=address)
        else:
            cf.scan()
        
        # Setup NatNet monitor for Optitrack
        cf.print(f"\n[Setup] Initializing Optitrack connection...", cf.LogLevel.info)
        try:
            monitor = NatNetRigidBodyMonitor()
            cf.set_natnet_monitor(monitor)
            cf.print("NatNet monitor initialized", cf.LogLevel.info)
        except Exception as e:
            cf.print(f"Warning: Could not initialize NatNet monitor: {e}", cf.LogLevel.warning)
            cf.print("  Continuing with test mode...", cf.LogLevel.warning)
        
        cf.test_mode(False)  # Need actual flight init for Optitrack
        
        cf.print("\n[Test 1] Connecting with Optitrack localization...", cf.LogLevel.info)
        cf.connect(start_flying=False, localization_mode="Optitrack")
        sleep(2)
        cf.print(f"Connected with mode: {cf.positioning_mode}", cf.LogLevel.info)
        
        cf.print("\n[Test 2] Checking external position streaming thread...", cf.LogLevel.info)
        if cf.ext_pos_thread and cf.ext_pos_thread.is_alive():
            cf.print("External position streaming active", cf.LogLevel.info)
            
            # Monitor for a few seconds
            cf.print("\n[Test 3] Monitoring position updates for 5 seconds...", cf.LogLevel.info)
            for i in range(5):
                sleep(1)
                state = cf.get_state()
                cf.print(f"  [{i+1}/5] Pos: ({state.x:.3f}, {state.y:.3f}, {state.z:.3f})", cf.LogLevel.info)
        else:
            cf.print("External position streaming not active (expected if no Optitrack)", cf.LogLevel.warning)
        
        cf.disconnect()
        cf.print("\n✓ Test completed", cf.LogLevel.message)
        
    except Exception as e:
        cf.print(f"\nTEST FAILED: {e}", cf.LogLevel.error)
        try:
            cf.disconnect()
        except:
            pass
        raise


def test_localization_flow(address=None):
    """Test Flow deck localization mode."""
    cf = CrazyFlie(address if address else "")
    cf.logging(enable=True, file=False, level=LogLevel.info)
    
    cf.print("=" * 60, cf.LogLevel.message)
    cf.print("TEST: Flow Deck Localization Mode", cf.LogLevel.message)
    cf.print("=" * 60, cf.LogLevel.message)
    
    try:
        cf.print("\n[Setup] Connecting...", cf.LogLevel.info)
        if address:
            cf.scan(specific=address)
        else:
            cf.scan()
        
        cf.test_mode(True)
        cf.connect(start_flying=False)
        sleep(2)
        
        cf.print("\n[Test 1] Checking for Flow deck...", cf.LogLevel.info)
        has_flow = cf.checking_decks(specific="bcFlow2") or cf.checking_decks(specific="bcFlow")
        
        if has_flow:
            cf.print("Flow deck detected", cf.LogLevel.info)
            cf.print("\n[Test 2] Selecting Flow localization mode...", cf.LogLevel.info)
            cf.select_localization_mode(specific="Flow")
            assert cf.positioning_mode == "Flow", "Flow mode not activated"
            cf.print(f"Mode set: {cf.positioning_mode}", cf.LogLevel.info)
        else:
            cf.print("No Flow deck detected, will fallback to Optitrack", cf.LogLevel.warning)
            cf.select_localization_mode(specific="Flow")
            cf.print(f"Fallback mode: {cf.positioning_mode}", cf.LogLevel.info)
        
        cf.disconnect()
        cf.print("\nTest completed", cf.LogLevel.message)
        
    except Exception as e:
        cf.print(f"\nTEST FAILED: {e}", cf.LogLevel.error)
        try:
            cf.disconnect()
        except:
            pass
        raise


def test_localization_loco(address=None):
    """Test Loco Positioning System mode."""
    cf = CrazyFlie(address if address else "")
    cf.logging(enable=True, file=False, level=LogLevel.info)
    
    cf.print("=" * 60, cf.LogLevel.message)
    cf.print("TEST: Loco Positioning System", cf.LogLevel.message)
    cf.print("=" * 60, cf.LogLevel.message)
    
    try:
        cf.print("\n[Setup] Connecting...", cf.LogLevel.info)
        if address:
            cf.scan(specific=address)
        else:
            cf.scan()
        
        cf.test_mode(True)
        cf.connect(start_flying=False)
        sleep(2)
        
        cf.print("\n[Test 1] Checking for Loco deck...", cf.LogLevel.info)
        has_loco = cf.checking_decks(specific="bcLoco")
        
        if has_loco:
            cf.print("Loco deck detected", cf.LogLevel.info)
            cf.print("\n[Test 2] Selecting Loco localization mode...", cf.LogLevel.info)
            cf.select_localization_mode(specific="Loco")
            assert cf.positioning_mode == "Loco", "Loco mode not activated"
            cf.print(f"Mode set: {cf.positioning_mode}", cf.LogLevel.info)
        else:
            cf.print("No Loco deck detected, will fallback to Optitrack", cf.LogLevel.warning)
            cf.select_localization_mode(specific="Loco")
            cf.print(f"Fallback mode: {cf.positioning_mode}", cf.LogLevel.info)
        
        cf.disconnect()
        cf.print("\nTest completed", cf.LogLevel.message)
        
    except Exception as e:
        cf.print(f"\nTEST FAILED: {e}", cf.LogLevel.error)
        try:
            cf.disconnect()
        except:
            pass
        raise


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Test CrazyFlie localization modes")
    parser.add_argument("--address", type=str, help="Drone URI") # if not provided, will scan for any drone listed in the config
    parser.add_argument("--mode", type=str, choices=["auto", "optitrack", "flow", "loco", "all"],
                       default="auto", help="Which mode to test")

    
    args = parser.parse_args()
    
    if args.mode == "all" or args.mode == "auto":
        test_localization_auto(args.address)
        print("\n")
    
    if args.mode == "all" or args.mode == "optitrack":
        test_localization_optitrack(args.address)
        print("\n")
    
    if args.mode == "all" or args.mode == "flow":
        test_localization_flow(args.address)
        print("\n")
    
    if args.mode == "all" or args.mode == "loco":
        test_localization_loco(args.address)
