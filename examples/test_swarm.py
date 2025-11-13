from pathlib import Path
import sys, time

sys.path.append(str(Path(__file__).resolve().parents[1]))

from crazyflie import bitcraze
import crazyflie.core.base_utils as base
from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.bitcraze.ai_deck import AI_Deck
from crazyflie.bitcraze.swarm import CrazySwarm
from crazyflie.core.base_utils import LogLevel
from crazyflie.core.shared_data import State
from crazyflie.constants import DRONE_DELAY, DECK_DELAY
from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor


RADIUS=0.5
POSITIONS = 50
ALTITUDE = 1.2 
DIRECTION= "clockwise"


swarm = CrazySwarm()
calculator = bitcraze.trajectory()
swarm.logging(enable=True, file=True, level=LogLevel.debug)
swarm._logging_level = LogLevel.debug
project_dir = swarm.get_directory()



natnet_monitor = NatNetRigidBodyMonitor()
natnet_monitor.start()
time.sleep(1.0)  # wait for monitor to start
while not natnet_monitor.is_running():
    time.sleep(0.1)
try:
    # find swarm members
    swarm.scan()
    swarm.set_natnet_monitor(natnet_monitor)
    swarm.set_delay(DRONE_DELAY, DECK_DELAY)
    calculator.set_count(swarm.get_count())
    # generate destinations
    zylinder_coordinates = calculator.zylinder(radius=RADIUS, object_height=1.0, object_position=State(0,0,1), positions=POSITIONS)
    verified_coordinates:list[list[State]] = []
    for coordinate in zylinder_coordinates:
        verified_coordinates.append(calculator.verify_position(coordinate))
    # change direction if required
    if DIRECTION == "clockwise":
        verified_coordinates = verified_coordinates[::-1]
        
    transformed__verified_coordinates = calculator.transform_positions(verified_coordinates)
    calculator.print_trajectory(verified_coordinates, "Generated trajectory:")
    
    # start drones
    swarm.start()
    # turn slowly with the second drone
    # if swarm.get_count() == 2:
    #     drone_index = 1
    #     swarm.arm(drone_index)
    #     start = swarm.get_state_single(drone_index)
    #     for yaw in range(0, -900, -225):
    #         position = calculator.get_position(x=start.get_x(), y=start.get_y(), z=ALTITUDE, yaw=(yaw / 10))
    #         swarm.fly_single(drone_index, position, photo=False)
    #         while not swarm.arrived_single(drone_index, photo=False):
    #             time.sleep(DRONE_DELAY)
    swarm.arm()
    swarm.turn_to_center()
    
    while True:
        for position in transformed__verified_coordinates:
            # dynamic trajectory
            swarm.fly(position)
            while not swarm.arrived():
                time.sleep(DRONE_DELAY)
except (*bitcraze.BitcrazeError, KeyboardInterrupt):
    pass
# land with all drones and stop them
swarm.land()
swarm.stop()

