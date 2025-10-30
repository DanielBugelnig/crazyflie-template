# Testing OptiTrack Crazyflie flight
# Make Square (set the size) 
# Dnyandeep Mandaokar (dnyandeep.mandaokar@aau.at)
import threading
import time
from threading import Lock

from NatNetClient import NatNetClient 

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.positioning.position_hl_commander import PositionHlCommander

# ========= CONFIG =========
#URI = "radio://0/100/2M/E7E7E7E701"
URI = "radio://0/80/2M/E7E7E7E7E7"


# Rigid body ID in Motive for the Crazyflie (set to match your setup)
DRONE_RB_ID  = 31   # OptiTrack rigid body for the Crazyflie

# Motive / network
CLIENT_IP = "192.168.1.143"  # your PC IP
SERVER_IP = "192.168.1.171"  # Motive server IP
USE_MULTICAST = False

# Behavior & safety
HOVER_DURATION_S  = 60.0      # hover time before landing (seconds)
DEFAULT_TAKEOFF_H = 0.3       # meters
DEFAULT_VELOCITY  = 0.5       # m/s (HL commander)
MOCAP_TX_RATE_HZ  = 100       # Hz for extpos streaming
MOCAP_FRESH_MS    = 150       # mocap sample considered fresh if younger than this
MOCAP_SETTLE_S    = 1.0       # seconds of stable mocap before EKF reset

# Coordinate mapping ( axes) =========
# Motive x=forward/back, y=up/down, z=left/right
# Crazyflie world: x=forward, y=left, z=up
# Mapping: x_cf <- x_m ; y_cf <- -z_m ; z_cf <- y_m
def motive_to_cf_pos(p):
    x_m, y_m, z_m = p
    return (x_m, -z_m, y_m)

# Globals
position_lock = Lock()
shutdown_flag = threading.Event()

# latest raw pose from Motive (Motive frame)
drone_pose_motive = {"pos": None, "quat": None}
last_drone_time = None

# Local origin captured at start (CF coords)
origin_offset_cf = None  # (ox, oy, oz) in CF frame

# NatNet callbacks
def receive_rigid_body_frame(rigid_body_id, position, rotation):
    """
    position: tuple (x, y, z) in Motive coordinates
    rotation: tuple quaternion (qx, qy, qz, qw) in Motive coordinates
    """
    global last_drone_time
    now = time.time()
    if rigid_body_id == DRONE_RB_ID:
        with position_lock:
            drone_pose_motive["pos"] = position
            drone_pose_motive["quat"] = rotation
            last_drone_time = now

def _fresh_mocap(max_age_ms=MOCAP_FRESH_MS):
    with position_lock:
        return (drone_pose_motive["pos"] is not None) and last_drone_time and (time.time() - last_drone_time < max_age_ms/1000.0)

# Prep EKF + capture local origin 
def wait_and_seed_ekf_with_local_origin(scf, settle_s=MOCAP_SETTLE_S, timeout_s=5.0):
    """
    Waits for fresh, stable mocap, captures current CF-frame pose as origin,
    then enables EKF and seeds Kalman to local (0,0,0).
    """
    global origin_offset_cf

    t0 = time.time()
    fresh_count = 0
    last_cf = None

    while time.time() - t0 < timeout_s and not shutdown_flag.is_set():
        with position_lock:
            pos_m = drone_pose_motive["pos"]
            fresh = (pos_m is not None) and last_drone_time and (time.time() - last_drone_time < MOCAP_FRESH_MS/1000.0)

        if fresh:
            cf = motive_to_cf_pos(pos_m)
            if last_cf is not None:
                dx = abs(cf[0]-last_cf[0]) + abs(cf[1]-last_cf[1]) + abs(cf[2]-last_cf[2])
                if dx < 0.05:  # ~<5 cm while still
                    fresh_count += 1
            last_cf = cf
            if fresh_count * 0.05 >= settle_s:  # ~20 Hz effective
                break
        time.sleep(0.05)
    else:
        print("[Prep] WARN: extpos not fresh/stable; proceeding anyway.")
        last_cf = last_cf or (0.0, 0.0, 0.0)

    # Capture origin
    origin_offset_cf = last_cf
    print(f"[Prep] Local origin captured (CF coords): {origin_offset_cf}")

    def try_set(name, value):
        try:
            scf.cf.param.set_value(name, value)
        except Exception as e:
            print(f"[param] {name}={value} failed: {e}")

    # Enable EKF and seed to local origin (0,0,0)
    try_set("stabilizer.estimator", 2)     # EKF
    try_set("kalman.initialX", 0.0)
    try_set("kalman.initialY", 0.0)
    try_set("kalman.initialZ", 0.0)
    try_set("kalman.resetEstimation", 1)
    time.sleep(0.1)
    try_set("kalman.resetEstimation", 0)
    print("[Prep] EKF enabled and seeded at local (0,0,0).")

# Streaiming Threads
def mocap_streamer_thread(cf):
    """
    Streams external position in LOCAL frame:
      local = (mapped CF coords) - origin_offset_cf
    """
    period = 1.0 / MOCAP_TX_RATE_HZ
    while not shutdown_flag.is_set():
        with position_lock:
            pos_m = drone_pose_motive["pos"]
            fresh = last_drone_time and (time.time() - last_drone_time < MOCAP_FRESH_MS/1000.0)
            origin = origin_offset_cf

        if pos_m is not None and fresh and origin is not None:
            x_cf, y_cf, z_cf = motive_to_cf_pos(pos_m)
            lx = x_cf - origin[0]
            ly = y_cf - origin[1]
            lz = z_cf - origin[2]
            try:
                cf.extpos.send_extpos(lx, ly, lz)
            except Exception as e:
                print(f"[extpos] error: {e}")
        time.sleep(period)

# Move
def square(scf):

    lost_since = None
    takeoff_time = None

    def try_set(name, value):
        try:
            scf.cf.param.set_value(name, value)
        except Exception:
            pass

    try_set("stabilizer.estimator", 2)     # EKF
    try_set("locSrv.extPosStdDev", 0.001)  # meters (if present)

    with PositionHlCommander(
        scf,
        x=0.0, y=0.0, z=0.0,                        # LOCAL origin
        default_velocity=DEFAULT_VELOCITY,
        default_height=DEFAULT_TAKEOFF_H,
        controller=PositionHlCommander.CONTROLLER_PID
    ) as pc:


        start_time = time.time()
        duration = 15  # seconds


        # --- tunables ---
        SIDE_LEN = 0.6           # meters, square side length
        LEG_TIME = 2.5           # seconds to spend on each side (time-based switching)
        SWAP_XY_FOR_GO_TO = True # set False if your go_to expects (x_cf, y_cf, z_cf) directly
        # -----------------

        origin_cf = None             # (x0, y0, z0) captured from OptiTrack on first loop
        corners_cf = None            # 4 absolute waypoints in CF frame
        corner_idx = 0               # which corner commanding
        leg_start = time.time()      # when we started current leg

        start_time = time.time()
        while time.time() - start_time < duration:
            with position_lock:
                pos_m = drone_pose_motive["pos"]
                # Convert: OptiTrack -> Crazyflie frame
                x_cf, y_cf, z_cf = motive_to_cf_pos(pos_m)

                # keep your original rounded prints
                target_y = round(x_cf, 2)
                target_z = round(z_cf, 2)
                target_x = round(y_cf, 2)

            # Initialize the square on the FIRST measurement
            if origin_cf is None:
                x0, y0, z0 = x_cf, y_cf, z_cf
                z_des = z0
                corners_cf = [
                    (x0 + 0.0,       y0 + 0.0,       z_des),  # C0
                    (x0 + SIDE_LEN,  y0 + 0.0,       z_des),  # C1
                    (x0 + SIDE_LEN,  y0 + SIDE_LEN,  z_des),  # C2
                    (x0 + 0.0,       y0 + SIDE_LEN,  z_des),  # C3
                ]
                origin_cf = (x0, y0, z0)
                leg_start = time.time()  # start timing the first leg

            # Current commanded corner (absolute, CF frame)
            wx, wy, wz = corners_cf[corner_idx]

            # Map to your go_to argument order
            if SWAP_XY_FOR_GO_TO:
                go_x = round(wy, 2)      # your code: target_x = round(y_cf, 2)
                go_y = round(wx, 2)      # your code: target_y = round(x_cf, 2)
            else:
                go_x = round(wx, 2)
                go_y = round(wy, 2)
            go_z = round(wz, 2)

            try:
                print(f"[Track] Now at X={target_x}, Y={target_y}, Z={target_z} | Go to X={go_x}, Y={go_y}, Z={go_z} | corner={corner_idx}")
                pc.go_to(go_x, go_y, go_z)
            except Exception as e:
                print(f"[Error] Failed to go to target: {e}")

            # Time-based corner change (robust to noisy distance and slow update)
            if time.time() - leg_start >= LEG_TIME:
                corner_idx = (corner_idx + 1) % 4
                leg_start = time.time()

            time.sleep(0.5)

        pc.land()

# Stream
def start_streaming_and_drone():
    streaming_client = NatNetClient()
    streaming_client.set_client_address(CLIENT_IP)
    streaming_client.set_server_address(SERVER_IP)
    streaming_client.rigid_body_listener = receive_rigid_body_frame
    streaming_client.set_use_multicast(USE_MULTICAST)

    print("[Init] Starting NatNet client...")
    if not streaming_client.run('d'):
        print("[Error] Failed to start NatNet client.")
        return
    print("[Init] NatNet client started.")

    try:
        with SyncCrazyflie(URI, cf=Crazyflie(rw_cache="./cache")) as scf:
            # Start external pose streaming to the CF (LOCAL frame)
            mocap_thread = threading.Thread(target=mocap_streamer_thread, args=(scf.cf,))
            mocap_thread.daemon = True
            mocap_thread.start()

            # Prepare EKF & capture local origin
            wait_and_seed_ekf_with_local_origin(scf)
            
            # Move square
            square(scf)

    finally:
        shutdown_flag.set()
        streaming_client.shutdown()
        print("[Shutdown] NatNet client shutdown.")

#  Main 
if __name__ == "__main__":
    # Init the radio drivers once
    cflib.crtp.init_drivers()

    drone_thread = threading.Thread(target=start_streaming_and_drone)
    drone_thread.daemon = True
    drone_thread.start()

    # Keep the main thread alive until shutdown
    try:
        while drone_thread.is_alive():
            time.sleep(0.1)
    finally:
        shutdown_flag.set()



