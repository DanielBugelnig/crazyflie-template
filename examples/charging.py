from pathlib import Path
import sys, time

sys.path.append(str(Path(__file__).resolve().parents[1]))

from crazyflie import bitcraze
import crazyflie.core.base_utils as base
from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.bitcraze.ai_deck import AI_Deck
import crazyflie.bitcraze.swarm as swarm_module

drone = CrazyFlie()   # create object
drone.logging(enable=True, file=False, level=base.LogLevel.message)  # set up logging
try:
    drone.scan()    # scan for drones
    drone.test_mode(True)   # set test mode
    drone.connect() # open link
    drone.charge_state()
    print(f"Address: {drone._address}")
except (bitcraze.CrazyFlieError, KeyboardInterrupt):
    pass
drone.disconnect()