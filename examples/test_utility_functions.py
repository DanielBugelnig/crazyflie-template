"""
Test script for CrazyFlie utility functions.

This script demonstrates:
- Battery monitoring and charge state
- Propeller self-test
- Position averaging and saving
- Keyboard controls (emergency stop with 'q', land with 'l')
- Various configuration options

Author: Test Suite
Date: 2026
"""

import sys
from pathlib import Path
from time import sleep
from datetime import datetime
sys.path.insert(0, str(Path(__file__).parent.parent))


from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor


from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.core.base_utils import LogLevel


def test_propeller_test(address=None):
    """Test the propeller self-test function."""
    cf = CrazyFlie(address if address else "")
    cf.logging(enable=True, file=False, level=LogLevel.info)
    
    cf.print("=" * 60, cf.LogLevel.message)
    cf.print("TEST: Propeller Self-Test", cf.LogLevel.message)
    cf.print("=" * 60, cf.LogLevel.message)
    cf.print("\nPlace drone on flat surface", cf.LogLevel.warning)
    cf.print("Ensure propellers can spin freely", cf.LogLevel.warning)
    cf.print("Stand clear of propellers", cf.LogLevel.warning)
    
    input("\nPress ENTER to continue or Ctrl+C to abort...")
    
    try:
        cf.print("\n[Setup] Connecting...", cf.LogLevel.info)
        if address:
            cf.scan(specific=address)
        else:
            cf.scan()
        
        cf.print("\n[Test] Running propeller test...", cf.LogLevel.info)
        cf.test_fans()
        cf.print("Propeller test completed", cf.LogLevel.info)
        
        cf.disconnect()
        cf.print("\nTest completed", cf.LogLevel.message)
        
    except Exception as e:
        cf.print(f"\nTEST FAILED: {e}", cf.LogLevel.error)
        try:
            cf.disconnect()
        except:
            pass
        raise


def test_battery_monitoring(address=None, duration=10):
    """Test battery voltage monitoring."""
    cf = CrazyFlie(address if address else "")
    cf.logging(enable=True, file=False, level=LogLevel.info)
    
    cf.print("=" * 60, cf.LogLevel.message)
    cf.print("TEST: Battery Monitoring", cf.LogLevel.message)
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
        
        cf.print(f"\n[Test] Monitoring battery for {duration} seconds...", cf.LogLevel.info)
        cf.print("Time (s) | Voltage (V) | Status", cf.LogLevel.info)
        cf.print("-" * 40, cf.LogLevel.info)
        
        from crazyflie.constants import LOW_BATTERY
        
        for i in range(duration):
            sleep(1)
            state = cf.get_state()
            status = "OK"
            if state.battery <= LOW_BATTERY:
                status = "⚠ LOW!"
            elif state.battery <= LOW_BATTERY + 0.2:
                status = "⚠ Getting low"
            
            cf.print(f"{i+1:7d}  | {state.battery:10.2f}  | {status}", cf.LogLevel.info)
        
        cf.print("Monitoring complete", cf.LogLevel.info)
        
        cf.disconnect()
        cf.print("\nTest completed", cf.LogLevel.message)
        
    except Exception as e:
        cf.print(f"\nTEST FAILED: {e}", cf.LogLevel.error)
        try:
            cf.disconnect()
        except:
            pass
        raise


def test_charge_state(address=None):
    """Test battery charge state monitoring."""
    cf = CrazyFlie(address if address else "")
    cf.logging(enable=True, file=False, level=LogLevel.info)
    
    cf.print("=" * 60, cf.LogLevel.message)
    cf.print("TEST: Charge State Monitoring", cf.LogLevel.message)
    cf.print("=" * 60, cf.LogLevel.message)
    cf.print("\n⚠️  Connect drone to charger before starting", cf.LogLevel.warning)
    
    input("\nPress ENTER when charger is connected, or Ctrl+C to abort...")
    
    try:
        cf.print("\n[Setup] Connecting...", cf.LogLevel.info)
        if address:
            cf.scan(specific=address)
        else:
            cf.scan()
        
        cf.print("\n[Test] Monitoring charge state...", cf.LogLevel.info)
        cf.print("This will run until battery is charged or you press Ctrl+C", cf.LogLevel.info)
        cf.charge_state(parallel=False)
        
        cf.print("Charging complete or monitoring stopped", cf.LogLevel.info)
        
        cf.disconnect()
        cf.print("\n✓ Test completed", cf.LogLevel.message)
        
    except KeyboardInterrupt:
        cf.print("\nMonitoring stopped by user", cf.LogLevel.warning)
        try:
            cf.disconnect()
        except:
            pass
    except Exception as e:
        cf.print(f"\nTEST FAILED: {e}", cf.LogLevel.error)
        try:
            cf.disconnect()
        except:
            pass
        raise


def test_position_averaging(address=None, sample_count=10, sample_time=5.0):
    """Test position averaging function."""
    cf = CrazyFlie(address if address else "")
    cf.logging(enable=True, file=False, level=LogLevel.info)
    
    cf.print("=" * 60, cf.LogLevel.message)
    cf.print("TEST: Position Averaging", cf.LogLevel.message)
    cf.print("=" * 60, cf.LogLevel.message)
    
    monitor = NatNetRigidBodyMonitor()
    cf.set_natnet_monitor(monitor)
    
    try:
        cf.print("\n[Setup] Connecting...", cf.LogLevel.info)
        if address:
            cf.scan(specific=address)
        else:
            cf.scan()
        
        cf.test_mode(True)
        cf.connect(start_flying=False)
        sleep(2)
        
        cf.print(f"\n[Test 1] Getting averaged position ({sample_count} samples over {sample_time}s)...", cf.LogLevel.info)
        avg_pos = cf.get_position(sample_count, sample_time)
        cf.print(f"Averaged position:", cf.LogLevel.info)
        cf.print(f"  - X: {avg_pos.x:.4f} m", cf.LogLevel.info)
        cf.print(f"  - Y: {avg_pos.y:.4f} m", cf.LogLevel.info)
        cf.print(f"  - Z: {avg_pos.z:.4f} m", cf.LogLevel.info)
        cf.print(f"  - Yaw: {avg_pos.yaw:.2f}°", cf.LogLevel.info)
        cf.print(f"  - Battery: {avg_pos.battery:.2f} V", cf.LogLevel.info)
        
        cf.print(f"\n[Test 2] Getting synchronized averaged position...", cf.LogLevel.info)
        sync_pos = cf._get_position_sync(sample_count, sample_time)
        cf.print(f"Synchronized position:", cf.LogLevel.info)
        cf.print(f"  - X: {sync_pos.x:.4f} m", cf.LogLevel.info)
        cf.print(f"  - Y: {sync_pos.y:.4f} m", cf.LogLevel.info)
        cf.print(f"  - Z: {sync_pos.z:.4f} m", cf.LogLevel.info)
        cf.print(f"  - Yaw: {sync_pos.yaw:.2f}°", cf.LogLevel.info)
        
        # Compare variance
        cf.print(f"\n[Analysis] Difference between methods:", cf.LogLevel.info)
        cf.print(f"  - ΔX: {abs(avg_pos.x - sync_pos.x):.4f} m", cf.LogLevel.info)
        cf.print(f"  - ΔY: {abs(avg_pos.y - sync_pos.y):.4f} m", cf.LogLevel.info)
        cf.print(f"  - ΔZ: {abs(avg_pos.z - sync_pos.z):.4f} m", cf.LogLevel.info)
        
        cf.disconnect()
        cf.print("\nTest completed", cf.LogLevel.message)
        
    except Exception as e:
        cf.print(f"\nTEST FAILED: {e}", cf.LogLevel.error)
        try:
            cf.disconnect()
        except:
            pass
        raise


def test_position_saving(address=None):
    """Test position saving to file."""
    cf = CrazyFlie(address if address else "")
    cf.logging(enable=True, file=False, level=LogLevel.info)
    
    cf.print("=" * 60, cf.LogLevel.message)
    cf.print("TEST: Position Saving", cf.LogLevel.message)
    cf.print("=" * 60, cf.LogLevel.message)
    
    monitor = NatNetRigidBodyMonitor()
    cf.set_natnet_monitor(monitor)
    
    try:
        cf.print("\n[Setup] Connecting...", cf.LogLevel.info)
        if address:
            cf.scan(specific=address)
        else:
            cf.scan()
        
        # Set custom output directory
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        output_dir = Path(__file__).parent / "test_output" / timestamp
        output_dir.mkdir(parents=True, exist_ok=True)
        cf.set_directory(str(output_dir))
        cf.print(f"Output directory: {output_dir}", cf.LogLevel.info)
        
        cf.test_mode(True)
        cf.connect(start_flying=False)
        sleep(2)
        
        cf.print("\n[Test] Saving 3 position samples...", cf.LogLevel.info)
        for i in range(3):
            cf.print(f"\n  Sample {i+1}/3:", cf.LogLevel.info)
            pos = cf.get_position(5, 2.0)
            cf.print(f"    Position: ({pos.x:.3f}, {pos.y:.3f}, {pos.z:.3f})", cf.LogLevel.info)
            cf.save_position(pos)
            count = cf.get_position_count()
            cf.print(f"    ✓ Saved (total saved: {count})", cf.LogLevel.info)
            sleep(1)
        
        cf.print(f"\n✓ Saved {cf.get_position_count()} positions to {output_dir}", cf.LogLevel.info)
        
        # List saved files
        saved_files = list(output_dir.glob("*.txt"))
        cf.print(f"\nSaved files:", cf.LogLevel.info)
        for f in saved_files:
            cf.print(f"  - {f.name} ({f.stat().st_size} bytes)", cf.LogLevel.info)
        
        cf.disconnect()
        cf.print("\n✓ Test completed", cf.LogLevel.message)
        
    except Exception as e:
        cf.print(f"\n✗ TEST FAILED: {e}", cf.LogLevel.error)
        try:
            cf.disconnect()
        except:
            pass
        raise


def test_configuration_options(address=None):
    """Test various configuration options."""
    cf = CrazyFlie(address if address else "")
    cf.logging(enable=True, file=False, level=LogLevel.debug)
    
    cf.print("=" * 60, cf.LogLevel.message)
    cf.print("TEST: Configuration Options", cf.LogLevel.message)
    cf.print("=" * 60, cf.LogLevel.message)
    
    try:
        cf.print("\n[Test 1] Testing delay configuration...", cf.LogLevel.info)
        cf.set_delay(0.05)
        cf.print("✓ Set delay to 0.05s", cf.LogLevel.info)
        
        cf.print("\n[Test 2] Testing update time configuration...", cf.LogLevel.info)
        cf.set_update_time(50)  # 50ms
        cf.print("✓ Set update time to 50ms", cf.LogLevel.info)
        
        cf.print("\n[Test 3] Testing blocking mode...", cf.LogLevel.info)
        cf.set_unblocking(False)
        cf.print("✓ Set blocking mode enabled", cf.LogLevel.info)
        
        cf.print("\n[Test 4] Testing connection...", cf.LogLevel.info)
        if address:
            cf.scan(specific=address)
        else:
            cf.scan()
        
        cf.test_mode(True)
        cf.connect(start_flying=False)
        sleep(2)
        
        cf.print("\n[Test 5] Testing state updates...", cf.LogLevel.info)
        for i in range(5):
            sleep(0.1)
            state = cf.get_state()
            cf.print(f"  Update {i+1}: z={state.z:.3f}m", cf.LogLevel.debug)
        cf.print("✓ Fast state updates working", cf.LogLevel.info)
        
        cf.disconnect()
        cf.print("\n✓ All configuration tests passed", cf.LogLevel.message)
        
    except Exception as e:
        cf.print(f"\n✗ TEST FAILED: {e}", cf.LogLevel.error)
        try:
            cf.disconnect()
        except:
            pass
        raise


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test CrazyFlie utility functions")
    parser.add_argument("--address", type=str, help="Drone URI")
    parser.add_argument("--test", type=str, 
                       choices=["propeller", "battery", "charge", "position-avg", 
                               "position-save", "config", "all"],
                       default="all", help="Which test to run")
    
    args = parser.parse_args()
    
    tests = {
        "propeller": test_propeller_test,
        "battery": test_battery_monitoring,
        "charge": test_charge_state,
        "position-avg": test_position_averaging,
        "position-save": test_position_saving,
        "config": test_configuration_options,
    }
    
    if args.test == "all":
        for name, test_func in tests.items():
            if name != "charge":  # Skip charge test in "all" mode
                test_func(args.address)
                # Print separator between tests - using standard print since no cf object here
                print("\n" + "="*60 + "\n")
    else:
        tests[args.test](args.address)
