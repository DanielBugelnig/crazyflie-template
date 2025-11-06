from pathlib import Path
import sys, time,os 


import sys
import os

# add project root to Python path (one line, automatic)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from crazyflie import bitcraze
import crazyflie.core.base_utils as base
from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.bitcraze.ai_deck import AI_Deck
import crazyflie.bitcraze.swarm as swarm_module
from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor
from crazyflie.bitcraze.trajectory import Trajectory

calculator = Trajectory()
calculator.logging(enable=True, file=True, level=calculator.LogLevel.message)
calculator.set_count(1)
positions_all = calculator.circle(radius=1, positions=15, altitude=1.5)
positions=[]
for position in positions_all:
    positions.append(position[0])
    print(f"Position  = {position[0]}")





natnet_monitor = NatNetRigidBodyMonitor()
natnet_monitor.start()
time.sleep(1.0)  # wait for monitor to start
while not natnet_monitor.is_running():
    time.sleep(0.1)

print("NatNet monitor is running.")
cf = CrazyFlie()
cf.logging(enable=True, file=True, level=base.LogLevel.debug)
cf.set_natnet_monitor(natnet_monitor)

try:
    cf.scan()    # scan for drones
    cf.connect(start_flying=True, localization_mode="Optitrack") # open link
    
    for position in positions:
        cf.fly(position)
        while not cf.arrived(position):
            time.sleep(0.1)
        time.sleep(0.2)
    cf.land()
except (bitcraze.CrazyFlieError, KeyboardInterrupt):
    pass
cf.disconnect()