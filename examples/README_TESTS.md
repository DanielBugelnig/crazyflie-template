# CrazyFlie Test Suite

This directory contains comprehensive test scripts for the CrazyFlie class.

## Test Scripts Overview

### 1. `test_basic_connection.py`
Tests basic connection, disconnection, and state reading.

**Features tested:**
- Scanning for drones
- Connecting to a drone
- Reading connection state
- Getting current state (position, battery)
- State monitoring
- Disconnecting safely

**Usage:**
```bash
python examples/test_basic_connection.py
# Or specify a drone:
python examples/test_basic_connection.py --address "radio://0/90/2M/E7E7E7E701"
```

**Requirements:** USB radio dongle, drone powered on

---

### 2. `test_parameters_decks.py`
Tests parameter reading and deck detection.

**Features tested:**
- Reading system parameters (estimator, controller, etc.)
- Detecting all attached decks
- Checking specific decks (Flow, Loco, AI-deck)
- Parameter write operations (demo only)
- AI-deck MAC address lookup

**Usage:**
```bash
python examples/test_parameters_decks.py
```

**Requirements:** USB radio dongle, drone powered on

---

### 3. `test_localization_modes.py`
Tests different localization modes and selection logic.

**Features tested:**
- Automatic mode selection based on detected decks
- Manual mode selection (Optitrack, Flow, Loco)
- EKF seeding with external position
- External position streaming
- Fallback behavior

**Usage:**
```bash
# Test all modes
python examples/test_localization_modes.py --mode all

# Test specific mode
python examples/test_localization_modes.py --mode optitrack --optitrack-server 192.168.1.100

# Test with specific drone
python examples/test_localization_modes.py --address "radio://0/90/2M/E7E7E7E701" --mode flow
```

**Arguments:**
- `--mode`: auto, optitrack, flow, loco, or all
- `--address`: Drone URI
- `--optitrack-server`: Optitrack server IP (default: 127.0.0.1)

**Requirements:** 
- USB radio dongle
- Optitrack system (for optitrack mode)
- Flow/Loco deck (for respective modes)

---

### 4. `test_flight_basics.py` ⚠️
Tests actual flight operations. **DRONE WILL FLY!**

**Features tested:**
- Taking off to hover position
- Hovering at specified height
- Flying to waypoints
- Checking arrival at positions
- Landing safely
- Emergency motor stop

**Usage:**
```bash
# Simple hover test
python examples/test_flight_basics.py --test hover --hover-height 0.5 --hover-duration 10

# Waypoint flight
python examples/test_flight_basics.py --test waypoints --optitrack-server 192.168.1.100

# Emergency stop test (hold drone in hand!)
python examples/test_flight_basics.py --test emergency
```

**Arguments:**
- `--test`: hover, waypoints, or emergency
- `--address`: Drone URI
- `--optitrack-server`: Optitrack server IP
- `--hover-height`: Height in meters (default: 0.5)
- `--hover-duration`: Duration in seconds (default: 10)

**Safety Requirements:**
- ⚠️ Clear flight area
- ⚠️ Emergency stop ready (press 'q' key)
- ⚠️ Optitrack or similar localization active
- ⚠️ Drone on flat surface
- ⚠️ Adequate battery charge

---

### 5. `test_utility_functions.py`
Tests utility and helper functions.

**Features tested:**
- Propeller self-test
- Battery voltage monitoring
- Charge state monitoring
- Position averaging (normal and synchronized)
- Position saving to file
- Configuration options (delay, update time, etc.)

**Usage:**
```bash
# Run all utility tests
python examples/test_utility_functions.py --test all

# Specific tests
python examples/test_utility_functions.py --test propeller
python examples/test_utility_functions.py --test battery
python examples/test_utility_functions.py --test charge  # Requires charger connected
python examples/test_utility_functions.py --test position-avg
python examples/test_utility_functions.py --test position-save
python examples/test_utility_functions.py --test config
```

**Arguments:**
- `--test`: propeller, battery, charge, position-avg, position-save, config, or all
- `--address`: Drone URI

**Special Requirements:**
- `charge` test: Drone must be connected to charger
- `propeller` test: Place drone on flat surface, clear of obstacles

---

## Keyboard Controls (During Flight Tests)

When flight tests are running, these keyboard shortcuts are available:

- **`Ctrl + Alt + Q`**: Emergency stop (motors off immediately)
- **`Ctrl + Alt + L`**: Initiate landing sequence
- **`Esc`**: Stop keyboard listener

---

## Quick Start Guide

### First Time Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure constants:**
   Edit `crazyflie/constants.py`:
   - Add your drone URIs to `CRAZYFLIES`
   - Add AI-deck MAC addresses to `MAC_LOOKUP`
   - Add Optitrack rigid body IDs to `RIGID_BODY_ID_LOOKUP`

3. **Test basic connection:**
   ```bash
   python examples/test_basic_connection.py
   ```

### Running Tests

**Safe tests (no flight):**
```bash
python examples/test_basic_connection.py
python examples/test_parameters_decks.py
python examples/test_localization_modes.py --mode auto
python examples/test_utility_functions.py --test config
```

**Flight tests (⚠️ REQUIRES SUPERVISION):**
```bash
# Start with a simple hover
python examples/test_flight_basics.py --test hover --hover-height 0.3 --hover-duration 5

# Then try waypoints
python examples/test_flight_basics.py --test waypoints
```

---

## Troubleshooting

### Connection Issues
- Ensure drone is powered on and batteries charged
- Check USB radio dongle is connected
- Verify drone URI in `constants.py` matches your drone
- Try rescanning: `cf.scan()` will find available drones

### Localization Issues
- **Optitrack:** Verify server IP is correct and Motive is streaming
- **Flow:** Ensure deck is properly installed and surface has texture
- **Loco:** Check positioning system is calibrated and operational

### Flight Issues
- Check battery level (> 3.7V recommended)
- Verify localization system provides position updates
- Ensure flight area is clear and well-lit (for Flow deck)
- Start with low hover heights (0.3-0.5m) for testing

### Parameter Errors
- Some parameters may not be available on all firmware versions
- Update drone firmware to latest version if needed
- Use `cf.read_parameters(read_all=True)` to see all available parameters

---

## Test Output

Test scripts create output in:
- **Console:** Real-time test progress and results
- **Log files:** `examples/logs/` (if file logging enabled)
- **Position files:** `examples/test_output/` (position saving tests)
- **Datasets:** `examples/datasets/` (flight recording, if enabled)

---

## Development Notes

### Adding New Tests

To add a new test:

1. Create a new test file: `test_your_feature.py`
2. Follow the existing test structure:
   ```python
   def test_your_feature(address=None):
       print("=" * 60)
       print("TEST: Your Feature Name")
       print("=" * 60)
       
       cf = CrazyFlie(address if address else "")
       cf.logging(enable=True, file=False, level=LogLevel.info)
       
       try:
           # Your test code
           pass
       except Exception as e:
           # Cleanup
           pass
   ```
3. Add argparse support for command-line arguments
4. Document in this README

### Test Best Practices

- Always include try/except with cleanup
- Use descriptive print statements for test progress
- Test one feature at a time
- Include safety warnings for flight tests
- Provide clear success/failure indicators (✓/✗)

---

## Safety Reminders

⚠️ **Always follow these safety guidelines:**

1. Keep a clear flight area (minimum 2m x 2m x 2m)
2. Keep emergency stop button/key ready (press 'q')
3. Ensure adequate battery charge (> 3.7V)
4. Test new configurations at low altitude first
5. Never fly near people or obstacles
6. Always supervise autonomous flights
7. Have a landing area prepared
8. Know how to trigger emergency stop

---

## Support

For issues or questions:
- Check the main class documentation in `crazyflie/bitcraze/crazyflie.py`
- Review the examples in this directory
- Check Bitcraze documentation: https://www.bitcraze.io/documentation/

---

**Last Updated:** 2026-02-05
