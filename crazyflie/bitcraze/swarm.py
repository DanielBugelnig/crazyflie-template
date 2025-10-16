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
    """Generic exception for CrazySwarm-related failures.

    This exception is raised for high-level swarm operations such as scanning,
    starting, stopping, and coordinating Crazyflies and AI decks.

    Args:
        message (str, optional): Human-readable error description. Defaults to "".
    """
    def __init__(self, message=""):
        # Swarm Error
        super().__init__(message)
        return
    
class _SwarmMember:
    """Container for a single swarm member (Crazyflie + optional AI Deck).

    Holds identifiers, timing parameters, synchronization primitives, and shared
    state objects used by the worker thread/process.

    Attributes:
        address (str): Crazyflie radio URI/address (e.g., 'radio://0/80/2M/E7E7E7E7E7').
        name (str): Human-readable short name derived from the address.
        mac (str): AI deck MAC address if paired/known, else empty string.
        ip (str): AI deck IPv4 address if detected, else empty string.
        drone_delay (float): Sleep interval (seconds) between drone control steps.
        ai_delay (float): Sleep interval (seconds) between AI deck steps.
        cf_process (Thread | None): Thread running the Crazyflie worker.
        ai_process (Process | None): Process running the AI deck worker.
        value_manager (StateManager): Factory for shared state objects.
        lock (multiprocessing.synchronize.Lock): Inter-process lock for this member.
        image_counter (Counter): Shared counter of saved images.
        position_counter (Counter): Shared counter of saved positions.
        flag (Flag): Shared flags for lifecycle and synchronization.
        next_position (State): Target state/position for the next command.
        current_state (State): Last known measured/estimated state.
    """
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
    """High-level controller for scanning and coordinating a Crazyflie swarm.

    This class discovers Crazyflie 2.1 drones via radio, associates them with
    AI decks discovered on the local network, and manages their life cycle.
    Each drone is handled by a worker thread; each AI deck is handled by a
    separate process to isolate compute/IO workloads.
    """


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
        """Initialize a CrazySwarm instance.

        Sets up internal member storage, output directory handling, and a
        thread-level radio lock to serialize low-level radio operations.
        """
        super().logging(enable=enable, file=file, level=level, name="Swarm")
        if enable and file:
            self._output_directory = self.get_path() + os.sep + "datasets" + os.sep + self._logging_directory.split(os.sep)[-1]
            self._check_path(self._output_directory)
        return
    
    def get_directory(self):
        """Return (and ensure) the current output directory for datasets.

        If no dedicated dataset directory exists yet for this session, one is
        created under `<project_root>/datasets`.

        Returns:
            str: Absolute path to the output directory used by workers.
        """
        if self._output_directory == self.get_path():
            self._output_directory = self.create_directory(self.get_path() + os.sep + "datasets")
        return self._output_directory
    
    def scan(self):
        """Scan for Crazyflie radios and associated AI decks.

        Performs a radio scan using `cflib` and a local network scan for AI decks,
        then builds an internal list of `_SwarmMember` objects, pairing drones to
        decks via the configured MAC lookup.

        Returns:
            list[str]: List of Crazyflie radio addresses found.

        Raises:
            SwarmError: If no drones or no AI decks are found, or scanning fails.
        """
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
        """Set the loop sleep delays for drone and AI deck workers.

        Args:
            delay_s_drone (float): Sleep interval (seconds) for the Crazyflie worker thread.
            delay_s_deck (float): Sleep interval (seconds) for the AI deck worker process.

        Returns:
            None
        """
        for member in self._members:
            member.drone_delay = delay_s_drone
            member.ai_delay = delay_s_deck
        return
    
    def start(self):
        """Launch worker thread/process for each swarm member and wait for readiness.

        Ensures a dataset output directory exists, creates and starts:
        - one `Thread` per Crazyflie running `cf_worker`
        - one `Process` per AI deck running `ai_worker`

        Blocks until each member's `Flag` indicates a successful connection.

        Raises:
            SwarmError: If any member fails to initialize or connect.
        """
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
        """Arm one or all Crazyflies for flight (set 'ready' flag).

        If `drone_index` is provided and valid, arms only that drone.
        Otherwise, arms all connected drones.

        Args:
            drone_index (int | None): Index of the drone to arm; if None, arm all.

        Returns:
            None
        """
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
        """Gracefully stop all worker thread/process pairs in the swarm.

        Sets the exit flag for each member, then joins the AI deck process
        and the Crazyflie thread to ensure clean shutdown.

        Returns:
            None
        """
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
        """Command all drones to land, optionally at specified target positions.

        If `positions` is None, each drone lands at its current location.
        Otherwise, each drone lands at the corresponding position in `positions`.

        Args:
            positions (list[State] | None): Target landing positions per drone.

        Raises:
            SwarmError: If the number of positions does not match the swarm size,
                or if a member access fails.
        """
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
        """Command all drones to fly to target positions (optionally save photo).

        Args:
            positions (list[State]): Desired target states/poses for each drone.
            photo (bool): If True, mark the position as one where an image should be saved.

        Raises:
            SwarmError: If the number of positions does not match the swarm size,
                or if a member access fails.
        """
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
        """Get the current measured/estimated state for each drone.

        Returns:
            list[State]: Shallow copies of each drone's current state.

        Raises:
            SwarmError: If a member access fails.
        """
        # return a list of states with the current states of the drones
        states = []
        try:
            for index in range(len(self._members)):
                states.append(self.get_state_single(index))
        except SwarmError as message:
            raise SwarmError(message)
        return states
    
    def arrived(self, photo:bool=True):
        """Check if all drones reached their targets (and optionally saved photos).

        Args:
            photo (bool): If True, require that the 'position saved' flag is set;
                otherwise only check arrival without save.

        Returns:
            bool: True if every drone reports arrival (and photo saved if requested).

        Raises:
            SwarmError: If a member access fails.
        """
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
        """Land a single drone, optionally at a specified position.

        If `position` is None, the drone lands at its current location.

        Args:
            index (int): Index of the drone within the swarm.
            position (State | None): Target landing state/pose.

        Raises:
            SwarmError: If the drone index is invalid.
        """
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
        """Command a single drone to fly to a given position.

        Optionally flag the position to trigger image capture on arrival.

        Args:
            index (int): Drone index within the swarm.
            position (State): Target state/pose to reach.
            photo (bool): If True, signal that the position should trigger a save.

        Raises:
            SwarmError: If the drone index is invalid.
        """
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
        """Return a copy of the current state for a single drone.

        Args:
            index (int): Drone index within the swarm.

        Returns:
            State: A new `State` object populated with the drone's current values.

        Raises:
            SwarmError: If the drone index is invalid.
        """
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
        """Check arrival status for a single drone (and optional photo save).

        Args:
            index (int): Drone index within the swarm.
            photo (bool): If True, require that 'position saved' is True; otherwise
                only require arrival without save.

        Returns:
            bool: True if the arrival condition is satisfied; False otherwise.

        Raises:
            SwarmError: If the drone index is invalid.
        """
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
        """Return the number of discovered/registered swarm members.

        Returns:
            int: Count of `_SwarmMember` objects currently managed.
        """
        return self._count

    """ ---------------------------------------------------------------------------- """

    def _scan_cf(self):
        """Scan for Crazyflie devices via radio.

        Uses `cflib.crtp.scan_interfaces` for each configured address pattern,
        returning a list of available radio URIs.

        Returns:
            list[str]: List of Crazyflie radio addresses found.

        Raises:
            SwarmError: If no drones are discovered.
        """
        # scan for CrazyFlies, return the addresses
        available = []
        self.print("scanning for drones", self.LogLevel.message)
        cflib.crtp.init_drivers()   # initialize the low level drivers
        for address in CRAZYFLIES:   
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
        """Scan local networks for AI Decks and return recognized (MAC, IP) pairs.

        Ensures Wi-Fi is connected/configured through `AI_Deck` helper, then uses
        `arp -a` output to find responding devices. Filters devices by known MACs
        from `MAC_LOOKUP`.

        Returns:
            list[tuple[str, str]]: List of `(mac, ip)` pairs for recognized AI decks.

        Raises:
            SwarmError: If Wi-Fi cannot be prepared/verified or no decks are found.
        """
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
        """Return the IPv4 address of the active Wi-Fi interface, if any.

        Scans network interfaces for those typically named like Wi-Fi (e.g., 'wlp*',
        'wlan*') and returns the first IPv4 address found.

        Returns:
            str: IPv4 address as a string, or "No Wi-Fi IP found" if none detected.
        """
        for interface, addrs in psutil.net_if_addrs().items():
            if "wlp" in interface or "wlan" in interface: 
                for addr in addrs:
                    if addr.family == socket.AF_INET:  # IPv4 address
                        return addr.address  # return the first Wi-Fi IP found
        return "No Wi-Fi IP found"

