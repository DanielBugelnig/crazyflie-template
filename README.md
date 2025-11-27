# Crazyflie template repository for developing with cflib

Lightweight template and utilities to work with Bitcraze Crazyflie drones,
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
Enter your fixed values (i.e. antenna adresses, flight space boundaries, rigid_body_ids, time constants, mac addresses of AI-deck...) in [crazyflie/constants.py](crazyflie/constants.py).


2. Run an example (check battery charge)
    ```sh
    python examples/charging.py
    ```
3. Explore other examples in the `examples/` folder:
   - examples/test_crazyflie.py — single-drone demo
   - examples/test_swarm.py — swarm demo using trajectories
   - examples/test_trajectory.py — trajectory generator demo

## Repository layout

- crazyflie/
  - bitcraze/
    - crazyflie.py — High-level CrazyFlie controller
    - ai_deck.py — AI-Deck camera interface (not tested yet)
    - swarm.py — Swarm orchestration helpers
    - trajectory.py — Trajectory generation utilities
    - optitrack_integration/  - scripts for integrating Optitrack position data
- crazyflie/core/
  - base_utils.py — logging & helper utilities
- examples/ — runnable demonstration scripts

## Key modules

- crazyflie.core.base_utils.BaseClass — logging, file helpers, helpers
- crazyflie.bitcraze.crazyflie.CrazyFlie — connect, command, safety, logging
- crazyflie.bitcraze.trajectory.Trajectory — circle/formation/path helpers
- crazyflie.bitcraze.optitrack_integration.optitrack.NatNetRigidBodyMonitor — thread-safe NatNet interface

