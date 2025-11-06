"""
    store constants and settings here
        Daniel Bugelnig, 2025 (daniel.bugelnig@aau.at)
"""

from .core.shared_data import State



"""        EXPOSED SETTINGS - MODIFY HERE (can be added to UI)        """

# operating system
OP_SYSTEM = "Linux" # "Windows", "Linux" some features are not implemented on Windows

# Wi-Fi, set the settings of the access point created by the host computer
WIFI_NAME = "ai_deck"
WIFI_PASSWORD = "bitcraze"




"""        OTHER CONSTANTS (hardcoded constants, shoudn't be changed from one run to another)        """
# List all crazyflies here with their URIs
CRAZYFLIES = [
    "radio://0/90/2M/E7E7E7E701", # Daniels Crazyflie 2.1+ Number12
    "radio://0/90/2M/E7E7E7E702", # Daniels Crazyflie 2.1 Number13
    "radio://0/100/2M/E7E7E7E702",
    "radio://0/100/2M/E7E7E7E701",
    "radio://0/80/2M/E7E7E7E702",
    "radio://0/100/2M/E7E7E7E703",
    "radio://0/80/2M/E7E7E7E704",
    "radio://0/90/2M/E7E7E7E705",
    "radio://0/90/2M/E7E7E7E706",
    "radio://0/95/2M/E7E7E7E707",
    "radio://0/95/2M/E7E7E7E708",
    "radio://0/100/2M/E7E7E7E709",
    "radio://0/100/2M/E7E7E7E710",
    "radio://0/100/2M/E7E7E7E715", # 20 in 0x
]



# Lookup table for AI deck MAC addresses and drone addresses
MAC = ["-", # placeholder
    "78:21:84:7b:0f:58", #1 rgb
    "78:21:84:7a:4f:70", #2 rgb
    "78:21:84:7a:50:c8", #3 rgb
    "78:21:84:7b:0b:8c", #4 mono
]
MAC_LOOKUP = {
              "radio://0/100/2M/E7E7E7E701": MAC[2],   #rgb drone 1  # mono: "radio://0/100/2M/E7E7E7E701": "78:21:84:7b:0f:59"
              "radio://0/100/2M/E7E7E7E702": MAC[1],
              "radio://0/100/2M/E7E7E7E703": MAC[4],  # 78:21:84:7a:4f:70
              "radio://0/80/2M/E7E7E7E704": "78:21:84:7b:0f:58", # should be rgb (still to change) "78:21:84:7b:0f:58"
              "radio://0/90/2M/E7E7E7E705": "78:21:84:7a:4f:71",
              "radio://0/100/2M/E7E7E7E706": MAC[2],
              "radio://0/100/2M/E7E7E7E707": MAC[3],
              "radio://0/95/2M/E7E7E7E708": "78:21:84:7b:0b:8d", 
              "radio://0/100/2M/E7E7E7E709": MAC[4],
              "radio://0/100/2M/E7E7E7E710": "78:21:84:7a:4f:71",}   

# Positioning system settings
POSITIONING_SYSTEM = "OptiTrack"  # "OptiTrack"
# ===== CONFIG Optitrack =====
CLIENT_IP     = "192.168.1.143"
SERVER_IP     = "192.168.1.171"
USE_MULTICAST = False
# Rigid body IDs
RIGID_BODY_ID  =[
    13,
    12,
    35
    ]
#
MOCAP_TX_RATE_HZ  = 120       # Hz for extpos streaming
MOCAP_FRESH_MS    = 150       # mocap sample considered fresh if younger than this
MOCAP_SETTLE_S    = 1.0       # seconds of stable mocap before EKF reset
TIMEOUT = 5

# Meshroom path (used for 3D reconstruction on the host computer)
MESHROOM_ROOT = "/home/danielbugelnig/applications/Meshroom-2023.3.0"   
ALICE_VISION_ROOT = "/home/danielbugelnig/applications/Meshroom-2023.3.0/aliceVision"

FLYING_AREA =               [State(x=0,     y=0,     z=0.18),    # A0
                            State(x=3,     y=0.3,  z=0.18),    # A1
                            State(x=3.09,  y=2.5,  z=0.18),    # A2
                            State(x=0.0,  y=2.5, z=0.18),    # A3
                            State(x=0,     y=0,     z=2.03),    # A4
                            State(x=3,     y=0.3,  z=2.03),    # A5
                            State(x=3.09,  y=2.5,  z=2.03),    # A6
                            State(x=0,  y=2.50, z=2.03)]    # A7


# port to be used in Wi-Fi communication
WIFI_SOCKET_PORT = 5000

# drone battery parameters
LOW_BATTERY = 2.5   # V
RATED_CURRENT = 0.25    # Ah

# drone positioning thresholds
ARRIVAL_THRESHOLD_DISTANCE = 0.15  # m
ARRIVAL_THRESHOLD_ANGLE = 3   # deg
ARRIVAL_THRESHOLD_DISTANCE_ROUGH = 0.25  # m
ARRIVAL_THRESHOLD_ANGLE_ROUGH = 8   # deg
POSITION_AVERAGE = 1    # measurements to average when measuring position

# mapping parameters
DRONE_DELAY = 0.1     # s, delay between repeated operations in each thread
DECK_DELAY = 0.5      # s, delay between repeated operations in each thread

# camera
CAMERA = "RGB" # Monochrome, RGB
DISPLAY_IMAGES = True  # display images when received from the drone



# Potential Field parameters
REPULSION_FACTOR = 0.1
ATTRACTION_FACTOR = 1.4
REPULSION_FACTOR_OBJECT = 10
REPULSION_FACTOR_DRONE = 0.1
REPULSION_FACTOR_WALL = 0.2
OBJECT_RADIUS = 0.3
WALL_RADIUS = 0.6
DRONE_RADIUS = 0.8
OBJECT_NUMBER = 3
LINE_NUMBER = 1
GOAL_RADIUS = 0.05
GOAL_POSITIONS = 1

SPHERE_POINTS = 400
STEPSIZE = 0.01
RESOLUTION = 0.1

#local minima
WINDOW_SIZE = 10
THRESHOLD = 0.05
RANDOM_WALK_FACTOR = 0.1

#meshing
FILTER_FACTOR = 0.7


# result evaluation
EVALUATION_VOXEL_SIZE = 0.001
EVALUATION_SAMPLE_COUNT = 100000
EVALUATION_MAX_ITERATIONS = 500000
EVALUATION_THRESHOLD = 0.001
EVALUATION_RENDER_COUNT = 10
EVALUATION_SAVE_PICTURES = True
