from pathlib import Path
import sys, time,os 


import sys
import os

# add project root to Python path (one line, automatic)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import crazyflie.core.base_utils as base
from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.bitcraze.ai_deck import AI_Deck
import crazyflie.bitcraze.swarm as swarm_module
from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor

natnet_monitor = NatNetRigidBodyMonitor()
natnet_monitor.start()
time.sleep(1.0)  # wait for monitor to start
while not natnet_monitor.is_running():
    time.sleep(0.1)

print("NatNet monitor is running.")
id = 12
while True:
     pos = natnet_monitor.get_position(id)  # Rigid Body ID 38
     print(f"Position from NatNet RB {id}: {pos}")

