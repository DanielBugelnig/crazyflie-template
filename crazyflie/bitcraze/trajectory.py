"""
    calculate trajectories for drones in a swarm
    Veres-Vitalyos Almos (veresvalmos@gmail.com)
    Daniel Bugelnig (daniel.bugelnig@aau.at)
    2025
"""

from math import sin, cos, pi, ceil, floor

from ..core.base_utils import BaseClass
from ..core.shared_data import State
from ..constants import FLYING_AREA
from ..core.base_utils import LogLevel

OBJECT_POSITION = State(x=0, y=0, z=1)  # object position in meters
OBJECT_HEIGHT = 1  # object height in meters

import matplotlib.pyplot as plt

class TrajectoryError(Exception):
    def __init__(self, message=""):
        # Trajectory Error
        super().__init__(message)
        return

class Trajectory(BaseClass):
    # calculate trajectories for each drone in a swarm

    def __init__(self):
        # calculate everythin related to setpoints
        super().__init__()
        self._count = 0
        self._initial_altitude = 0
        self._bounds:dict[str, State] = {}
        self._object_placement:State = None
        # set anchor coordinates (hardcoded)
        self._get_anchor_positions()
        self._get_object_position()
        return
    
    def logging(self, enable, file, level):
        # set up logging
        super().logging(enable=enable, file=file, level=level, name="Trajectory")
        return
    
    """ ---------------------------------------------------------------------------- """

    def set_count(self, value):
        """Sets the number of drones in the swarm.

        Args:
            value (int): Number of drones.
        """
        self._count = value
        return

    """ ---------------------------------------------------------------------------- """

    def get_count(self):
        """Returns the number of drones in the swarm.

        Returns:
            int: The number of drones.
        """
        return self._count
    
    
    def _get_object_position(self):
        """Initializes the object position and height."""
        self._object_placement = OBJECT_POSITION
        self._object_height = OBJECT_HEIGHT
        self.print("object " + str(self._object_placement), self.LogLevel.info)
        return
    
    def _get_anchor_positions(self):
        """Retrieves the anchor positions and defines the flight bounding box.

        Assumes that:
            - Anchor 0 is the back-left corner (viewed facing -X direction).
            - Anchors 0–3 are bottom anchors, 4–7 are top anchors.
        """
        self._anchors = FLYING_AREA
        self._bounds["up"] = min(self._anchors[4].z, self._anchors[5].z, self._anchors[6].z, self._anchors[7].z)
        self._bounds["down"] = 0
        self._bounds["bl"] = self._anchors[0]
        self._bounds["br"] = self._anchors[3]
        self._bounds["fl"] = self._anchors[1]
        self._bounds["fr"] = self._anchors[2]
        self.print("Anchor positions set", level=LogLevel.info)
        return
    def validate_position(self, input:State) -> State:
        """Validates a given position against the predefined bounding box.

        Args:
            input (State): Position to be validated.

        Returns:
            State: Validated position within the bounding box.
        """
        try:
            x_min = max(self._bounds["bl"].x, self._bounds["br"].x)  
            x_max = min(self._bounds["fl"].x, self._bounds["fr"].x)
            y_min = max(self._bounds["bl"].y, self._bounds["fl"].y)
            y_max = min(self._bounds["br"].y, self._bounds["fr"].y)
            z_min = min(self._bounds["up"], self._bounds["down"])
            z_max = max(self._bounds["up"], self._bounds["down"])
        except (AttributeError, KeyError) as e:
            self.print("anchor positions not set" + str(e), self.LogLevel.error)
            raise TrajectoryError("anchor positions not set")
        # adding security margin
        x_min += 0.1
        x_max -= 0.1
        y_min += 0.1
        y_max -= 0.1
        z_min += 0.1
        z_max -= 0.1
        if input.get_x() > x_max or input.get_x() < x_min or input.get_y() > y_max or input.get_y() < y_min or input.get_z() > z_max or input.get_z() < z_min:
            self.print(f"position {input} out of bounds", self.LogLevel.warning)
            return False
        return True
       
            
    def _keep_in_box(self, input:State) -> State:
        """Keeps a given position within the predefined bounding box.

        Args:
            input (State): Position to be verified.

        Returns:
            State: Corrected position within the bounding box.

        Raises:
            TypeError: If input is not a State object.
            TrajectoryError: If anchor positions are not properly set.
        """
        # keep coordinates in the bounding box, anchors should be place in a rectangle, if not space will get lost (smallest rectangle is chosen as flying space)
        output = input.copy()
        if not isinstance(input, State):
            raise TypeError(f"_keep_in_box expects a State object, got {type(input)}")

        try:
            x_min = max(self._bounds["bl"].x, self._bounds["br"].x)  
            x_max = min(self._bounds["fl"].x, self._bounds["fr"].x)
            y_min = max(self._bounds["bl"].y, self._bounds["fl"].y)
            y_max = min(self._bounds["br"].y, self._bounds["fr"].y)
            # adding security margin
            x_min += 0.1
            x_max -= 0.1
            y_min += 0.1
            y_max -= 0.1

            # keep positions in the bounding box
            output.z = min(self._bounds["up"], max(output.z, self._bounds["down"]))
            output.x = min(x_max, max(output.x, x_min))
            output.y = min(y_max, max(output.y, y_min))
        except (AttributeError, KeyError) as e:
            self.print("anchor positions not set" + str(e), self.LogLevel.error)
            raise TrajectoryError("anchor positions not set")
        if output.yaw > 180:
            output.yaw = (-1) * (180 - (output.yaw - 180))
            self.print(f" position {input}, yaw > 180 correcting to {output.yaw}", self.LogLevel.debug)
            
       
        if output.get_x() != input.get_x() or output.get_y() != input.get_y() or output.get_z() != input.get_z():
            self.print(f"position {input} out of bounds, corrected to {output}", self.LogLevel.warning)
        return output
    
    """ ---------------------------------------------------------------------------- """

    def verify_position(self, input:list[State]) -> list[State]:
        """Checks and corrects a list of positions against bounding box limits.

        Args:
            input (list[State]): List of positions to verify.

        Returns:
            list[State]: Corrected list of positions.

        Raises:
            TrajectoryError: If anchor positions are not initialized.
        """
        output = [state.copy() for state in input]

        for index in range(len(input)):
            try:
                output[index] = self._keep_in_box(input[index])
            except TrajectoryError as message:
                raise TrajectoryError(message)
            
        return output
    
    def transform_positions(self, positions:list[list[State]]) -> list[list[State]]:
        """Transforms drone trajectory data from per-drone format to synchronized steps.

        Converts the list from [drone][position] to [position][drone] format.

        Args:
            positions (list[list[State]]): Positions of each drone.

        Returns:
            list[list[State]]: Transformed structure for synchronized processing.
        """
        # transform the positions from the format created by the functions zylinder to [positions][drones]
        transformed = []
        #print(f"length of positions: {len(positions)}, length of first position: {len(positions[0])}")
        for i in range(len(positions[0])): #number of points per drone
            position = []
            for index in range(len(positions)): # number of drones
                position.append(positions[index][i])
            transformed.append(position)
        #print(f"length of transformed positions: {len(transformed)}, length of first position: {len(transformed[0])}")
        return transformed
    
    def verify(self, coordinates:list[list[State]]) -> list[list[State]]:
        """Verifies all coordinates for all drones.

        Args:
            coordinates (list[list[State]]): List of trajectories per drone.

        Returns:
            list[list[State]]: Verified trajectories.
        """
        verified_coordinates = []
        for coordinate in coordinates:
            verified_coordinates.append(self.verify_position(coordinate))
        
        return verified_coordinates
    
    
    def circle(self, radius:float, positions:int, altitude:float) -> list[list[State]]:
        """Generates circular trajectories around the object for multiple drones.

        Args:
            radius (float): Radius of the circle around the object.
            positions (int): Number of discrete points per circle.
            altitude (float): Altitude at which to fly.

        Returns:
            list[list[State]]: 3D trajectory positions for each drone.
        """
        # calculate the coordinates for circling around an object with all the drones in the swarm
        # calculate every position for 1 drone
        first_drone = []
        for index in range(positions):
            try:
                x = self._object_placement.x - radius * cos(2 * pi * index / positions)
                y = self._object_placement.y - radius * sin(2 * pi * index / positions)
            except AttributeError:
                self.print("object position not set", self.LogLevel.error)
                raise TrajectoryError("object position not set")
            yaw = 360 * index / positions
            first_drone.append(State(x=x, y=y, z=altitude, yaw=yaw))
        # shift points to place all drones on the same circle
        second_drone = first_drone[int(positions / 2):] + first_drone[:int(positions / 2)]
        third_drone = first_drone[int(positions / 4):] + first_drone[:int(positions / 4)]
        fourth_drone = first_drone[int(3 * positions / 4):] + first_drone[:int(3 * positions / 4)]
        # create final data structure
        all_drones = []
        results = []
        for index in range(positions):
            all_drones.append([first_drone[index], fourth_drone[index], second_drone[index], third_drone[index]])
            results.append(all_drones[index][:self._count])
        return results # shape: [positions][drones]
    
    def zylinder(self, radius:float, positions:int, object_height:float=OBJECT_HEIGHT, object_position:State=OBJECT_POSITION, number_circles:int=1, vertical:bool=False) -> list[list[State]]:
        """
        Calculates 3D coordinates for a drone swarm to move around a cylindrical object.

        Each drone flies in a circular / vertical trajectory around the object at a unique height and starts at a different angular position.  

        Parameters:
            radius (float): Radius of the circular trajectory around the object in meters.  
                            It should include a safety margin (recommended: at least 0.5 meters).
            positions (int): Total number of image capture positions of one drone.
            object_height (float): Height of the object in meters.
            object_position (State): 3D position of the object in meters.  
                                      The object is assumed to be centered at this position.
            vertical (bool): If False, drones fly in circle movements  
                             If True, drones move vertically at their assigned section

        Returns:
            drone_positions (List[List[State]]): A list containing one list per drone,  
            where each inner list consists of `State` objects representing the planned 3D positions for that drone.
        
        The calculation considers a safety distance from the bottom and top of the object, according to the border of the .
        """
        lower_bound = max(object_position.get_z()- object_height/2 , self._bounds["down"] + 0.4) # 0.4 safety distance from bottom
        upper_bound = min(object_position.get_z() + object_height/2, self._bounds["up"] - 0.2) # 0.2 safety distance from top
        area = upper_bound - lower_bound
        #print(f"lower bound {lower_bound}, upper bound {upper_bound}")
        if self.get_count() == 0:
            self.print("drone count not set", level=self.LogLevel.error)
            return -1
        drone_count = self.get_count()
        drone_positions = []
        
        # circular movement
        if not vertical:
            z_offset = area / (drone_count*number_circles+1)
            #print(f"Offset between circles: {z_offset}, calculated from {area} / {drone_count*number_circles+1}")
            self.print(f"Number of circles per drone: {number_circles}, Number of drones: {self.get_count()}, Total number of circles: {number_circles * self.get_count()}", level=LogLevel.message)

            num_of_positions_per_circle = ceil(positions/number_circles)
            num_of_positions_per_circle = positions
            
            for drone in range(self.get_count()):
                angle_offset = drone * (360 / self._count)
               # print(f"Drone {drone} angle offset: {angle_offset}")
                drone_positions.append([])
                for circle in range(number_circles):
                    z = lower_bound + z_offset + z_offset* drone_count * circle + drone * z_offset
                    #print(f"Drone {drone} circle: {circle}, z: {z:.2f}")
                    for i in range(num_of_positions_per_circle):
                        x = object_position.x - radius * cos(2*pi*i/num_of_positions_per_circle + (pi/180)*angle_offset)
                        y = object_position.y + radius * sin(2*pi*i/num_of_positions_per_circle + (pi/180)*angle_offset)
                        yaw = ((-i / num_of_positions_per_circle)*360 + angle_offset) % 360 
                        self.print(f"Drone {drone} circle: {circle}, position: {i}, x:{x:.2f}, y:{y:.2f},z:{z:.2f} yaw: {yaw:.2f}", level=LogLevel.debug)
                        
                        drone_positions[drone].append(State(x,y,z,0,0,yaw))
            
            return drone_positions # shape: [drone][positions]
        # vertical movement
        else:
            # calculating number of vertical segment, number of layers for each segment and number of positions for each layer of each segment
            num_of_vertical_segments = self.get_count()
            num_of_layers = number_circles
            #num_of_positions_per_slice = ceil(positions/num_of_layers)
            num_of_positions_per_slice = positions
            z_offset = area / (number_circles+1)
            for drone in range(num_of_vertical_segments):
                angle_offset = drone * (360 / self.get_count())
                drone_positions.append([])
                for layer in range(num_of_layers):
                    z = lower_bound + z_offset + z_offset * layer
                    for i in range(num_of_positions_per_slice):
                        # redirect the positions calculation every second slice, to fly more efficient
                        if layer % 2 == 1:
                            i = num_of_positions_per_slice-1-i 
                        x = object_position.x - radius * cos(2*pi*i/num_of_positions_per_slice/num_of_vertical_segments + (pi/180)*angle_offset)
                        y = object_position.y + radius * sin(2*pi*i/num_of_positions_per_slice/num_of_vertical_segments + (pi/180)*angle_offset)
                        yaw = ((-i / num_of_positions_per_slice/num_of_vertical_segments)*360 + angle_offset) % 360 

                        drone_positions[drone].append(State(x,y,z,yaw,0,0))
                        i = num_of_positions_per_slice -1 -i
            
            return drone_positions


    def print_trajectory(self,positions: list[list[State]], add_object:bool=False, object_position:State=OBJECT_POSITION):
        ''' 
        Prints set of setpoint, given as a list of states
        positions: State list of position setpoints; multidimensional for multiple drones
        '''
        
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        
        color = ['red', 'blue', 'green', 'brown', 'yellow','cyan', 'black']
        
        drone_count = len(positions)
        points = []
        for drone in range(drone_count):
            points.append([])
            points[drone].append([])
            points[drone].append([])
            points[drone].append([])
            
            for state in positions[drone]:
                points[drone][0].append(state.get_x())
                points[drone][1].append(state.get_y())
                points[drone][2].append(state.get_z())
                ax.scatter(points[drone][0][-1], points[drone][1][-1], points[drone][2][-1], label=f'Drone {drone+1}', marker=f'{drone%4+1}', c=color[drone])
                ax.text(points[drone][0][-1], points[drone][1][-1], points[drone][2][-1],len(points[drone][2]), fontsize=8, color='black')
                
        if add_object:
            ax.scatter(object_position.x, object_position.y, object_position.z, label='Object', marker='o', c='red')
            ax.text(object_position.x, object_position.y, object_position.z, "Object", fontsize=8, color='black')
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        ax.set_title('Single Drone, Baseline ')
        #ax.legend()

        plt.show()   
            
        
    
    
    def get_position(self, x, y, z, yaw=0, pitch=0, roll=0):
        # return a State object from the provided positions
        return State(x=x, y=y, z=z, yaw=yaw, pitch=pitch, roll=roll)

