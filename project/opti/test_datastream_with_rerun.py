from pathlib import Path
import sys
import time
import rerun as rr

sys.path.append(str(Path(__file__).resolve().parents[1]))

from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor

RIGID_BODY_ID = 15


def test_optitrack():
    print("Connecting to OptiTrack...")
    monitor = NatNetRigidBodyMonitor()
    monitor.start()

    # init rerun
    rr.init("optitrack_minimal_test", spawn=True)
    trajectory = []
    # ------------------------

    time.sleep(2)
    print(f"Connected! Listening for Rigid Body ID {RIGID_BODY_ID}.\nPress Ctrl+C to stop.\n")

    try:
        while True:
            pos = monitor.get_position(RIGID_BODY_ID)

            if pos is not None:
                print(f"Tracking ID {RIGID_BODY_ID} -> X: {pos[0]:.3f} | Y: {pos[1]:.3f} | Z: {pos[2]:.3f}")

                # log to rerun
                current_pos = [pos[0], pos[1], pos[2]]
                trajectory.append(current_pos)

                # tail for ~10 seconds at 10Hz
                if len(trajectory) > 100:
                    trajectory.pop(0)

                # red dot
                rr.log("mocap/marker", rr.Points3D(current_pos, colors=[255, 0, 0], radii=0.03))

                #  tail lighter red line
                rr.log("mocap/trail", rr.LineStrips3D(trajectory, colors=[255, 100, 100]))
                # --------------------
            else:
                print(f"No data for ID {RIGID_BODY_ID}. Is it visible to the cameras?")

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nTest stopped by user.")


if __name__ == "__main__":
    test_optitrack()