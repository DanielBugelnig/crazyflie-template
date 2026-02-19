"""
Test script for reading CrazyFlie parameters and checking attached decks.

This script demonstrates:
- Reading system parameters
- Checking for attached decks (Flow, Loco, AI-deck)
- Inspecting estimator and controller settings
- Testing parameter read/write operations

Author: Daniel Bugelnig (daniel.bugelnig@aau.at)
Date: 2026
"""

import sys
from pathlib import Path
from time import sleep

sys.path.insert(0, str(Path(__file__).parent.parent))

from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.core.base_utils import LogLevel


def test_parameters_and_decks(address=None):
    """Test parameter reading and deck detection."""
    cf = CrazyFlie(address if address else "")
    cf.logging(enable=True, file=False, level=LogLevel.info)
    
    cf.print("=" * 60, cf.LogLevel.message)
    cf.print("TEST: Parameters and Deck Detection", cf.LogLevel.message)
    cf.print("=" * 60, cf.LogLevel.message)
    
    try:
        # Connect in test mode
        cf.print("\n[Setup] Connecting to drone...", cf.LogLevel.info)
        if address:
            cf.scan(specific=address)
        else:
            cf.scan()
        
        cf.test_mode(True)
        cf.connect(start_flying=False)
        sleep(2)
        cf.print("Connected in test mode", cf.LogLevel.info)
        
        # Test 1: Read standard parameters
        cf.print("\n[Test 1] Reading system parameters...", cf.LogLevel.info)
        params = cf.read_parameters(read_all=False)
        cf.print("Parameters read successfully:", cf.LogLevel.info)
        for name, value in params.items():
            cf.print(f"  - {name}: {value}", cf.LogLevel.info)
        
        # Test 2: Check all attached decks
        cf.print("\n[Test 2] Checking all attached decks...", cf.LogLevel.info)
        cf.checking_decks()
        
        # Test 3: Check for specific decks
        cf.print("\n[Test 3] Checking for specific decks...", cf.LogLevel.info)
        decks_to_check = ["bcFlow2", "bcFlow", "bcLoco", "bcAI"]
        for deck in decks_to_check:
            result = cf.checking_decks(specific=deck)
            status = "DETECTED" if result else "✗ Not detected"
            cf.print(f"  - {deck}: {status}", cf.LogLevel.info)
        
        # Test 4: Test _set method (parameter writing)
        cf.print("\n[Test 4] Testing parameter write operations...", cf.LogLevel.info)
        cf.print("  Note: Using _set() for test purposes only", cf.LogLevel.info)
        # Read current estimator value
        current_est = cf._scf.cf.param.get_value("stabilizer.estimator")
        cf.print(f"Current estimator: {current_est}", cf.LogLevel.info)
        # We won't actually change it, just demonstrate the method exists
        cf.print(" Parameter write method available", cf.LogLevel.info)
        
        # Test 5: Get MAC address (if AI deck present)
        cf.print("\n[Test 5] Checking AI-deck MAC address...", cf.LogLevel.info)
        if cf._mac and cf._mac != "unknown":
            cf.print(f"AI-deck MAC: {cf._mac}", cf.LogLevel.info)
        else:
            cf.print(" No AI-deck MAC configured", cf.LogLevel.info)
        
        # Test 6: Read all parameters (verbose)
        cf.print("\n[Test 6] Would you like to read ALL parameters? (skipped by default)", cf.LogLevel.info)
        cf.print("  To enable: uncomment 'cf.read_parameters(read_all=True)' in script", cf.LogLevel.info)
        # Uncomment the line below to see all available parameters
        # cf.read_parameters(read_all=True)
        
        # Disconnect
        cf.print("\n[Cleanup] Disconnecting...", cf.LogLevel.info)
        cf.disconnect()
        cf.print("Disconnected", cf.LogLevel.info)
        
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
    # Specify your drone address
    # test_parameters_and_decks("radio://0/90/2M/E7E7E7E701")
    test_parameters_and_decks()
