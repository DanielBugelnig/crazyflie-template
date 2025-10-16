"""
    scan for and control multiple Bitcraze Crazyflie 2.1 drones and AI decks
    
    scans the available USB devices for a dongle, then uses the dongle to scan for CrazyFlies
    scans the available networks for connected AI decks
    control is done via the worker functions in the respective fles

    Veres-Vitalyos Almos (veresvalmos@gmail.com)
    Daniel Bugelnig (daniel.bugelnig@edu.aau.at)
    2024.03.26
"""

import cflib.crtp   # communication over radio
from multiprocessing import Process # parallel execution
from multiprocessing.synchronize import Lock    # hint lock type
import socket   # communication over Wi-Fi
from threading import Thread    # multithreading
from threading import Lock as ThreadLock    # synchronizing
import os  # file paths
import psutil # system information, wifi ip address

from ..constants import MAC_LOOKUP, POSITION_AVERAGE, DISPLAY_IMAGES, OP_SYSTEM, CRAZYFLIES
from ..core.base_utils import BaseClass
from ..core.shared_data import StateManager, State, Flag, Counter

from .crazyflie import worker as cf_worker
from .ai_deck import worker as ai_worker
from .ai_deck import AI_Deck, AIDeckError

class SwarmError(Exception):
    def __init__(self, message=""):
        # Swarm Error
        super().__init__(message)
        return
    
class _SwarmMember:
    # data structure for swarm members
    def __init__(self):
        # identifiers
        self.address = ""
        self.name = ""
        self.mac = ""
        self.ip = ""
        # constants
        self.drone_delay = 0.1
        self.ai_delay = 0.5
        # multiprocessing objects
        self.cf_process:Thread = None
        self.ai_process:Process = None
        self.value_manager = StateManager()
        self.lock:Lock = self.value_manager.Lock()
        # shared values
        self.image_counter:Counter = self.value_manager.Counter()
        self.position_counter:Counter = self.value_manager.Counter()
        self.flag:Flag = self.value_manager.Flag()
        self.next_position:State = self.value_manager.State()
        self.current_state:State = self.value_manager.State()
        return

class CrazySwarm(BaseClass):
    # base class for swarm control

    def __init__(self):
        # initialize Swarm object
        super().__init__()
        # internal use
        self._members:list[_SwarmMember] = []
        self._output_directory = self.get_path()
        self._count = 0
        self._radio_lock = ThreadLock()
        return
    
    def logging(self, enable, file, level):
        # set up logging
        super().logging(enable=enable, file=file, level=level, name="Swarm")
        if enable and file:
            self._output_directory = self.get_path() + os.sep + "datasets" + os.sep + self._logging_directory.split(os.sep)[-1]
            self._check_path(self._output_directory)
        return
    
    def get_directory(self):
        # return the output directory
        # create an output directory if doesn't exist
        if self._output_directory == self.get_path():
            self._output_directory = self.create_directory(self.get_path() + os.sep + "datasets")
        return self._output_directory
    
    def scan(self):
        # scan for swarm members (CrazyFlies, with recognized AI decks)
        try:
            radios = self._scan_cf()
            clients = self._scan_ai()
        except SwarmError as message:
            raise SwarmError(message)
        # create swarm member objects
        for address in radios:
            member = _SwarmMember()
            member.address = address
            try:
                member.name = member.address[-10:]
            except IndexError:
                member.name = "unknown"
            for client in clients:
                mac = client[0]
                ip = client[1]
                if mac == MAC_LOOKUP[member.address]:
                    member.mac = mac
                    member.ip = ip
                    break
            self._members.append(member)
            self._count = self._count + 1
        return radios
    
    def set_delay(self, delay_s_drone:float, delay_s_deck:float):
        # set the wait time for each thread
        for member in self._members:
            member.drone_delay = delay_s_drone
            member.ai_delay = delay_s_deck
        return
    
    def start(self):
        # create an output directory
        if self._output_directory == self.get_path():
            self._output_directory = self.create_directory(self.get_path() + os.sep + "datasets")
        # start all members in separate processes
        for member in self._members:
            # initialize parameters
            cf_params = {"flag": member.flag,                   # shared value (state) to store the current state of each process
                         "counter": member.position_counter,    # shared value (int) to count saved positions
                         "lock": member.lock,                   # lock object from multiprocessing module for the member's processes
                         "thread_lock": self._radio_lock,       # thread lock for synchronizing radio communication
                         "position": member.next_position,      # shared object containing information about the next position of the drone
                         "status": member.current_state,        # keep track of the current state of the drone
                         "delay": member.drone_delay,           # wait time between operations in seconds
                         "address": member.address,             # radio link address
                         "directory": self._output_directory,   # output directory
                         "average_count": POSITION_AVERAGE,     # measurements to average when measuring position
                         "log_enable": self._logging,           # enable/disable logging
                         "log_file": self._logging_file,        # log to file/console
                         "log_level": self._logging_level}      # log severity level
            ai_params = {"flag": member.flag,                   # shared value (state) to store the current state of each process
                         "counter": member.image_counter,       # shared value (int) to count saved images
                         "lock": member.lock,                   # lock object from multiprocessing module for the member's processes
                         "delay": member.ai_delay,              # wait time between operations in seconds
                         "ip": member.ip,                       # IP address (IPv4)
                         "mac": member.mac,                     # MAC address
                         "directory": self._output_directory,   # output directory
                         "display": DISPLAY_IMAGES,             # show/hide recorded image stream
                         "log_enable": self._logging,           # enable/disable logging
                         "log_file": self._logging_file,        # log to file/console
                         "log_level": self._logging_level}      # log severity level
            # set up processes
            member.cf_process = Thread(target=cf_worker, kwargs=cf_params, daemon=False, name="drone_" + member.name)
            member.ai_process = Process(target=ai_worker, kwargs=ai_params, daemon=False, name="deck_" + member.mac)
            # start processes
            member.cf_process.start()
            self.print("drone " + member.name + " started", self.LogLevel.message)
            member.ai_process.start()
            self.print("deck " + member.mac + " started", self.LogLevel.message)
        # wait for all drones
        ready = False
        while not ready:
            for member in self._members:
                if not member.flag.get_connected():
                    ready = False
                    break
                else:
                    ready = True
        self.print("all drones are connected", self.LogLevel.message)
        return
    
    def arm(self, drone_index:int=None):
        # enable flight with drones
        with self._radio_lock:
            try:
                if self._members[drone_index].flag.get_connected():
                    self.print(self._members[drone_index].address + " is ready to fly", self.LogLevel.message)
                    self._members[drone_index].flag.set_ready()
            except (IndexError, TypeError):
                for member in self._members:
                    if member.flag.get_connected():
                        self.print(member.address + " is ready to fly", self.LogLevel.message)
                        member.flag.set_ready()
        return
    
    def stop(self):
        # stop all members (separate processes)
        for member in self._members:
            # set exit flag
            with member.lock:
                member.flag.set_exit()
            member.ai_process.join()
            self.print("deck " + member.mac + " stopped", self.LogLevel.message)
            member.cf_process.join()
            self.print("drone " + member.name + " stopped", self.LogLevel.message)
        return
    
    """ ---------------------------------------------------------------------------- """
    
    def land(self, positions:list[State]=None):
        # land with all drones to the required positions, or where they are
        try:
            for index in range(len(self._members)):
                if positions == None:
                    self.land_single(index)
                else:
                    self.land_single(index, positions[index])
        except IndexError:
            self.print("the number of swarm members and positions don't match", self.LogLevel.error)
            raise SwarmError("the number of swarm members and positions don't match")
        except SwarmError as message:
            raise SwarmError(message)
        return
    
    def fly(self, positions:list[State], photo:bool=True):
        # fly with all drones to the required positions
        try:
            for index in range(len(self._members)):
                self.fly_single(index, positions[index], photo)
        except IndexError:
            self.print("the number of swarm members and positions don't match", self.LogLevel.error)
            raise SwarmError("the number of swarm members and positions don't match")
        except SwarmError as message:
            raise SwarmError(message)
        return
    
    def get_state(self):
        # return a list of states with the current states of the drones
        states = []
        try:
            for index in range(len(self._members)):
                states.append(self.get_state_single(index))
        except SwarmError as message:
            raise SwarmError(message)
        return states
    
    def arrived(self, photo:bool=True):
        # check if all drones arrived at the desired locations and made a picture
        try:
            arrived = True
            for index in range(len(self._members)):
                arrived = self.arrived_single(index, photo)
                if not arrived:
                    break
        except SwarmError as message:
            raise SwarmError(message)
        return arrived
    
    """ ---------------------------------------------------------------------------- """

    def land_single(self, index:int, position:State=None):
        # land with a signle drone
        try:
            if position == None:
                # land everything where they are
                with self._members[index].lock:
                    self._members[index].next_position.set_grounded(True)
                    self._members[index].next_position.set_x(None)
                    self._members[index].flag.set_position_updated()
            else:
                # land on the required position
                with self._members[index].lock:
                    self._members[index].next_position.set_x(position.get_x())
                    self._members[index].next_position.set_y(position.get_y())
                    self._members[index].next_position.set_z(position.get_z())
                    self._members[index].next_position.set_yaw(position.get_yaw())
                    self._members[index].next_position.set_pitch(position.get_pitch())
                    self._members[index].next_position.set_roll(position.get_roll())
                    self._members[index].next_position.set_grounded(True)
                    self._members[index].flag.set_position_updated()
        except IndexError:
            self.print("drone not found", self.LogLevel.error)
            raise SwarmError("drone not found")
        return
    
    def fly_single(self, index:int, position:State, photo:bool=True):
        # fly with a single drone
        try:
            with self._members[index].lock:
                self._members[index].next_position.set_x(position.get_x())
                self._members[index].next_position.set_y(position.get_y())
                self._members[index].next_position.set_z(position.get_z())
                self._members[index].next_position.set_yaw(position.get_yaw())
                self._members[index].next_position.set_pitch(position.get_pitch())
                self._members[index].next_position.set_roll(position.get_roll())
                if photo:
                    self._members[index].flag.set_position_updated()
                else:
                    self._members[index].flag.set_position_updated_no_save()
        except IndexError:
            self.print("drone not found", self.LogLevel.error)
            raise SwarmError("drone not found")
        return
    
    def get_state_single(self, index:int):
        # get the state of a single drone
        try:
            result = State()
            result.set_x(self._members[index].current_state.get_x())
            result.set_y(self._members[index].current_state.get_y())
            result.set_z(self._members[index].current_state.get_z())
            result.set_yaw(self._members[index].current_state.get_yaw())
            result.set_pitch(self._members[index].current_state.get_pitch())
            result.set_roll(self._members[index].current_state.get_roll())
            result.set_battery(self._members[index].current_state.get_battery())
            result.set_grounded(self._members[index].current_state.get_grounded())
            return result
        except IndexError:
            self.print("drone not found", self.LogLevel.error)
            raise SwarmError("drone not found")
        
    def arrived_single(self, index:int, photo:bool=True):
        # check if the drone arrived at the destination and has made a picture
        try:
            if photo:
                return self._members[index].flag.get_position_saved()
            else:
                return self._members[index].flag.get_on_position_no_save()
        except IndexError:
            self.print("drone not found", self.LogLevel.error)
            raise SwarmError("drone not found")

    """ ---------------------------------------------------------------------------- """

    def get_count(self):
        # return the number of swarm members
        return self._count

    """ ---------------------------------------------------------------------------- """

    def _scan_cf(self):
        # scan for CrazyFlies, return the addresses
        available = []
        self.print("scanning for drones", self.LogLevel.message)
        cflib.crtp.init_drivers()   # initialize the low level drivers
        for address in CRAZYFLIES:   #996028180480):
            temp = cflib.crtp.scan_interfaces(address=int(address[-10:],16))
            try:
                available.append(temp[0])
            except IndexError:
                continue
        addresses = []
        if len(available) > 0:
            self.print("drones found:", self.LogLevel.info)
            # list available devices
            for index in range(len(available)):
                self.print("\t" + str(available[index][0]), self.LogLevel.info)
                addresses.append(available[index][0])
        else:
            self.print("no drones found", self.LogLevel.error)
            raise SwarmError("no drones found")
        return addresses

    """ ---------------------------------------------------------------------------- """

    def _scan_ai(self):
        # scan for AI decks, return the (mac, ip) pairs
        try:
            helper = AI_Deck()
            helper.logging(self._logging, self._logging_file, self._logging_level, self._logging_directory)
            if not helper._check_wifi(retries=1):
                helper._set_wifi()
                helper._connect_wifi()
                if not helper._check_wifi():
                    self.print("unable to scan for AI decks", self.LogLevel.error)
                    raise SwarmError("unable to scan for AI decks")
        except AIDeckError as message:
            raise SwarmError(message)
        hostname = socket.gethostname()
        networks = self.get_wifi_ip()
        self.print("hostname: " + hostname, self.LogLevel.debug)
        self.print("networks found: " + networks, self.LogLevel.debug)
        
        # collect MAC addresses which responded
        response, _ = self._run_cmd("arp -a")
        lines = response.split("\n")
        addresses = []
        self.print("devices responding on available networks:", self.LogLevel.debug)
        for line in lines[1:]:
            try:
                index = 2 if OP_SYSTEM == "Linux" else 1
                mac = line.split()[index] # on linux MAC is on inddex 2, on windows probably on 1
                ip = line.split()[0]
                self.print("\t" + mac + "\t-\t" + ip, self.LogLevel.debug)
                if mac in MAC_LOOKUP.values():
                    addresses.append((mac, ip))
                else:
                    # MAC address not registered
                    continue
            except IndexError:
                # this line doesn't contain AI decks
                continue
        if len(addresses) == 0:
            self.print("no AI decks were found", self.LogLevel.error)
            raise SwarmError("no AI decks were found")
        return addresses
    
    def get_wifi_ip(self):
        for interface, addrs in psutil.net_if_addrs().items():
            if "wlp" in interface or "wlan" in interface: 
                for addr in addrs:
                    if addr.family == socket.AF_INET:  # IPv4 address
                        return addr.address  # return the first Wi-Fi IP found
        return "No Wi-Fi IP found"

