"""
    Receive and store images from a Bitcraze AI Deck.

    The script connects to a single AI Deck that shares the same Wi-Fi network as the host.
    Received images are saved under ./datasets, indexed by the deck’s MAC address and the image number.
    To conserve disk space, each new image overwrites the previous one.

    Workflow:
        1. Connect to or configure the specified Wi-Fi network.
        2. Discover connected AI Deck devices by scanning MAC and IP pairs.
        3. Establish a TCP socket connection to the AI Deck.
        4. Continuously receive image data from the deck.
        5. Optionally display and/or save the received images.

    Authors:
        Veres-Vitalyos Almos (veresvalmos@gmail.com)
        Daniel Bugelnig (daniel.bugelnig@aau.at)

    Date:
        2025
"""


import struct, socket, numpy, cv2, time, threading
from multiprocessing.synchronize import Lock as ProcessLock   # hint lock type
from os import sep  # file paths
import os
import subprocess
from numpy.typing import NDArray

from ..constants import MAC_LOOKUP, WIFI_SOCKET_PORT, WIFI_NAME, WIFI_PASSWORD, OP_SYSTEM
from ..core.base_utils import BaseClass, LogLevel
from ..core.shared_data import Flag, Counter

class AIDeckError(Exception):
    def __init__(self, message=""):
        # AI Deck Error
        super().__init__(message)
        return
    
class _ImageType:
    """Internal helper class for storing image data and usage flags."""
    def __init__(self):
        self.data:NDArray[numpy.uint8] = None
        self.used = False
        return

class AI_Deck(BaseClass):
    """Interface class for connecting to and receiving images from a Bitcraze AI Deck."""
    # base class to control a Bitcraze AI deck

    def __init__(self, ip="", mac=""):
        """Initialize the AI Deck controller.

        Args:
            ip (str): IP address of the AI Deck.
            mac (str): MAC address of the AI Deck.
        """
        # initialize variables
        super().__init__()
        # identifiers
        self._ip = ip
        self._mac = mac
        # internal use
        self._image_counter = 0
        self._last_image = _ImageType()
        # user settable
        self._display = True
        self._directory = self.get_path()
        self._delay = 0.1
        # communication
        self._socket:socket.socket = None
        # parallel execution
        self._thread:threading.Thread = None
        self._thread_lock = threading.Lock()
        return
    
    def logging(self, enable, file, level, directory:str=None):
        # set up logging
        """Configure logging for the AI Deck instance.

        Args:
            enable (bool): Enable or disable logging.
            file (bool): Enable or disable log file output.
            level (LogLevel): Logging verbosity level.
            directory (str, optional): Directory for storing logs.
        """
        super().logging(enable=enable, file=file, level=level, name="AI_Deck_" + self._mac, directory=directory)
        return
    
    def scan(self):
        """Scan for available AI Decks on the network.

        Raises:
            AIDeckError: If no AI Deck can be found or connected.
        """
        # connect to Wi-Fi
        if not self._check_wifi(retries=1):
            self._set_wifi()
            self._connect_wifi()
            if not self._check_wifi():
                self.print("unable to scan for AI decks", self.LogLevel.error)
                raise AIDeckError("unable to scan for AI decks")
        # return the first ip-mac pair
        hostname = socket.gethostname()
        networks = socket.gethostbyname_ex(hostname)[2]
        self.print("networks found: " + str(networks), self.LogLevel.debug)
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
                    self._ip = ip
                    self._mac = mac
                else:
                    # MAC address not registered
                    continue
            except IndexError:
                # this line doesn't contain AI decks
                continue
        if self._mac == "":
            self.print("no AI decks were found", self.LogLevel.error)
            raise AIDeckError("no AI decks were found")
        self.print("AI deck found: " + self._mac + " at " + self._ip, self.LogLevel.message)
        return
    
    def connect(self):
        """Establish a TCP connection with the AI Deck and start image reception.

        Raises:
            AIDeckError: If connection fails or times out.
        """
        # connect to the AI deck
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._socket.connect((self._ip, WIFI_SOCKET_PORT))
            self._socket.settimeout(0.5)  # 0.5 second timeout to be responsive without blocking too long
            self._state.set_connected()
            self._thread = threading.Thread(target=self._image_fetcher, daemon=False, name="image fetching " + self._mac)
            self._thread.start()
        except (ConnectionRefusedError, TimeoutError):
            self.print("couldn't connect to " + self._mac, self.LogLevel.warning)
            raise AIDeckError("couldn't connect to " + self._mac)
        if self._logging:
            self.print("connected client: " + self._mac + " on " + self._ip, self.LogLevel.message)
        return
    
    def disconnect(self):
        """Disconnect from the AI Deck and terminate background threads."""
        # close the existing connection
        self.print("disconnecting from client: " + self._mac, self.LogLevel.message)
        if self._state.get_connected():
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
            self._state.set_exit()
            #self.deactivate_hotspot()
        try:
            self._thread.join()
        except AttributeError:
            pass
        return
    
    """ ---------------------------------------------------------------------------- """
    
    def set_display(self, display:bool):
        """Enable or disable OpenCV image display."""
        # display images or not
        self._display = display
        return
    
    def get_image_count(self):
        # return the current image index
        return self._image_counter
    
    def set_directory(self, directory:str):
        """Set the output directory for saving images."""
        # set output path
        self._directory = directory
        return
    
    def set_delay(self, delay_s:float):
        """Set the time delay (in seconds) between image fetches."""
        # set thread delay in seconds
        self._delay = delay_s
        return

    """ ---------------------------------------------------------------------------- """

    def _set_wifi(self):
        # set up Wi-Fi profile
        if OP_SYSTEM == "Windows":
            # create profile (windows)
            config = "<?xml version=\"1.0\"?>\n"
            config = config + "<WLANProfile xmlns=\"http://www.microsoft.com/networking/WLAN/profile/v1\">\n"
            config = config + "\t<name>" + WIFI_NAME + "</name>\n"
            config = config + "\t<SSIDConfig>\n"
            config = config + "\t\t<SSID>\n"
            config = config + "\t\t\t<name>" + WIFI_NAME + "</name>\n"
            config = config + "\t\t</SSID>\n"
            config = config + "\t</SSIDConfig>\n"
            config = config + "\t<connectionType>ESS</connectionType>\n"
            config = config + "\t<connectionMode>auto</connectionMode>\n"
            config = config + "\t<MSM>\n"
            config = config + "\t\t<security>\n"
            config = config + "\t\t\t<authEncryption>\n"
            config = config + "\t\t\t\t<authentication>WPA2PSK</authentication>\n"
            config = config + "\t\t\t\t<encryption>AES</encryption>\n"
            config = config + "\t\t\t\t<useOneX>false</useOneX>\n"
            config = config + "\t\t\t</authEncryption>\n"
            config = config + "\t\t\t<sharedKey>\n"
            config = config + "\t\t\t\t<keyType>passPhrase</keyType>\n"
            config = config + "\t\t\t\t<protected>false</protected>\n"
            config = config + "\t\t\t\t<keyMaterial>" + WIFI_PASSWORD + "</keyMaterial>\n"
            config = config + "\t\t\t</sharedKey>\n"
            config = config + "\t\t</security>\n"
            config = config + "\t</MSM>\n"
            config = config + "</WLANProfile>\n"
            # save profile
            file_name = self.get_path() + sep + WIFI_NAME + ".xml"
            file = open(file_name, "w")
            file.write(config)
            file.close()
            # load profile
            command = "netsh wlan add profile filename=\"" + WIFI_NAME + ".xml\"" + " interface=WiFi"
            response, _ = self._run_cmd(command)
            # check response
            if not ("Profile " + WIFI_NAME + " is added on interface WiFi." in response):
                self.print("couldn't set up Wi-Fi network", self.LogLevel.error)
                raise AIDeckError("couldn't set up Wi-Fi network")
            else:
                self.print("Wi-Fi profile created", self.LogLevel.info)
            return
        elif OP_SYSTEM == "Linux":
            # create profile (linux)
            file_name = "/etc/wpa_supplicant/wpa_supplicant.conf"
            config = "ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n"
            config = config + "update_config=1\n"
            config = config + "country=ES\n"
            config = config + "\nnetwork={\n"
            config = config + "\tssid=\"" + WIFI_NAME + "\"\n"
            config = config + "\tpsk=\"" + WIFI_PASSWORD + "\"\n"
            config = config + "\tkey_mgmt=WPA-PSK\n"
            config = config + "}\n"
   
            # save profile, #TODO file permissions do not work and checking of the network has to be done
            #os.chmod(file_name, 0o600)  # secure file permissions
            #file = open(file_name, "w")
            #file.write(config)
            
            #file.close()
            #print(f"Configuration file created at {file_name}")
    
    def _connect_wifi(self):
        # connect to Wi-Fi
        if OP_SYSTEM == "Windows":
            command = "netsh wlan connect name=\"" + WIFI_NAME + "\" ssid=\"" + WIFI_NAME + "\" interface=WiFi"
            command = f"nmcli dev wifi connect '{WIFI_NAME}' password '{WIFI_PASSWORD}'"
            response, _ = self._run_cmd(command)
        elif OP_SYSTEM == "Linux":
            try:
                interface = self.get_wifi_interface()
                self.start_hotspot(interface=interface, ssid=WIFI_NAME, password=WIFI_PASSWORD)
            except:
                raise OSError("Error while setting up WiFi Hotspot")
            
    
    def _check_wifi(self, retries=10, wait_s=0.5):
        # check if the connected network matches the required, added linux compatibility
        for _ in range(retries):
            if OP_SYSTEM == "Windows":
                command = "netsh wlan show interfaces"
                response, _ = self._run_cmd(command)
            
                response = response.split("\n")
                for line in response:
                    if "SSID" in line:
                        if WIFI_NAME in line:
                            return True
                
            
            elif OP_SYSTEM == "Linux":
                response = subprocess.run(["nmcli", "connection" ,"show" ,"--active"],capture_output=True, text=True)
                if "Hotspot" in response.stdout:
                    response = subprocess.run(["nmcli" ,"-f", "802-11-wireless.ssid", "connection", "show" ,"Hotspot"], capture_output=True, text=True)
                    if WIFI_NAME in response.stdout:
                        return True
                
            time.sleep(wait_s)   
        self.print("the connected network doesn't match the required one", self.LogLevel.critical)
        return False

    

    """ ---------------------------------------------------------------------------- """

    def _image_fetcher(self):
        # constantly download images to an internal buffer
        try:
            while not self._state.get_exit():
                image = self._get_image()
                if image is not None:  # Only update if we got a valid image
                    self._thread_lock.acquire()
                    self._last_image.data = image
                    self._last_image.used = False
                    self._thread_lock.release()
                time.sleep(self._delay)
        except (KeyboardInterrupt, AIDeckError):
            pass
        except socket.timeout:
            # Socket timeout is expected during normal operation, just continue
            pass
        except Exception as e:
            self.print(f"Error in image fetcher: {e}", self.LogLevel.warning)
        return
    
    def _receive_bytes(self, length):
        """Receive and decode a full image from the AI Deck.

        Returns:
            numpy.ndarray | None: Decoded color image or None on failure.
        """
        data = bytearray()
        try:
            while len(data) < length:
                chunk = self._socket.recv(length - len(data))
                if not chunk:
                    # Connection closed
                    raise AIDeckError("Connection closed")
                data.extend(chunk)
        except socket.timeout:
            # Timeout - incomplete data, raise so caller knows to retry
            raise AIDeckError(f"Socket timeout: only received {len(data)}/{length} bytes")
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except OSError as message:
            if "is not a socket" in str(message):
                raise KeyboardInterrupt
            else:
                raise OSError(message)
        return data
    
    
    def _get_image(self):
        """Receive and decode a full image from the AI Deck.

        Returns:
            numpy.ndarray | None: Decoded color image or None on failure.
        """
        try:
            # Info-Header (4 Byte)
            info_raw = self._receive_bytes(4)
            if len(info_raw) != 4:
                #print(f"[ERROR] Info header too short: got {len(info_raw)} bytes")
                return None

            length, routing, function = struct.unpack("<HBB", info_raw)

            # image header should be 11 bytes
            image_header = self._receive_bytes(length - 2)
            #print(f"[DEBUG] Received header: {image_header} ({len(image_header)} bytes)")

            if len(image_header) != 11:
                #print(f"[ERROR] Expected 11 bytes for header, got {len(image_header)}")
                return None

            magic, width, height, depth, format, size = struct.unpack("<BHHBBI", image_header)

            if magic != 0xBC:
                #print(f"[ERROR] Invalid magic byte: {magic}")
                return None

            image_stream = bytearray()
            while len(image_stream) < size:
                info_raw = self._receive_bytes(4)
                length, destination, source = struct.unpack("<HBB", info_raw)
                chunk = self._receive_bytes(length - 2)
                image_stream.extend(chunk)

            # Bayer → RGB
            bayer_image = numpy.frombuffer(image_stream, dtype=numpy.uint8)
            bayer_image.shape = (height, width)

            if format == 0:
                color_image = cv2.cvtColor(bayer_image, cv2.COLOR_BayerBG2BGRA)
            else:
                color_image = cv2.imdecode(bayer_image, cv2.IMREAD_UNCHANGED)

            return color_image

        except KeyboardInterrupt:
            raise
        except AIDeckError as e:
            # Timeout or incomplete data - just return None to retry next time
            return None
        except Exception as e:
            print(f"[ERROR] Unexpected error in _get_image: {e}")
            return None
    
    def save_image(self):
        """Save the latest received image to disk and optionally display it.

        Returns:
            bool: True if a new image was saved, False otherwise.
        """
        try:
            # get the last image
            self._thread_lock.acquire()
            image = self._last_image
            flag = image.used
            image.used = True
            self._thread_lock.release()
            # check if it was saved or not
            if flag:
                self.print("there is no new image to be saved", self.LogLevel.info)
                return False
            # check if it is a valid image or not
            try:
                if image.data == None:
                    self.print("no image has been made yet", self.LogLevel.info)
                    return False
            except ValueError:
                pass
            # save it
            self.print("saving image from AI deck " + str(self._mac), self.LogLevel.info)
            cv2.imwrite(self._directory + sep + str(self._mac) + "_" + str(self._image_counter) + ".png", image.data)
            self._image_counter = self._image_counter + 1
            # display it
            if self._display:
                cv2.imshow("AI deck " + str(self._mac), image.data)  # makes the script more visual
                cv2.waitKey(1)
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        return True
    
    """ ---------------------------------------------------------------------------- """

def worker(flag:Flag, counter:Counter, lock:ProcessLock, delay, ip, mac, directory:str, display=True, log_enable=True, log_file=True, log_level=LogLevel.message, continuous=False):
    """Worker function that manages AI Deck connection and image recording.

    Args:
        flag (Flag): Shared flag object for synchronization.
        counter (Counter): Shared counter for image numbering.
        lock (ProcessLock): Interprocess lock for thread-safe operations.
        delay (float): Delay between operations.
        ip (str): IP address of the AI Deck.
        mac (str): MAC address of the AI Deck.
        directory (str): Output directory for saved images.
        display (bool, optional): Whether to display images. Defaults to True.
        log_enable (bool, optional): Enable or disable logging. Defaults to True.
        log_file (bool, optional): Enable log file output. Defaults to True.
        log_level (LogLevel, optional): Logging verbosity. Defaults to LogLevel.message.
        continuous (bool, optional): If True, stream images continuously without waiting for positioning signals. Defaults to False.
    """
    deck = AI_Deck(ip, mac)  # initialize object
    deck.logging(log_enable, log_file, log_level, deck.get_path() + sep + "logs" + sep + directory.split(sep)[-1])   # set up logging
    deck.set_display(display)   # display, or hide images
    deck.set_directory(directory)   # set output path
    deck.set_delay(delay)   # set thread delay
    deck.print("waiting for start signal", deck.LogLevel.info)
    while flag.get_connected():
        time.sleep(0.5)
    deck.connect()  # connect to the socket
    deck.print("deck connected", deck.LogLevel.info)
    try:
        if continuous:
            # Continuous streaming mode - publish images all the time
            deck.print("starting continuous image streaming", deck.LogLevel.info)
            while True:
                # exit if required
                if flag.get_exit():
                    deck.print("disconnecting", deck.LogLevel.info)
                    deck.disconnect()
                    break
                # continuously save images - keep trying until one succeeds
                if deck.save_image():
                    lock.acquire()
                    counter.set(deck.get_image_count())
                    lock.release()
                # Always sleep a small amount, similar to test_ai_deck.py polling
                time.sleep(delay)
        else:
            # Synchronized mode - wait for positioning signals
            while True:
                # exit if required
                if flag.get_exit():
                    deck.print("disconnecting", deck.LogLevel.info)
                    deck.disconnect()
                    break
                # wait for the drone to be positioned
                deck.print("waiting for drone to be on position", deck.LogLevel.info)
                while (not flag.get_on_position()) and (not flag.get_exit()):
                    time.sleep(delay)
                # set state to start recording
                deck.print("drone positioned", deck.LogLevel.info)
                if not flag.get_exit():
                    lock.acquire()
                    deck.print("start recording", deck.LogLevel.info)
                    flag.set_recording()
                    lock.release()
                # record an image
                deck.print("waiting for image", deck.LogLevel.info)
                while not deck.save_image():
                    time.sleep(delay)
                deck.print("image from " + deck._mac + " saved", deck.LogLevel.message)
                # set output variables
                lock.acquire()
                deck.print("signaling to drone", deck.LogLevel.info)
                counter.set(deck.get_image_count())
                if not flag.get_exit():
                    flag.set_image_saved()
                lock.release()
                time.sleep(delay)
    except (AIDeckError, KeyboardInterrupt):
        deck.print("disconnecting", deck.LogLevel.info)
        deck.disconnect()   # shut down
    return
