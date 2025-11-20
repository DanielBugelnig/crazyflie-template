"""
Bitcraze Crazyflie 2.1 control utilities.

This module provides a high-level `CrazyFlie` controller class that wraps common
tasks around connecting to a Crazyflie 2.1, configuring the estimator/controller,
state logging, command streaming in a dedicated thread, and simple mission
primitives such as fly-to and land. It also includes a `worker` entry point
designed for multi-process/multi-thread orchestration with shared flags and
state objects.

Design Overview:
    * Connection layer: Uses `cflib` (Crazyflie Python library) to initialize
      radio drivers, open a link and subscribe to connection callbacks.
    * State logging: A `LogConfig` is configured to stream position/attitude/
      battery into an internal `State` object at a configurable rate.
    * Flight thread: A commander loop runs in its own thread to repeatedly send
      setpoints, enforce yaw rate limits, check battery/alarm conditions, and
      handle landing/stop sequences.
    * Synchronization: A radio `Lock` serializes param/log access across
      multiple drones; an internal `Lock` protects setpoint/landing updates.
    * Orchestration: The `worker(...)` function shows one way to combine
      multiprocessing flags and shared objects to coordinate multiple drones.

Prerequisites:
    - `cflib` installed and radio drivers available.
    - A localization system (LPS, OptiTrack, Lighthouse, etc.) publishing
      into the Crazyflie estimator when position setpoints are used.
    - Proper URIs in `CRAZYFLIES` and a `MAC_LOOKUP` for AI-Decks (optional).

Authors:
    Veres-Vitalyos Almos (veresvalmos@gmail.com)
    Daniel Bugelnig (daniel.bugelnig@aau.at)

Year:
    2025
"""

from pathlib import Path  # file paths
from copy import deepcopy
import cflib.crtp   # connection through radio link
from cflib.crazyflie import Crazyflie   # communicate with the drone
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie # synchronous behaviour
from time import sleep, time  # delays
from cflib.crazyflie.log import LogConfig   # logging from the drone
from cflib.crazyflie.syncLogger import SyncLogger   # synchronous logging
from threading import Thread, Lock    # flight commander running in different thread
from multiprocessing.synchronize import Lock as ProcessLock   # hint lock type
from os import sep  # file paths
from pynput import keyboard    # keyboard listener

from crazyflie.constants import MAC_LOOKUP, LOW_BATTERY, RATED_CURRENT, ARRIVAL_THRESHOLD_DISTANCE, ARRIVAL_THRESHOLD_ANGLE, ARRIVAL_THRESHOLD_DISTANCE_ROUGH, ARRIVAL_THRESHOLD_ANGLE_ROUGH
from crazyflie.constants import CRAZYFLIES, TIMEOUT, MOCAP_FRESH_MS, MOCAP_SETTLE_S, MOCAP_TX_RATE_HZ, RIGID_BODY_ID_LOOKUP
from crazyflie.core.base_utils import BaseClass, LogLevel
from crazyflie.core.shared_data import State, Counter, Flag
from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor

class CrazyFlieError(Exception):
    """Exception raised for Crazyflie-specific errors.

    This custom exception type is used across the module to indicate failures
    related to connection, logging, parameter access, or flight control.

    Attributes:
        message: Optional human-readable error message.
    """
    def __init__(self, message=""):
        # Crazy Flie Error
        super().__init__(message)
        return

class CrazyFlie(BaseClass):
    """High-level controller for a Bitcraze Crazyflie 2.1 drone.

    This class:
      - Handles scanning/connecting/disconnecting to a Crazyflie.
      - Configures the estimator/controller and waits for a stable state.
      - Sets up synchronous logging of state estimates and battery voltage.
      - Runs a dedicated commander thread to continuously stream position
        setpoints to the drone with simple safety checks (battery, landing).
      - Exposes primitives to send a target pose (`fly`), land (`land`),
        and stop motors (`motors_off`).

    Typical Usage:
        >>> cf = CrazyFlie("radio://0/100/2M/E7E7E7E701")
        >>> cf.logging(enable=True, file=True, level=LogLevel.info)
        >>> cf.scan()                # optional if address is known
        >>> cf.connect(start_flying=False)
        >>> cf.fly(State(x=0.0, y=0.0, z=0.5, yaw=0.0))
        >>> # ...
        >>> cf.land()
        >>> cf.disconnect()

    Thread-safety:
        - Use `set_radio_lock()` when coordinating multiple drones to serialize
          param/log operations on the radio.
        - Internal setpoints are protected with an instance-level `Lock`.

    Notes:
        - Position setpoints require a working position estimator (e.g. EKF)
          with external positioning input.
    """
    _cf_ID = 0
    def __init__(self, address=""):
        """Initialize the CrazyFlie controller object (not connected yet).

        Args:
            address: Crazyflie URI (e.g., 'radio://0/100/2M/E7E7E7E701'). If
                empty, `scan()` can be used to find one.
        """
        # initialize the object
        super().__init__()
        #   for internal use
        # flags
        self._blocking = True
        self._test_mode = False
        self._flying = False
        # objects
        self._cf_ID = CrazyFlie._cf_ID
        CrazyFlie._cf_ID += 1
        self.natnet_monitor:NatNetRigidBodyMonitor = None
        self.ext_pos_thread:Thread = None
        self._cf:Crazyflie = None
        self._scf:SyncCrazyflie = None
        self._log_config:LogConfig = None
        self._current_state = State()
        self._initial_position = State()
        self._next_position = State()
        self._landing_position:State = None
        self._flight_thread:Thread = None
        self._lock = Lock()
        self._radio_lock:Lock = None
        # other values
        self._address = address
        try:
            self._name = self._address[-10:]
        except IndexError:
            self._name = ""
        self._update_time = 100
        self._mac = ""
        self._delay = 0.1
        self._position_counter = 0
        self._directory = self.get_path()
        # keyboard events
        self.keyboard_listener._on_press = self._on_press
        self.keyboard_listener._on_release = self._on_release
        self.keyboard_listener.start()
        
    
    def logging(self, enable, file, level, directory:str=None):
        """Configure BaseClass logging for this instance.

        Args:
            enable: Enable/disable logging globally for this instance.
            file: If True, write logs to file; otherwise console-only.
            level: Logging level (see `LogLevel`).
            directory: Optional directory for log files. If None, BaseClass
                default is used.

        Returns:
            None
        """
        super().logging(enable=enable, file=file, level=level, name="CrazyFlie_" + self._name, directory=directory)
        return
    
    def scan(self, specific=None): # register specific address, format radio://0/100/2M/E7E7E7E701
        """Scan for available Crazyflies and select one.

        If a specific URI is provided, the method uses it directly after
        initializing drivers. Otherwise, it iterates through `CRAZYFLIES` and
        tries to match discovered interfaces.

        Args:
            specific: Optional URI string (e.g., 'radio://0/100/2M/E7E7E7E701').

        Raises:
            CrazyFlieError: If no drone is found.

        Returns:
            None. Updates `self._address` and `self._name` on success.
        """
        if not specific == None:
            self.print(f"scanning for specific drone: {specific}", self.LogLevel.message)
            try:
                self._address = specific
                try:
                        self._name = self._address[-10:]
                        
                except IndexError:
                        self._name = "unknown"
                self.print("drone found: " + self._address, self.LogLevel.message)
                cflib.crtp.init_drivers()   # initialize the low level drivers

                return
            except IndexError:
                pass

        # return the first address
        self.print("scanning for available drones, can take a while", self.LogLevel.message)
        cflib.crtp.init_drivers()   # initialize the low level drivers
        for address in CRAZYFLIES:
            temp = cflib.crtp.scan_interfaces(address=int(address[-10:],16))
            try:
                self._address = str(temp[0][0])
                try:
                    self._name = self._address[-10:]
                except IndexError:
                    self._name = "unknown"
                self.print("drone found: " + self._address, self.LogLevel.info)
                return
            except IndexError:
                continue
        self._state.set_scanned()
        self.print("no drones found, ", self.LogLevel.error)
        raise CrazyFlieError("no drones found, verify address in constant.py")

    def connect(self, start_flying=True, localization_mode="Optitrack"):
        """Connect to the Crazyflie and initialize flight/logging.
        

        Steps:
            1) Initialize radio drivers if needed.
            2) Open a link via `Crazyflie`, set connection callbacks.
            3) Optionally block until fully connected (parameters downloaded).
            4) Create `SyncCrazyflie` and start the state logger.
            5) Load AI-deck MAC (optional) and initialize flight system.
            6) Optionally start the flight thread.

        Args:
            start_flying: If True and not in test mode, start the commander
                thread after initialization.
            localization_mode: Optional string to configure the estimator
            ("Loco", "Flow", "Optitrack"        Raises:
            CrazyFlieError: On connection failure or lost link.

        Returns:
            None
        """
        # connects to the desired drone
        # initialize driver if wasn't initialized
        if not self._state.get_scanned():
            cflib.crtp.init_drivers()   # initialize the low level drivers
            self._state.set_scanned()
        self._cf = Crazyflie(rw_cache=self.get_path() + sep + "cache")
        # add callbacks to handle connection states
        self._cf.connected.add_callback(self._connected)
        self._cf.fully_connected.add_callback(self._fully_connected)
        self._cf.disconnected.add_callback(self._disconnected)
        self._cf.connection_failed.add_callback(self._connection_failed)
        self._cf.connection_lost.add_callback(self._connection_lost)
        # initialize link
        self._cf.open_link(self._address)
        # wait for parameters to be initialized
        if self._blocking:
            while not self._state.get_ready():
                sleep(0.5)
        # synchronized object initialization (for logging)
        self._scf = SyncCrazyflie(self._address, self._cf)
        # start logging
        self._log_setup()
        # look up the MAC address of the connected AI Deck
        try:
            self._mac = MAC_LOOKUP[self._address]
            self.print("AI deck MAC address: " + self._mac, self.LogLevel.info)
        except KeyError:
            self.print("no associated AI deck was found", self.LogLevel.warning)
            self._mac = "unknown"
        # initialize flying
        if not self._test_mode:
            self.print("initializing flight system...", self.LogLevel.info)
            self._init_flight(localization_mode)
            if start_flying:
                self.print("starting flight thread...", self.LogLevel.info)
                self._start_flying()
        return
    
    def disconnect(self):
        """Stops the flight thread, logging, and close the link.

        The method:
          - Signals exit via internal state.
          - Joins the commander thread (if alive).
          - Stops the log configuration (if active).
          - Closes the radio link.

        Returns:
            None
        """
        # stop flying
        self._state.set_exit()
        try:
            if self._flight_thread.is_alive():
                self._flight_thread.join()
                self._flying = False
        except AttributeError:
            pass
        # stop external position streaming
        try:
            if self.ext_pos_thread.is_alive():
                self.ext_pos_thread.join()
        except AttributeError:
            pass
        # stop logging
        try:
            self._log_config.stop()
        except AttributeError:
            pass
        # close radio link
        try:
            self._cf.close_link()
        except AttributeError:
            pass
        return
    
    """ ---------------------------------------------------------------------------- """

    def set_radio_lock(self, lock:Lock):
        """Register a shared radio lock to serialize radio operations.

        Use this when multiple drones run in parallel to avoid overlapping
        access to parameters/logging through the same radio channel.

        Args:
            lock: A `threading.Lock` instance shared among drones.

        Returns:
            None
        """
        self._radio_lock = lock
        return
    
    def get_radio(self):
        """Acquire the shared radio lock (if configured).

        Blocks up to 10 seconds. If no lock was set, this is a no-op.

        Returns:
            None
        """
        # acquire lock on radio
        try:
            self._radio_lock.acquire(timeout=10)
        except AttributeError:
            pass
        return
    
    def release_radio(self):
        """Release the shared radio lock (if configured).

        Returns:
            None
        """
        # release radio lock
        try:
            self._radio_lock.release()
        except AttributeError:
            pass
        return

    def set_unblocking(self, state:bool):
        """Enable/disable blocking wait for parameters after `open_link()`.

        Args:
            state: If True, do not block; if False, wait until fully ready.

        Returns:
            None
        """
        # set to true to disable blocking after connection until all the parameters are updated
        self._blocking = state
        return

    def set_natnet_monitor(self, monitor:NatNetRigidBodyMonitor):
        self.natnet_monitor = monitor

    def get_natnet_monitor(self) -> NatNetRigidBodyMonitor:
        return self.natnet_monitor
    
    def test_mode(self, state:bool):
        """Enable/disable test mode.

        In test mode the flight initialization is performed but the commander
        thread is not started automatically. Useful for parameter inspection,
        hardware tests, and similar actions without flying.

        Args:
            state: True to enable test mode, False to disable.

        Returns:
            None
        """
        # set to true to disable flight
        self._test_mode = state
        return
    
    def set_update_time(self, time_ms:int):
        """Set the logging update period in milliseconds.

        Args:
            time_ms: Desired update period for state logging.

        Returns:
            None
        """
        # set state update time in ms
        self._update_time = time_ms
        return
    
    def get_connection_state(self) -> str:
        """Report the connection state as a human-readable string.

        Returns:
            One of: "not initialized", "connected", "ready", "disconnected",
            or "unknown".
        """
        # return the connection status
        if self._state.get_not_initialized():
            return "not initialized"
        elif self._state.get_connected():
            return "connected"
        elif self._state.get_ready():
            return "ready"
        elif self._state.get_disconnected():
            return "disconnected"
        return "unknown"
    
    def get_state(self):
        """Get the latest position of the drone.

        Returns:
            State: A copy-like object with x, y, z, roll, pitch, yaw, battery.
        """
        # return the state of the drone
        return deepcopy(self._current_state)
    
    def set_delay(self, time_s:float):
        """Set the delay between commander iterations.

        Args:
            time_s: Sleep duration (seconds) between setpoint updates.

        Returns:
            None
        """
        # set the delay time between destination updates
        self._delay = time_s
        return
    
    def set_directory(self, directory):
        """Set the output directory for position log files.

        Args:
            directory: Filesystem path used by `save_position()`.

        Returns:
            None
        """
        # set the output path
        self._directory = directory
        return
    
    def get_position_count(self) -> int:
        """Get the number of positions saved so far.

        Returns:
            int: The number of saved position entries.
        """
        # return the position counter
        return self._position_counter

    """ ---------------------------------------------------------------------------- """

    def _connected(self, address):
        """Callback: called when a link to the Crazyflie has been established.

        Args:
            address: Link address info from cflib.

        Returns:
            None
        """
        # run when the drone gets connected
        self.print("connected to " + self._name, self.LogLevel.message)
        self._state.set_connected()
        return
    
    def _fully_connected(self, _):
        """Callback: called when parameters are downloaded and link is ready.

        Returns:
            None
        """
        # run when the drone is connected and all parameters have been donwloaded
        self.print(f"Drone {self._name} ready", self.LogLevel.message)
        self._state.set_ready()
        return
    
    def _disconnected(self, _):
        """Callback: called when the Crazyflie has been disconnected.

        Returns:
            None
        """
        # run when the drone gets disconnected
        self._state.set_exit()
        self.print(f"Drone {self._name} disconnected", self.LogLevel.message)
        self._state.set_disconnected()
        return
    
    def _connection_failed(self, _, message):
        """Callback: called when establishing the link failed.

        Args:
            message: Error message from cflib.

        Raises:
            CrazyFlieError: Always raised to signal failure.
        """
        # run when the connection fails
        self._state.set_exit()
        self.print(f"Drone {self._name} failed to connect", self.LogLevel.error)
        self._state.set_disconnected()
        raise CrazyFlieError("failed to connect")
    
    def _connection_lost(self, _, message):
        """Callback: called when the link has been lost.

        Args:
            message: Error message from cflib.

        Raises:
            CrazyFlieError: Always raised to signal loss.
        """
        # run when the connection is lost
        self._state.set_exit()
        self.print(f"Drone {self._name} lost connection ", self.LogLevel.error)
        self._state.set_disconnected()
        raise CrazyFlieError("connection lost")
    
    """ ---------------------------------------------------------------------------- """
    
    def _log_data_save(self, timestamp, data, _):
        """Internal: Update current state with values from the logger.

        Args:
            timestamp: Log timestamp (unused here).
            data: Dictionary containing logged variables:
                - "stateEstimate.x/y/z"
                - "stabilizer.roll/pitch/yaw"
                - "pm.vbat"
            _: Unused argument (logger source).

        Returns:
            None
        """
        # incoming data from the drone
        self._current_state.x = data["stateEstimate.x"]
        self._current_state.y = data["stateEstimate.y"]
        self._current_state.z = data["stateEstimate.z"]
        self._current_state.roll = data["stabilizer.roll"]
        self._current_state.pitch = data["stabilizer.pitch"]
        self._current_state.yaw = data["stabilizer.yaw"]
        self._current_state.battery = data["pm.vbat"]
        self.print(str(self._current_state), self.LogLevel.debug)
        return
    
    def _log_error(self, _, message):
        """Internal: Handle log errors by raising a CrazyFlieError.

        Args:
            _: Unused argument (logger source).
            message: Error message.

        Raises:
            CrazyFlieError: Always raised for logging errors.
        """
        # incoming error from the drone
        self.print(message, self.LogLevel.error)
        raise CrazyFlieError(message)

    def _log_setup(self):
        """Configure and start the periodic state logger.

        Sets up a `LogConfig` with position, attitude and battery voltage, and
        attaches callbacks for data and error handling.

        Raises:
            CrazyFlieError: If a log variable is missing or the logger cannot
                be added.

        Returns:
            None
        """
        # set up logging for the state of the drone
        # add parameters to a configuration
        self._log_config = LogConfig(name="Crazy Flie State Updater", period_in_ms=self._update_time)
        self._log_config.add_variable("stateEstimate.x", "float")
        self._log_config.add_variable("stateEstimate.y", "float")
        self._log_config.add_variable("stateEstimate.z", "float")
        self._log_config.add_variable("stabilizer.roll", "float")
        self._log_config.add_variable("stabilizer.pitch", "float")
        self._log_config.add_variable("stabilizer.yaw", "float")
        self._log_config.add_variable("pm.vbat", "FP16")   # battery level as 16-bit float
        # add callbacks
        try:
            self._cf.log.add_config(self._log_config)   # add configuration
            self._log_config.data_received_cb.add_callback(self._log_data_save)  # function to run when data is incoming
            self._log_config.error_cb.add_callback(self._log_error) # function to run when there is an error
        except KeyError as e:
            self.print("logging error: " + str(e) + " not found", self.LogLevel.error)
            raise CrazyFlieError("logging error: " + str(e) + " not found")
        except AttributeError:
            self.print("logging error", self.LogLevel.error)
            raise CrazyFlieError("logging error")
        self._log_config.start()
        return

    """ ---------------------------------------------------------------------------- """
    def _set(self,name,val):
        try: self._cf.param.set_value(name, val)
        except Exception as e: print(f"[param] {name}={val} failed: {e}")
        
    def select_localization_mode(self, specific=None):
        """
        Select the localization mode based on attached decks or user preference.
        This method checks for the presence of Flow and Loco decks and sets the
        localization mode accordingly.
        Args:
            specific: Optional specific localization mode to activate
                      ("Loco", "Flow", "Optitrack"). If None, automatic mode is used.
        Returns:

            None
            
        """
        #self.checking_decks()  # update deck information
        self.positioning_mode = "Optitrack"
        if specific==None: #automatic mode: take Flow deck if available, else Loco deck
            if self.checking_decks("bcFlow2") or self.checking_decks("bcFlow"):
                #self.print(f"Test flow: {self.checking_decks('bcFlow2')}, {self.checking_decks('bcFlow')}", self.LogLevel.debug)
                self.print("Flow Deck detected, activating Flow localization", self.LogLevel.info)
                self.positioning_mode = "Flow"
            elif self.checking_decks("bcLoco"):
                self.print("Loco Deck detected, activating Loco localization", self.LogLevel.info)
                self.positioning_mode = "Loco"
            else:
                self.print("Activating Optitrack localization", self.LogLevel.warning)
                self.positioning_mode = "Optitrack"

        elif specific=="Loco":
            if self.checking_decks("bcLoco"):
                self.print("Loco Deck detected, activating Loco localization", self.LogLevel.info)
                self.positioning_mode = "Loco"
            else:
                self.print("Loco Deck not detected, cannot activate Loco localization, activating Optitrack", self.LogLevel.error)
                self.positioning_mode = "Optitrack"
        elif specific=="Flow":
            if self.checking_decks("bcFlow2") or self.checking_decks("bcFlow"):
                self.print("Flow Deck detected, activating Flow localization", self.LogLevel.info)
                self.positioning_mode = "Flow"
            else:
                self.print("Flow Deck not detected, cannot activate Flow localization, activating Optitrack", self.LogLevel.error)
                self.positioning_mode = "Optitrack"
        elif specific=="Optitrack":
            self.print("Activating Optitrack localization", self.LogLevel.info)
            self.positioning_mode = "Optitrack"
        else:
            self.print("Unknown localization mode specified, activating Optitrack localization", self.LogLevel.error)
            self.positioning_mode = "Optitrack"
        return
    

    def _activate_localization(self):
        if self.positioning_mode=="Optitrack":
            self.rigid_body_id = RIGID_BODY_ID_LOOKUP[self._address]
            if self.natnet_monitor is None:
                self.print(f"NatNet monitor must be initialized. Cannot activate Optitrack localization for drone {self._name}", self.LogLevel.warning)
            if self.natnet_monitor.is_running() == False:
                try: 
                    self.print(f"Activating NatNet monitor for Optitrack localization{self._name}", self.LogLevel.info)
                    self.natnet_monitor.start()
                except Exception as e:
                    self.print(f"Failed to start NatNet monitor for Optitrack localization for drone {self._name}: {str(e)}", self.LogLevel.error)
                    return -1
            else:
                print(f"NatNet monitor already running for Optitrack localization for drone {self._name}", self.LogLevel.info)
            self.seed_ekf_with_absolute()
            sleep(MOCAP_SETTLE_S)  # wait for mocap to stabilize
            # start external position streaming thread
            self.ext_pos_thread = Thread(target=self.ext_pos_streaming_loop, daemon=True)
            self.ext_pos_thread.start()
            self.print(f"Optitrack localization activated for drone {self._name}", self.LogLevel.info)
        return 0
            
    def seed_ekf_with_absolute(self):
        t0 = time()
        abs_cf = None
        while time() - t0 < TIMEOUT:
            pos_m, _, age_ms = self.natnet_monitor.get_latest(self.rigid_body_id)
            if pos_m is not None and age_ms < MOCAP_FRESH_MS:
                abs_cf = self.natnet_monitor.motive_to_cf_pos(pos_m)  # absolute CF-Koordinaten
                break
            sleep(0.02)

        if abs_cf is None:
            abs_cf = (0.0, 0.0, 0.0)  # Fallback (not ideal)
        # EKF auf absolute Welt setzen
        self._set("stabilizer.estimator", 2)   # EKF
        self._set("kalman.initialX", abs_cf[0])
        self._set("kalman.initialY", abs_cf[1])
        self._set("kalman.initialZ", abs_cf[2])
        self._set("kalman.resetEstimation", 1)
        sleep(0.1)
        self._set("kalman.resetEstimation", 0)

        # increase external position trust
        self._set("locSrv.extPosStdDev", 0.002)  # ~2 mm, needs to be adjusted to quality of mocap
        print(f"[EKF] Seeded to absolute world at {abs_cf}")

    def ext_pos_streaming_loop(self):
        """ Continuously stream external position data to the Crazyflie EKF.
        This method should be run in a separate thread.
        """
        while not self._state.get_exit():
            pos_m, _, age_ms = self.natnet_monitor.get_latest(self.rigid_body_id)
            if pos_m is not None and age_ms < MOCAP_FRESH_MS:
                x_cf, y_cf, z_cf = self.natnet_monitor.motive_to_cf_pos(pos_m)  # absolute CF-Koordinaten
                # Stream external position to Crazyflie
                with self._lock:
                    self._cf.extpos.send_extpos(x_cf, y_cf, z_cf)
            sleep(1.0/MOCAP_TX_RATE_HZ) 
            
    def _init_flight(self, localization_mode=None):
        """Initialize flight stack (controller/estimator) and get start pose.

        Actions:
            - Set estimator/controller (EKF + PID by default).
            - Set localization mode (Flow, Loco, Optitrack).
            - activate localization stream for optitrack if needed
            - Reset the Kalman filter and wait for variance stabilization.
            - Average a few samples to obtain an initial pose.
            - Prepare the commander thread but do not start it.

        Notes:
            The method assumes that external position data will be available
            to the estimator shortly after reset.

        Returns:
            None
        """
        # initialize flying
        # set controller and estimator
        self.get_radio()
        self._scf.cf.param.set_value("stabilizer.estimator", 2) # 0-auto, 1-complementary, 2-ekf, 3-ukf
        self._scf.cf.param.set_value("stabilizer.controller", 1)    # 0-auto, 1-PID, 2-Mellinger, 3-INDI, 4-Brescianini, 5-OOT
        # Mellinger for maneuvers, INDI against windup, Berscianini against disturbances
        # set localization mode
        self.print("selecting localization mode...", self.LogLevel.info)
        self.select_localization_mode(localization_mode)
        self._activate_localization()
        # reset the position estimator
        self._scf.cf.param.set_value("kalman.resetEstimation", "1")
        sleep(0.1)
        self._scf.cf.param.set_value("kalman.resetEstimation", "0")
        self.release_radio()
        try:
            self._wait_estimator()
        except KeyboardInterrupt:
            self.print("flight initialization aborted", self.LogLevel.critical)
            return
        # average positions to get the starting point
        average = 10
        for _ in range(average):
            self._initial_position.x = self._initial_position.x + self._current_state.x
            self._initial_position.y = self._initial_position.y + self._current_state.y
            self._initial_position.z = self._initial_position.z + self._current_state.z
            self._initial_position.yaw = self._initial_position.yaw + self._current_state.yaw
            self._initial_position.roll = self._initial_position.roll + self._current_state.roll
            self._initial_position.pitch = self._initial_position.pitch + self._current_state.pitch
            self._initial_position.battery = self._current_state.battery
            sleep(0.1)
        self._initial_position.x = self._initial_position.x / average
        self._initial_position.y = self._initial_position.y / average
        self._initial_position.z = self._initial_position.z / average
        self._initial_position.yaw = self._initial_position.yaw / average
        self._initial_position.roll = self._initial_position.roll / average
        self._initial_position.pitch = self._initial_position.pitch / average
        self._next_position = self._initial_position
        self._next_position.set_z(0.5)
        self.print("initial " + str(self._initial_position), self.LogLevel.debug)
        # start a thread for the flight controller
        self._flight_thread = Thread(target=self._flight_commander, daemon=False, name="commander " + self._address)
        return
    
    def _start_flying(self):
        """Start the commander thread if not already running.
        Args:
            None
            
        Returns:
            None
        """
        # start the flight commander thread
        if not self._flying:
            self._flight_thread.start()
            self._flying = True
        return
    
    def checking_decks(self, specific=None):
        """
        Check and print all detected decks attached to the Crazyflie.

        This method iterates through the parameter table of the connected Crazyflie
        and checks for all groups starting with 'deck'. Each deck parameter indicates
        whether a specific deck (e.g., Flow Deck, Loco Deck, AI-deck) is detected
        or not. A value of 1 means the deck is detected, while 0 means it is not.

        The method prints the results both via the internal logger and to the console.

        Args:
            specific: Optional specific deck to check (ex. specific = bcFlow2)
        Example:
            deck.bcFlow2 = 1
            deck.bcLoco = 0
            deck.bcAiDeck = 1

        Returns:
            None
        """
        if specific is None:
            found = False
            for group in self._scf.cf.param.toc.toc.keys():
                if group.startswith('deck'):
                    for param in self._scf.cf.param.toc.toc[group]:
                        val = self._scf.cf.param.get_value(f'{group}.{param}')
                        self.print(f'Detected deck: {param} {val}', self.LogLevel.info)
                        print(f'{group}.{param} = {val}')
                        found = True
            if not found:
                self.print("No deck parameters found", self.LogLevel.warning)
            return  # kein spezieller Wert – reine Auflistung
        else:
            try:
                val = self._scf.cf.param.get_value(f'deck.{specific}')
            except ValueError:
                self.print(f'Deck parameter {specific} not found in group, self.LogLevel.error)')
                print(f'deck.{specific} not found')
                return 0
            self.print(f'Deck {specific}, value: {val}', self.LogLevel.info)
            #print(f'deck.{specific} = {val}')
            #print(type(val))
            if val == 0:
                
                return False


    def read_parameters(self, read_all=False):
        """Read a small set of useful Crazyflie parameters.
        Args:
            read_all: If True, list all available parameters (for debugging).
        Parameters include:
            - Loco Positioning: 'loco.mode', 'locSrv.enRangeStreamFP32'
            - Kalman robustness flags: 'kalman.robustTdoa', 'kalman.robustTwr'
            - Stabilizer: 'stabilizer.controller', 'stabilizer.estimator',
                          'stabilizer.stop'

        Returns:
            dict: Mapping from parameter name to current value (strings).
                  If a read fails, the entry may be missing and a warning is
                  logged.
        """
        param_names = [
            # Loco Positioning
            "loco.mode",
            'locSrv.enRangeStreamFP32',
            'kalman.robustTdoa',
            'kalman.robustTwr',
            
            'stabilizer.controller',
            'stabilizer.estimator' , 
            'stabilizer.stop'
            
        ]
        
        # list all available parameters
        if read_all:
            self.print("reading all available parameters:", self.LogLevel.info)
            available_params = self._scf.cf.param.toc.toc  # = list of strings like "group.name"
            for name in available_params:
                self.print(f"{name}, type {type(name)}", self.LogLevel.info)


        parameters = {}
        for name in param_names:
            try:
                value = self._scf.cf.param.get_value(name)
                parameters[name] = value
            except Exception as e:
                self.print(f"Error reading parameter '{name}': {e}", self.LogLevel.warning)

        return parameters
    
    def _flight_commander(self):
        """Commander thread body: send setpoints, check battery, and land to drone.

        Behavior:
            - While `self._state.get_ready()` is True, the thread:
                * Checks battery against `LOW_BATTERY` and exits to land if low.
                * If landing is requested (`_next_position.grounded`), lands.
                * Otherwise, sends the latest position setpoint with a yaw
                  step limit (±45°/iteration) to avoid large jumps.
                * Sleeps `self._delay` between iterations.
            - On exit, executes a landing sequence and sends stop setpoints.

        Safety:
            - The landing sequence sends a zero-altitude position setpoint at
              the last known XY and waits a few seconds before issuing stop
              commands.

        Returns:
            None
        """
        try:
            while self._state.get_ready():
                # check battery state
                if self._current_state.battery <= LOW_BATTERY:
                    self.print(f"Drone {self._name}: battery level: " + str(self._current_state.battery) + "V", self.LogLevel.debug)
                    self.print(f"Drone {self._name}: battery level critical", self.LogLevel.warning)
                    break
                else:
                    # check if landing is required
                    if self._next_position.grounded == True:
                        self.print(f"Drone {self._name} landing requested", self.LogLevel.debug)
                        break
                    else:
                        # set setpoint
                        with self._lock:
                            coordinates = deepcopy(self._next_position)
                        angle_diff = self._angle_diff(coordinates.yaw,self._current_state.yaw)
                        #self.print(f"angle diff: {angle_diff}", self.LogLevel.debug)
                        # check against the maximum allowed rotation
                        if abs(angle_diff) > 45:
                            #self.print(f"angle diff {angle_diff} too large, limiting to 45 degrees", self.LogLevel.debug)
                            coordinates.yaw = self._current_state.yaw + 45 * (1 if angle_diff > 0 else -1)
                            self.print(f"error in position measurement, new yaw correction: input: {coordinates.yaw}, current pos {self._current_state.yaw}", self.LogLevel.debug)
                        self.print(f"Sending setpoint to {self._name}: [{coordinates.x},{coordinates.y},{coordinates.z},{coordinates.yaw}]", level=LogLevel.debug)
                        self._scf.cf.commander.send_position_setpoint(coordinates.x, coordinates.y, coordinates.z, coordinates.yaw)
                # delay to let time for other threads
                sleep(self._delay)
            # land
            self.print(f"Drone {self._name} landing", self.LogLevel.info)
            with self._lock:
                if not isinstance(self._landing_position, State):
                    self._landing_position = self._current_state
                    self._landing_position.z = 0
            self._scf.cf.commander.send_position_setpoint(self._landing_position.x, self._landing_position.y, self._landing_position.z, self._landing_position.yaw)
            sleep(3)
            self.print("landing succeeded", self.LogLevel.debug)
        except KeyboardInterrupt:
            pass
        self.print("stopping motors", self.LogLevel.debug)
        self._scf.cf.commander.send_stop_setpoint()
        self._scf.cf.commander.send_notify_setpoint_stop()
        return
    
    def _angle_diff(self, target, current):
        """Return the minimal signed angular difference (target - current) in degrees.

        Range: (-180, 180]
        """
        diff = (target - current + 180) % 360 - 180
        return diff
    
    def _wait_estimator(self):
        """Wait for the Kalman filter variances to stabilize.

        Opens a temporary `SyncLogger` for `kalman.varP{X,Y,Z}` and checks the
        sliding window range until it drops below a small threshold, indicating
        convergence.

        Raises:
            KeyboardInterrupt: If interrupted by the user.

        Returns:
            None
        """
        # wait until the current position is determined
        try:
            self.print(f"Drone {self._name} waiting for estimator to find position...", self.LogLevel.message)
            log_config = LogConfig(name="Estimator Monitoring", period_in_ms=100)
            log_config.add_variable("kalman.varPX", "float")
            log_config.add_variable("kalman.varPY", "float")
            log_config.add_variable("kalman.varPZ", "float")
            var_y_history = [1000] * 10
            var_x_history = [1000] * 10
            var_z_history = [1000] * 10
            threshold = 0.001
            timeout = 20  # seconds
            elapsed = 0.0
            self.get_radio()
            with SyncLogger(self._scf, log_config) as logger:
                for log_entry in logger:
                    sleep(0.1); elapsed += 0.1
                    data = log_entry[1]
                    var_x_history.append(data["kalman.varPX"])
                    var_x_history.pop(0)
                    var_y_history.append(data["kalman.varPY"])
                    var_y_history.pop(0)
                    var_z_history.append(data["kalman.varPZ"])
                    var_z_history.pop(0)
                    min_x = min(var_x_history)
                    max_x = max(var_x_history)
                    min_y = min(var_y_history)
                    max_y = max(var_y_history)
                    min_z = min(var_z_history)
                    max_z = max(var_z_history)
                    if (max_x - min_x) < threshold and (max_y - min_y) < threshold and (max_z - min_z) < threshold:
                        break
                    if elapsed >= timeout:
                        self.print(f"Drone {self._name} estimator timeout after {timeout} seconds", self.LogLevel.warning)
                        break
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        finally:
            try:
                self.print(f"Drone {self._name} calibration finished", self.LogLevel.message)
                self.release_radio()
            except RuntimeError:
                pass
        return
    
    def arrived(self, position:State, fine:bool=True):
        """Check whether the drone has arrived at the desired pose.

        The method compares the absolute differences in x, y, z and the minimal
        yaw angle difference. For distance, it currently uses the maximum of
        axis-wise absolute errors; angle is the absolute yaw difference.

        Args:
            position: Target `State` (x, y, z, yaw). Other fields are ignored.
            fine: If True, use strict arrival thresholds; otherwise use relaxed
                thresholds.

        Returns:
            bool: True if within thresholds, False otherwise.
        """
        # return true if the drone arrived to the given position
        # check current distance
        try:
            difference = State()
            difference.x = abs(position.x - self._current_state.x)
            difference.y = abs(position.y - self._current_state.y)
            difference.z = abs(position.z - self._current_state.z)
            difference.yaw = abs(self._angle_diff(position.yaw, self._current_state.yaw))   #case target 180 , state -176 =
            if difference.yaw > 45:
                self.print("target " + str(position), self.LogLevel.debug)
                self.print("current " + str(self._current_state), self.LogLevel.debug)
            #self.print("difference: " + str(difference), self.LogLevel.debug)
            # find largest deviations
            distance = max(difference.x, difference.y, difference.z)
            angle = difference.yaw
            # compare deviations to thresholds (in meters for distance and degrees for angle)
            if fine:
                if (distance <= ARRIVAL_THRESHOLD_DISTANCE) and (angle <= ARRIVAL_THRESHOLD_ANGLE):
                    self.print("position reached", self.LogLevel.info)
                    return True
            else:
                if (distance <= ARRIVAL_THRESHOLD_DISTANCE_ROUGH) and (angle <= ARRIVAL_THRESHOLD_ANGLE_ROUGH):
                    self.print("position reached", self.LogLevel.info)
                    return True
        except TypeError:
            pass
        self.print(f"Drone {self._name} didn't reach the destination", self.LogLevel.info)
        return False    # didn't arrive
    
    def _valid_pose(self, s: State) -> bool:
        try:
            vals = [s.x, s.y, s.z, s.yaw]
            return all(v is not None for v in vals)
        except Exception:
            return False
        
    def fly(self, position:State):
        """Update the next setpoint to fly towards.

        Thread-safe: acquires the internal lock to update `_next_position`.

        Args:
            position: Desired target `State`. Only x, y, z, yaw are used.
                Set `position.grounded=False` to fly (default in `State`).

        Raises:
            CrazyFlieError: If the argument is not a `State`.

        Returns:
            None
        """
        # go to position
        if not isinstance(position, State) or not self._valid_pose(position):
            self.print("invalid position format", self.LogLevel.error)
            raise CrazyFlieError("invalid position format")
        with self._lock:
            self._next_position = position
        return

    def land(self, position:State=None):
        """Request a landing sequence.

        If a `position` is provided, the drone will attempt to land at that
        pose (x, y, z=0, yaw). Otherwise it lands at the current position.

        Args:
            position: Optional `State` defining a landing target.

        Returns:
            None
        """
        # land the drone
        if isinstance(position, State):
            with self._lock:
                self._landing_position = position
        else:
            self.print("landing to the current position", self.LogLevel.warning)
        with self._lock:
            self._next_position.grounded = True
        return
    
    def motors_off(self):
        """Attempt to stop the motors immediately (emergency stop).

        Note:
            Setting `stabilizer.stop=1` requests the stabilizer to stop.
            Consider also sending stop setpoints (see `_flight_commander()`)
            to make sure the commander is not holding non-zero thrust.

        Returns:
            None
        """
        # stop the motors. did not work, deeper insight required
        
        with self._lock:
            try:
                self._scf.cf.param.set_value("stabilizer.stop", "1")
            except Exception:
                pass
            try:
                self._scf.cf.commander.send_stop_setpoint()
                self._scf.cf.commander.send_notify_setpoint_stop()
            except Exception:
                pass
    
    """ ---------------------------------------------------------------------------- """
    
    def get_position(self, average_count, average_time_s):
        """Return a simple averaging of the current state over a time window.

        This non-synchronous approach reads from the last cached state values
        and averages them over `average_count` samples, sleeping between samples
        so that the total duration is approximately `average_time_s`.

        Args:
            average_count: Number of samples to average.
            average_time_s: Total averaging time in seconds.

        Returns:
            State: Averaged state (x, y, z, roll, pitch, yaw, battery).
        """
        # return the current position averaged during the required time
        this_position = State()
        rest_time = average_time_s / average_count
        for _ in range(average_count):
            this_position.x = this_position.x + self._current_state.x
            this_position.y = this_position.y + self._current_state.y
            this_position.z = this_position.z + self._current_state.z
            this_position.roll = this_position.roll + self._current_state.roll
            this_position.pitch = this_position.pitch + self._current_state.pitch
            this_position.yaw = this_position.yaw + self._current_state.yaw
            this_position.battery = this_position.battery + self._current_state.battery
            sleep(rest_time)
        this_position.x = this_position.x / average_count
        this_position.y = this_position.y / average_count
        this_position.z = this_position.z / average_count
        this_position.roll = this_position.roll / average_count
        this_position.pitch = this_position.pitch / average_count
        this_position.yaw = this_position.yaw / average_count
        this_position.battery = this_position.battery / average_count
        return this_position
    
    def _get_position_sync(self, average_count, average_time_s):
        """Synchronously read and average state using a temporary logger.

        Opens a dedicated `SyncLogger` with the same variables as the main
        state logger and averages `average_count` samples spaced by
        `average_time_s / average_count`.

        Args:
            average_count: Number of samples to collect.
            average_time_s: Total averaging time (seconds).

        Returns:
            State: Averaged state from synchronous logs.
        """
        # return the current position averaged during the required time
        self.print(f"Drone {self._name} reading starting position", self.LogLevel.message)
        this_position = State()
        rest_time = (average_time_s / average_count) * 1000
        log_config = LogConfig(name="Starting Position Reader", period_in_ms=rest_time)
        log_config.add_variable("stateEstimate.x", "float")
        log_config.add_variable("stateEstimate.y", "float")
        log_config.add_variable("stateEstimate.z", "float")
        log_config.add_variable("stabilizer.roll", "float")
        log_config.add_variable("stabilizer.pitch", "float")
        log_config.add_variable("stabilizer.yaw", "float")
        log_config.add_variable("pm.vbat", "FP16")   # battery level as 16-bit float
        count = 0
        self.get_radio()
        with SyncLogger(self._scf, log_config) as logger:
            for log_entry in logger:
                sleep(0.01)
                data = log_entry[1]
                this_position.set_x(this_position.get_x() + data["stateEstimate.x"])
                this_position.set_y(this_position.get_y() + data["stateEstimate.y"])
                this_position.set_z(this_position.get_z() + data["stateEstimate.z"])
                this_position.set_roll(this_position.get_roll() + data["stabilizer.roll"])
                this_position.set_pitch(this_position.get_pitch() + data["stabilizer.pitch"])
                this_position.set_yaw(this_position.get_yaw() + data["stabilizer.yaw"])
                this_position.set_battery(this_position.get_battery() + data["pm.vbat"])
                count = count + 1
                if count >= average_count:
                    break
        self.release_radio()
        this_position.set_x(this_position.get_x() / average_count)
        this_position.set_y(this_position.get_y() / average_count)
        this_position.set_z(this_position.get_z() / average_count)
        this_position.set_roll(this_position.get_roll() / average_count)
        this_position.set_pitch(this_position.get_pitch() / average_count)
        this_position.set_yaw(this_position.get_yaw() / average_count)
        this_position.set_battery(this_position.get_battery() / average_count)
        self.print("starting " + str(this_position), self.LogLevel.debug)
        return this_position
    
    def save_position(self, position:State):
        """Persist a measured/averaged position to disk.

        File layout:
            <directory>/<MAC>/<N>.txt

        Where:
            - `<directory>` is set via `set_directory()`.
            - `<MAC>` resolves from `MAC_LOOKUP` if available (else "unknown").
            - `<N>` is an incrementing integer.

        Args:
            position: The `State` to write.

        Returns:
            None
        """
        # save a position coming from this drone
        self.print("saving position", self.LogLevel.info)
        self._check_path(self._directory + sep + str(self._mac))
        file = open(self._directory + sep + str(self._mac) + "_" + str(self._position_counter) + ".txt", "w")
        file.write(str(position))
        file.close()
        self._position_counter = self._position_counter + 1
        return
    
    """ ---------------------------------------------------------------------------- """
    
    def test_fans(self):
        """Run the propeller self-test (no lift; on the ground).

        Behavior:
            - Switch to test mode (if not already).
            - Connect if needed.
            - Trigger `health.startPropTest`.
            - Wait for the test to complete (approx. 6 seconds).

        Returns:
            None
        """
        # propeller test
        # connect in test mode
        self.test_mode(True)
        if self._state.get_not_initialized():
            self.connect()
        self.print("testing propellers", self.LogLevel.message)
        # start test
        self._scf.cf.param.set_value("health.startPropTest", "1")
        # wait until the test finishes
        while self._state.get_ready():
            if self._scf.cf.param.get_value("health.startPropTest") == "0":
                # this parameter will be 0 exactly after the test has started
                break
            sleep(1)
        sleep(6)    # wait some time for the test to finish
        return

    def charge_state(self, parallel:bool=False):
        """Monitor charge state when the Crazyflie is connected to a charger.

        The function logs current (`pm.chargeCurrent`) and cell voltage
        (`pm.vbat`), prints progress, and stops when voltage is high and current
        has tapered below a fraction of `RATED_CURRENT`.

        Args:
            parallel: If True, check once and return (used for multi-CF loops).

        Returns:
            None
        """
        # check the state of the battery when plugged to a charger
        # connect in test mode
        threshold = 0.03 * RATED_CURRENT    # charge current in A
        maximum = -1.0
        self.test_mode(True)
        if self._state.get_not_initialized():
            self.connect()
        # set up a logger to monitor the cell voltage and the charge current
        self.print(f"checking charge status of {self._address}", self.LogLevel.message)
        log_config = LogConfig(name="Crazy Flie Charger Monitor", period_in_ms=1000)
        log_config.add_variable("pm.chargeCurrent", "float")
        log_config.add_variable("pm.vbat", "float")
        with SyncLogger(self._scf, log_config) as logger:
            try:
                for log_entry in logger:
                    # get logger data
                    data = log_entry[1]
                    current = data["pm.chargeCurrent"]
                    voltage = data["pm.vbat"]
                    self.print("charge current: " + str(current), self.LogLevel.debug)
                    self.print("cell voltage: " + str(voltage), self.LogLevel.debug)
                    # if the cell voltage is high and the charger current dropped, the cell is charged
                    if (current <= threshold) and (voltage > 4):
                        if self._logging:
                            self.print(f"battery charged {self._address}", self.LogLevel.message)
                        break
                    else:
                        if voltage < 4.2:
                            # constant current charge
                            charge = self._map(2.8, 4.2, 0, 37, voltage)
                        else:
                            # saturation charge
                            charge = self._map(0.25, threshold, 37, 100, current, inverse_exponential=True)
                        if self._logging:
                            if maximum < charge:
                                maximum = charge
                            self.progress_bar(maximum, 100)
                    if parallel: #for parallel charging requests
                        break
                    if not self._state.get_ready():
                        break
                    sleep(1)
            except KeyboardInterrupt:
                if maximum > 0:
                    self.print(" " * 100, self.LogLevel.message)   # hide the progress bar
                raise KeyboardInterrupt
        return
    
    
    def _on_press(self,key):
        if key == keyboard.Key.ctrl:
            self.keyboard_listener.ctrl_pressed = True
        elif key == keyboard.Key.alt:
            self.keyboard_listener.alt_pressed = True
        try:
            #print(f'Key {key.char} pressed')
            pass
        except AttributeError:
            #print(f'Special key {key} pressed')
            pass
        self.keyboard_listener._enabling_control_mode()
        if (self.keyboard_listener.control_mode):
            try:
                if key.char == 'q':
                    self.print("Emergency stop via Keyboard 'q'", self.LogLevel.warning)
                    self.motors_off()
                if key.char == 'l':
                    self.print("Landing via Keyboard 'l'", self.LogLevel.warning)
                    self.land()
            except AttributeError:
                pass
            return
           

    def _on_release(self,key):
        if key == keyboard.Key.ctrl:
            self.keyboard_listener.ctrl_pressed = False
        elif key == keyboard.Key.alt:
            self.keyboard_listener.alt_pressed = False
        self.keyboard_listener._disabling_control_mode()
        
        #print(f'Key {key} released')
        if key == keyboard.Key.esc:
            self.keyboard_listener.listener.stop()
            self.keyboard_listener._running = False
            return False  # Stop listener





""" ---------------------------------------------------------------------------- """

def worker(flag:Flag, counter:Counter, lock:ProcessLock, thread_lock:Lock, position:State, status:State, delay, address, directory:str, average_count=10, log_enable=True, log_file=True, log_level=LogLevel.message, localization_mode=None, natnet_monitor=None):
    """Orchestrate a single Crazyflie in a separate process/thread loop.

    The `worker` function encapsulates the full lifecycle for one drone:
      1) Create the controller, configure logging/output, and connect.
      2) Read and print key parameters for diagnostics.
      3) Measure an initial averaged position and publish it to `status`.
      4) Wait for a global start signal via `flag`.
      5) Start the commander thread.
      6) In a loop:
           - Wait for updated position or exit.
           - Copy the target into a local `State`.
           - Set the appropriate flag (positioning vs. no-save).
           - Issue `fly()` or `land()` based on the target.
           - Block until `arrived(...)`.
           - Signal arrival; optionally wait for an external image save signal.
           - Save the current averaged position and increment `counter`.
           - Repeat until `flag.get_exit()` is set.

    Concurrency Protocol (Flags):
        * `flag.set_connected()` — Signals "I'm ready and waiting".
        * Clearing `get_connected()` — Signals "start flying now".
        * `set_positioning()` / `set_positioning_no_save()` — Indicates whether
          the next target should result in a logged/saved position.
        * `set_on_position()` / `_no_save()` — Signals "arrived at target".
        * `set_position_saved()` — Signals "position saved to disk".
        * `get_image_saved()` — External signal that an image has been saved.

    Shared Objects:
        - `status` (State): Continuously updated with the CF's current state.
        - `counter` (Counter): Updated with the number of saved positions.

    Args:
        flag: Shared `Flag` for cross-process coordination.
        counter: Shared `Counter` for position numbering/progress.
        lock: `multiprocessing.synchronize.Lock` protecting shared `status` and
            counter updates.
        thread_lock: `threading.Lock` for serializing radio operations across
            multiple Crazyflies in the same process.
        position: Shared `State` where the next target pose is written by the
            coordinator.
        status: Shared `State` to publish current/averaged drone state.
        delay: Commander loop sleep duration (seconds).
        address: Crazyflie URI to use for connection.
        directory: Output directory for saved positions/logs.
        average_count: Number of samples for averaging positions.
        log_enable: Enable/disable logging.
        log_file: If True, log to file as well as console.
        log_level: Logging level (see `LogLevel`).

    Raises:
        CrazyFlieError: Propagated errors from the controller where applicable.
        KeyboardInterrupt: If interrupted.

    Returns:
        None
    """
    # create a CrazyFlie instance and send it to positions
    drone = CrazyFlie(address)  # initialize object
    drone.logging(log_enable, log_file, log_level, drone.get_path() + sep + "logs" + sep + directory.split(sep)[-1])  # set up logging
    drone.set_directory(directory)  # set output path
    drone.set_delay(delay)  # set update delay
    drone.set_radio_lock(thread_lock)   # synchronize radio
    drone.set_natnet_monitor(natnet_monitor)  # set NatNet monitor
    drone.connect(start_flying=False, localization_mode=localization_mode) # open link
    sleep(3)
    parameters = drone.read_parameters()
    for name, value in parameters.items():
        drone.print(f"Drone {drone._name}: {name} = {value}", level=drone.LogLevel.debug)# save position
    
    drone.print(f"Drone {drone._name} measuring initial position", drone.LogLevel.info)
    lock.acquire()
    starting_position = drone._get_position_sync(average_count, delay * average_count)
    status.set_x(starting_position.get_x())
    status.set_y(starting_position.get_y())
    status.set_z(starting_position.get_z())
    status.set_yaw(starting_position.get_yaw())
    status.set_pitch(starting_position.get_pitch())
    status.set_roll(starting_position.get_roll())
    status.set_battery(starting_position.get_battery())
    status.set_grounded(starting_position.get_grounded())
    lock.release()
    # wait for all drones
    flag.set_connected()
    drone.print("waiting for start signal", drone.LogLevel.info)
    while flag.get_connected():
        sleep(0.5)
    drone.print("start flying", drone.LogLevel.info)
    drone._start_flying()   # initialize flying
    try:
        while True:
            # exit if required
            if flag.get_exit():
                drone.print("disconnecting", drone.LogLevel.info)
                drone.disconnect()
                break            
            # wait for the position to be updated
            drone.print("wait for new coordinates", drone.LogLevel.info)
            while (not (flag.get_position_updated() or flag.get_position_updated_no_save())) and (not flag.get_exit()):
                # get current position
                lock.acquire()
                status.set_x(drone.get_state().get_x())
                status.set_y(drone.get_state().get_y())
                status.set_z(drone.get_state().get_z())
                status.set_yaw(drone.get_state().get_yaw())
                status.set_pitch(drone.get_state().get_pitch())
                status.set_roll(drone.get_state().get_roll())
                status.set_battery(drone.get_state().get_battery())
                status.set_grounded(drone.get_state().get_grounded())
                lock.release()
                sleep(delay)
            # get position
            drone.print("new coordinates received", drone.LogLevel.info)
            lock.acquire()
            drone.print("flying to new position", drone.LogLevel.info)
            current_position = State()
            current_position.set_x(position.get_x())
            current_position.set_y(position.get_y())
            current_position.set_z(position.get_z())
            current_position.set_yaw(position.get_yaw())
            current_position.set_pitch(position.get_pitch())
            current_position.set_roll(position.get_roll())
            current_position.set_battery(position.get_battery())
            current_position.set_grounded(position.get_grounded())
            # set state
            if not flag.get_exit():
                if flag.get_position_updated():
                    flag.set_positioning()
                else:
                    flag.set_positioning_no_save()
            lock.release()
            # fly to position or land
            if current_position.grounded:
                if (current_position.x == None) or (current_position.y == None) or (current_position.z == None) or (current_position.yaw == None):
                    drone.land()
                else:
                    drone.land(current_position)
            else:
                drone.fly(current_position)
            # wait until the drone arrives
            drone.print("waiting for arrival", drone.LogLevel.info)
            while (not drone.arrived(current_position, fine=flag.get_positioning())) and (not flag.get_exit()):
                sleep(delay)
            # set flags
            drone.print(drone._address + " arrived", drone.LogLevel.message)
            lock.acquire()
            drone.print("signal arrival", drone.LogLevel.info)
            if not flag.get_exit():
                if flag.get_positioning():
                    flag.set_on_position()
                else:
                    flag.set_on_position_no_save()
            lock.release()
            if flag.get_on_position_no_save():
                drone.print("no saving required, skipping to next iteration", drone.LogLevel.info)
                continue
            # wait until the image is saved
            drone.print("waiting for image", drone.LogLevel.info)
            while (not flag.get_image_saved()) and (not flag.get_exit()):
                sleep(delay)
            # save position
            if flag.get_image_saved():
                drone.print("image received, saving position", drone.LogLevel.info)
                drone.save_position(drone.get_position(average_count, delay * average_count))
                # set flags
                lock.acquire()
                counter.set(drone.get_position_count())
                if not flag.get_exit():
                    flag.set_position_saved()
                drone.print("position saved", drone.LogLevel.info)
                lock.release()
            # give time for other threads
            sleep(delay)
    except (CrazyFlieError, KeyboardInterrupt):
        drone.print("disconnecting", drone.LogLevel.info)
        drone.disconnect()   # shut down
    return

