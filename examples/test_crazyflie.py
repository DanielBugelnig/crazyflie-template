from pathlib import Path
import sys, time

sys.path.append(str(Path(__file__).resolve().parents[1]))

from crazyflie import bitcraze
import crazyflie.core.base_utils as base
from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.bitcraze.ai_deck import AI_Deck
import crazyflie.bitcraze.swarm as swarm_module
from crazyflie.core.base_utils import LogLevel


if __name__ == "__main__":
    drone = bitcraze.crazyflie()
    calculator = bitcraze.trajectory()
    
    drone.logging(enable=True, file=True, level=LogLevel.message)
    calculator.logging(enable=True, file=True, level=LogLevel.message)
    # positions = [calculator.get_position(x=0.69, y=3.64, z=1.2, yaw=0.0),
    #              calculator.get_position(x=0.76, y=3.39, z=1.2, yaw=30.0),  # don't turn more than 45 degrees for once
    #              calculator.get_position(x=0.94, y=3.21, z=1.2, yaw=60.0),
    #              calculator.get_position(x=1.19, y=3.14, z=1.2, yaw=90.0),
    #              calculator.get_position(x=1.44, y=3.21, z=1.2, yaw=120.0),
    #              calculator.get_position(x=1.62, y=3.39, z=1.2, yaw=150.0),
    #              calculator.get_position(x=1.69, y=3.64, z=1.2, yaw=180.0),
    #              calculator.get_position(x=1.62, y=3.89, z=1.2, yaw=-150.0),
    #              calculator.get_position(x=1.44, y=4.07, z=1.2, yaw=-120.0),
    #              calculator.get_position(x=1.19, y=4.14, z=1.2, yaw=-90.0),
    #              calculator.get_position(x=0.94, y=4.07, z=1.2, yaw=-60.0),
    #              calculator.get_position(x=0.76, y=3.89, z=1.2, yaw=-30.0)]
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
