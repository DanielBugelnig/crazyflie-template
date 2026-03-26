from pathlib import Path
import sys, time

sys.path.append(str(Path(__file__).resolve().parents[1]))

from crazyflie import bitcraze
import crazyflie.core.base_utils as base
from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.bitcraze.ai_deck import AI_Deck
import crazyflie.bitcraze.swarm as swarm_module
from crazyflie.core.base_utils import LogLevel
from crazyflie.bitcraze.trajectory import Trajectory


if __name__ == "__main__":
    drone = CrazyFlie()
    drone.logging(enable=True, file=True, level=LogLevel.debug)
    calculator = Trajectory()
    
    drone.logging(enable=True, file=True, level=LogLevel.message)
    calculator.logging(enable=True, file=True, level=LogLevel.message)
    calculator.set_count(1)
    positions_all = calculator.circle(radius=0.5, positions=12, altitude=1.0)
    positions=[]
    for position in positions_all:
        positions.append(position[0])
        print(f"Position  = {position[0]}")
 
    try:
        drone.scan()    # scan for drones
        drone.connect() # open link
        for position in positions:
            drone.fly(position)
            while not drone.arrived(position):
                time.sleep(0.1)
            time.sleep(0.2)
        drone.land()
    except (bitcraze.CrazyFlieError, KeyboardInterrupt):
        pass
    drone.disconnect()
