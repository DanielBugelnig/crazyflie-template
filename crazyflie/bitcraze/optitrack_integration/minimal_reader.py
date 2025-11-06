#!/usr/bin/env python3
# Minimal NatNet reader: print pose of one RB once per second (no frame dump)

import time
from crazyflie.bitcraze.optitrack_integration.NatNetClient import NatNetClient  # from OptiTrack NatNet SDK samples
from crazyflie.constants import CLIENT_IP, SERVER_IP, USE_MULTICAST, RIGID_BODY_ID, MOCAP_TX_RATE_HZ
# ===== CONFIG =====
CLIENT_IP     = "192.168.1.143"
SERVER_IP     = "192.168.1.171"
USE_MULTICAST = False
TARGET_RB_ID  = RIGID_BODY_ID[0]  # set to the rigid body ID you want to track
PRINT_HZ      = 120
# ==================

latest = {"pos": None, "quat": None, "t": 0.0}

def on_rigid_body(rigid_body_id, position, rotation):
    if rigid_body_id == TARGET_RB_ID:
        latest["pos"]  = position
        latest["quat"] = rotation
        latest["t"]    = time.time()


def main():
    client = NatNetClient()
    client.set_client_address(CLIENT_IP)
    client.set_server_address(SERVER_IP)
    client.set_use_multicast(USE_MULTICAST)
    client.rigid_body_listener = on_rigid_body

    print("[Init] Starting NatNet client…")
    if not client.run('d'):
        print("[Error] Failed to start NatNet client. Check IPs and Motive streaming settings.")
        return
    print(f"[Init] Listening for RB {TARGET_RB_ID}. Ctrl+C to stop.")

    try:
        period = 1.0 / max(1, PRINT_HZ)
        while True:
            if latest["pos"] is not None:
                x, y, z = latest["pos"]
                qx, qy, qz, qw = latest["quat"]
                age_ms = (time.time() - latest["t"]) * 1000.0
                print(f"RB {TARGET_RB_ID} | pos=({x:+.3f}, {y:+.3f}, {z:+.3f}) m  "
                      f"quat=({qx:+.3f}, {qy:+.3f}, {qz:+.3f}, {qw:+.3f})  "
                      f"age={age_ms:5.1f} ms")
            time.sleep(period)
    except KeyboardInterrupt:
        print("\n[Shutdown] Stopping…")
    finally:
        client.shutdown()
        print("[Shutdown] Done.")

if __name__ == "__main__":
    main()
