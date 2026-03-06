
import time
import threading
from typing import Dict, Optional, Tuple
from unittest.mock import Base
from .NatNetClient import NatNetClient
# from NatNetClient import NatNetClient  # from OptiTrack NatNet SDK samples
from crazyflie.constants import CLIENT_IP, SERVER_IP, USE_MULTICAST, MOCAP_TX_RATE_HZ

Pose = Tuple[float, float, float]
Quat = Tuple[float, float, float, float]

class NatNetRigidBodyMonitor(Base):
    """
    Minimal NatNet reader as a class.

    Features:
      - Start/stop the NatNet client
      - Thread-safe storage of the latest pose of one target rigid body
      - Optional console printing at a chosen rate
      - Context-manager support (so you can use "with ... as monitor:")
    """

    def __init__(
        self,
        client_ip: str = CLIENT_IP,
        server_ip: str = SERVER_IP,
        use_multicast: bool = USE_MULTICAST,
        natnet_mode: str = "d",          # 'd' = data, 'c' = command (per SDK)
        print_rate_hz: float = 1.0,
    ) -> None:
        self.client_ip = client_ip
        self.server_ip = server_ip
        self.use_multicast = use_multicast
        self.natnet_mode = natnet_mode
        self.print_period = 1.0 / max(1e-6, print_rate_hz)

        self._client: Optional[NatNetClient] = None
        self._running = False
        self._print_thread: Optional[threading.Thread] = None

        self._lock = threading.Lock()
        # Per-RB storage
        self._pos: Dict[int, Pose] = {}
        self._quat: Dict[int, Quat] = {}
        self._t_last: Dict[int, float] = {}


    def is_running(self) -> bool:
        """Return whether the NatNet client is running."""
        return self._running
    # -------------------- lifecycle --------------------

    def start(self) -> bool:
        """Start the NatNet client and begin receiving frames."""
        if self._running:
            return True

        client = NatNetClient()
        client.set_client_address(self.client_ip)
        client.set_server_address(self.server_ip)
        client.set_use_multicast(self.use_multicast)
        client.rigid_body_listener = self._on_rigid_body

        print("[Init] Starting NatNet client…")
        ok = client.run(self.natnet_mode)
        if not ok:
            print("[Error] Failed to start NatNet client. Check IPs and Motive streaming settings.")
            return False

        self._client = client
        self._running = True
        print(f"[Init] Listening to all Rigid Bodies")
        return True

    def stop(self) -> None:
        """Stop the NatNet client and clean up."""
        if not self._running:
            return
        print("[Shutdown] Stopping…")
        try:
            if self._client is not None:
                self._client.shutdown()
        finally:
            self._client = None
            self._running = False
            print("[Shutdown] Done.")

    # -------------------- callback & data handling --------------------

    def _on_rigid_body(
        self,
        rigid_body_id: int,
        position: Pose,
        rotation: Quat,
    ) -> None:
        now = time.time()
        with self._lock:
            self._pos[rigid_body_id] = position
            self._quat[rigid_body_id] = rotation
            self._t_last[rigid_body_id] = now
            
    def get_position(self, rb_id: int) -> Optional[Pose]:
        """Latest position (x,y,z) for this RB, or None if not available."""
        with self._lock:
            return self._pos.get(rb_id)
    def get_latest(self, rb_id: int) -> Tuple[Optional[Pose], Optional[Quat], float]:
        """Return (pos, quat, age_ms) for this RB ID."""
        with self._lock:
            pos = self._pos.get(rb_id)
            quat = self._quat.get(rb_id)
            t_last = self._t_last.get(rb_id, 0.0)
        age_ms = (time.time() - t_last) * 1000.0 if t_last else float("inf")
        return pos, quat, age_ms

    # -------------------- optional console print loop --------------------

    def start_print_loop(self, rb_ids: Optional[list[int]] = None) -> None:
        """
        Print poses periodically.
        - rb_ids=None -> print all RBs we’ve seen so far
        - rb_ids=[31,32] -> print only these
        """
        if not self._running:
            raise RuntimeError("Client not started. Call start() first.")
        if self._print_thread and self._print_thread.is_alive():
            return

        def _worker():
            try:
                while self._running:
                    with self._lock:
                        ids = rb_ids if rb_ids is not None else sorted(self._pos.keys())
                        snapshot = [(i, self._pos.get(i), self._quat.get(i), self._t_last.get(i, 0.0)) for i in ids]
                    now = time.time()
                    for i, pos, quat, t_last in snapshot:
                        if pos is None or quat is None:
                            continue
                        age_ms = (now - t_last) * 1000.0 if t_last else float("inf")
                        x, y, z = pos
                        qx, qy, qz, qw = quat
                        print(
                            f"RB {i} | "
                            f"pos=({x:+.3f}, {y:+.3f}, {z:+.3f}) m  "
                            f"quat=({qx:+.3f}, {qy:+.3f}, {qz:+.3f}, {qw:+.3f})  "
                            f"age={age_ms:5.1f} ms"
                        )
                    time.sleep(self.print_period)
            except Exception as e:
                print(f"[PrintLoop] Error: {e}")

        self._print_thread = threading.Thread(target=_worker, daemon=True)
        self._print_thread.start()
        
    def motive_to_cf_pos(self, pos_motive:Pose) -> Pose:
        """
        Convert position from Motive to Crazyflie coordinate frame.
        Motive: x-forward, y-left, z-up
        Crazyflie: x-forward, y-right, z-down
        """
        # needs to be checked
        x_m, y_m, z_m = pos_motive
        x_cf = x_m
        y_cf = -y_m
        z_cf = -z_m
        return pos_motive
    # -------------------- context manager --------------------

    def __enter__(self) -> "NatNetRigidBodyMonitor":
        if not self.start():
            raise RuntimeError("Failed to start NatNet client.")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()


# -------------------- Example usage --------------------
if __name__ == "__main__":
    # You can hardcode or import these values
    TARGET_RB_ID = 31
    CLIENT_IP = "192.168.1.143"
    SERVER_IP = "192.168.1.171"
    USE_MULTICAST = False
    PRINT_HZ = 1.0

    monitor = NatNetRigidBodyMonitor(
        target_rb_id=TARGET_RB_ID,
        client_ip=CLIENT_IP,
        server_ip=SERVER_IP,
        use_multicast=USE_MULTICAST,
        print_rate_hz=PRINT_HZ,
    )

    try:
        with monitor:
            monitor.start_print_loop()   # Optional: print continuously
            while True:
                # Example: access data programmatically
                pos, quat, age_ms = monitor.get_latest()
                # You could feed this into your EKF or log system here
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass