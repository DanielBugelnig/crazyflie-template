# Crazyflie template repository for developing with cflib

Template and utilities to work with Bitcraze Crazyflie drones,
AI-Deck cameras, and OptiTrack/NatNet motion capture integration.

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/DanielBugelnig/crazyflie-template.git
```
#### Checkout your branch
```bash
git checkout <branch-name>
```

### 2. Venv (Python 3.10)
Make sure Python 3.10 is installed:
ate and activate the venv:
```bash
python3.10 -m venv venv

source venv/bin/activate
```
### 3. Install dependencies
Upgrade pip and install requirements:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## Usage

### Starting a New Project

The `project/` folder is your workspace for developing new applications:

1. Navigate to the project folder:
    ```sh
    cd project
    ```

2. Use the configuration GUI to set up your project constants:
    ```sh
    python config_gui.py
    ```
   This GUI allows you to configure:
   - Crazyflie URIs and hardware settings
   - OptiTrack positioning system parameters
   - Control parameters and flight boundaries
   - AI-Deck MAC addresses

3. Start developing your application in the `project/` folder. You can reference the examples for guidance.

### Running Examples

Explore example scripts in the `examples/` folder to learn the API:
- `examples/charging.py` — check battery charge
- `examples/test_crazyflie.py` — single-drone demo
- `examples/test_swarm.py` — swarm demo using trajectories
- `examples/test_trajectory.py` — trajectory generator demo

## Repository layout

- **project/** — your workspace for new applications and custom scripts
  - config_gui.py — interactive configuration manager
  - test.py — your main development file
  - test_config.json — saved configuration settings
- **crazyflie/** — core library modules
  - bitcraze/
    - crazyflie.py — High-level CrazyFlie controller
    - ai_deck.py — AI-Deck camera interface (not tested yet)
    - swarm.py — Swarm orchestration helpers
    - trajectory.py — Trajectory generation utilities
    - optitrack_integration/ — scripts for integrating OptiTrack position data
  - core/
    - base_utils.py — logging & helper utilities
  - constants.py — project configuration constants
- **examples/** — runnable demonstration scripts

## Key modules

- crazyflie.core.base_utils.BaseClass — logging, file helpers, helpers
- crazyflie.bitcraze.crazyflie.CrazyFlie — connect, command, safety, logging
- crazyflie.bitcraze.trajectory.Trajectory — circle/formation/path helpers
- crazyflie.bitcraze.optitrack_integration.optitrack.NatNetRigidBodyMonitor — thread-safe NatNet interface

# Bug reporting
If you find a bug or a feature is missing, please open an Issue on GitHub.

