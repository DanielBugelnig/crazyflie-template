"""
    store datatypes which are intended for sharing between processes

    Daniel Bugelnig, 2025 (daniel.bugelnig@aau.at)
"""

from multiprocessing import Lock                    # synchronization
from multiprocessing.managers import BaseManager    # sharing state data between processes
import math

""" ---------------------------------------------------------------------------- """

class StateManager(BaseManager):
    # share state data between processes
    def __init__(self):
        super().__init__()
        self.register("State", State)
        self.register("Counter", Counter)
        self.register("Flag", Flag)
        self.register("Lock", Lock)
        self.start()
        return

""" ---------------------------------------------------------------------------- """

class State:
    # defines the state of the drone (serializable)
    def __init__(self, x=0, y=0, z=0, pitch=0, roll=0, yaw=0, battery=0):
        self.x = x           # x position in meters
        self.y = y           # y position in meters
        self.z = z           # z position in meters
        self.pitch = pitch   # pitch angle in degrees (-180 - +180)
        self.roll = roll     # roll angle in degrees (-180 - +180)
        self.yaw = yaw       # yaw angle in degrees (-180 - +180)
        self.battery = battery     # battery percentage with 10% resolution
        self.grounded = False
        return
    
    # setters
    def set_x(self, x):
        self.x = x
        return
    
    def set_y(self, y):
        self.y = y
        return
    
    def set_z(self, z):
        self.z = z
        return
    
    def set_roll(self, roll):
        self.roll = roll
        return
    
    def set_pitch(self, pitch):
        self.pitch = pitch
        return
    
    def set_yaw(self, yaw):
        self.yaw = yaw
        return
    
    def set_battery(self, battery):
        self.battery = battery
        return
    
    def set_grounded(self, grounded):
        self.grounded = grounded
        return

    # getters
    def get_x(self):
        return self.x
    
    def get_y(self):
        return self.y
    
    def get_z(self):
        return self.z
    
    def get_roll(self):
        return self.roll
    
    def get_pitch(self):
        return self.pitch
    
    def get_yaw(self):
        return self.yaw
    
    def get_battery(self):
        return self.battery
    
    def get_grounded(self):
        return self.grounded
    
    def copy(self):
        return State(self.x, self.y, self.z, self.pitch, self.roll, self.yaw, self.grounded)
    # magic functions
    def __str__(self):
        data = "state:\n"
        data = data + "\tx: " + "{:.2f}\n".format(self.x)
        data = data + "\ty: " + "{:.2f}\n".format(self.y)
        data = data + "\tz: " + "{:.2f}\n".format(self.z)
        data = data + "\troll: " + "{:.2f}\n".format(self.roll)
        data = data + "\tpitch: " + "{:.2f}\n".format(self.pitch)
        data = data + "\tyaw: " + "{:.2f}\n".format(self.yaw)
        data = data + "\tbattery: " + "{:.2f}\n".format(self.battery)
        return data
    
    def __getstate__(self):
        return self.__dict__
    
    def __setstate__(self, data):
        self.__dict__ = data
        return
    
    def __eq__(self, other):
        if not isinstance(other, State):
            return NotImplemented

        return (
            math.isclose(self.x, other.x, abs_tol=1e-4) and
            math.isclose(self.y, other.y, abs_tol=1e-4) and
            math.isclose(self.z, other.z, abs_tol=1e-4) and
            math.isclose(self.yaw, other.yaw, abs_tol=1e-3) and
            math.isclose(self.pitch, other.pitch, abs_tol=1e-3) and
            math.isclose(self.roll, other.roll, abs_tol=1e-3)
        )

    def __ne__(self, other):
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return NotImplemented
        return not eq
    
    def copy(self):
        return State(self.x, self.y, self.z, self.pitch, self.roll, self.yaw, self.battery)
    
""" ---------------------------------------------------------------------------- """

class Counter:
    # simple counter
    def __init__(self):
        self.value = 0
        return
    
    def increment(self):
        self.value = self.value + 1
        return
    
    def decrement(self):
        self.value = self.value - 1
        return
    
    def set(self, value):
        self.value = value
        return
    
    def get(self):
        return self.value
    
    def __getstate__(self):
        return self.__dict__
    
    def __setstate__(self, data):
        self.__dict__ = data
        return

""" ---------------------------------------------------------------------------- """

class Flag:
    # state flag
    def __init__(self):
        self._positioning = 0
        self._on_position = 1
        self._recording = 2
        self._image_saved = 3
        self._position_saved = 4
        self._position_updated = 5
        self._idle = 6
        self._exit = 7
        self._converted = 8
        self._parsed = 9
        self._moved = 10
        self._processed = 11
        self._scanned = 12
        self._connected = 13
        self._ready = 14
        self._not_initialized = 15
        self._disconnected = 16
        self._position_updated_no_save = 17
        self._positioning_no_save = 18
        self._on_position_no_save = 19

        self.value = self._not_initialized
        return
    
    def set(self, value):
        self.value = value
        return
    
    def get(self):
        return self.value
    
    def __getstate__(self):
        return self.__dict__
    
    def __setstate__(self, data):
        self.__dict__ = data
        return
    
    def get_positioning(self):
        if self.value == self._positioning:
            return True
        return False
    
    def set_positioning(self):
        self.value = self._positioning
        return
    
    def get_on_position(self):
        if self.value == self._on_position:
            return True
        return False
    
    def set_on_position(self):
        self.value = self._on_position
        return
    
    def get_recording(self):
        if self.value == self._recording:
            return True
        return False
    
    def set_recording(self):
        self.value = self._recording
        return
    
    def get_image_saved(self):
        if self.value == self._image_saved:
            return True
        return False
    
    def set_image_saved(self):
        self.value = self._image_saved
        return
    
    def get_position_saved(self):
        if self.value == self._position_saved:
            return True
        return False
    
    def set_position_saved(self):
        self.value = self._position_saved
        return
    
    def get_position_updated(self):
        if self.value == self._position_updated:
            return True
        return False
    
    def set_position_updated(self):
        self.value = self._position_updated
        return

    def get_idle(self):
        if self.value == self._idle:
            return True
        return False
    
    def set_idle(self):
        self.value = self._idle
        return

    def get_exit(self):
        if self.value == self._exit:
            return True
        return False
    
    def set_exit(self):
        self.value = self._exit
        return
    
    def get_converted(self):
        if self.value == self._converted:
            return True
        return False
    
    def set_converted(self):
        self.value = self._converted
        return
    
    def get_parsed(self):
        if self.value == self._parsed:
            return True
        return False
    
    def set_parsed(self):
        self.value = self._parsed
        return
    
    def get_moved(self):
        if self.value == self._moved:
            return True
        return False
    
    def set_moved(self):
        self.value = self._moved
        return
    
    def get_processed(self):
        if self.value == self._processed:
            return True
        return False
    
    def set_processed(self):
        self.value = self._processed
        return
    
    def get_scanned(self):
        if self.value == self._scanned:
            return True
        return False
    
    def set_scanned(self):
        self.value = self._scanned
        return
    
    def get_connected(self):
        if self.value == self._connected:
            return True
        return False
    
    def set_connected(self):
        self.value = self._connected
        return
    
    def get_ready(self):
        if self.value == self._ready:
            return True
        return False
    
    def set_ready(self):
        self.value = self._ready
        return

    def get_not_initialized(self):
        if self.value == self._not_initialized:
            return True
        return False
    
    def set_not_initialized(self):
        self.value = self._not_initialized
        return

    def get_disconnected(self):
        if self.value == self._disconnected:
            return True
        return False
    
    def set_disconnected(self):
        self.value = self._disconnected
        return
    
    def get_position_updated_no_save(self):
        if self.value == self._position_updated_no_save:
            return True
        return False
    
    def set_position_updated_no_save(self):
        self.value = self._position_updated_no_save
        return
    
    def get_position_updated_no_save(self):
        if self.value == self._position_updated_no_save:
            return True
        return False
    
    def set_position_updated_no_save(self):
        self.value = self._position_updated_no_save
        return
    
    def get_positioning_no_save(self):
        if self.value == self._positioning_no_save:
            return True
        return False
    
    def set_positioning_no_save(self):
        self.value = self._positioning_no_save
        return
    
    def get_on_position_no_save(self):
        if self.value == self._on_position_no_save:
            return True
        return False
    
    def set_on_position_no_save(self):
        self.value = self._on_position_no_save
        return
