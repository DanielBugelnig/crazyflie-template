from pathlib import Path
import sys, time, numpy as np, rerun as rr
from datetime import datetime
sys.path.append(str(Path(__file__).resolve().parents[2]))
from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor
from project.maneuver_a.utility_functions import save_waypoints

#constants
ID = 44
MAX_TRAJECTORY_POINTS = 500
THRESHOLD = 0.01
LOG_PATH_FREQUENCY = 10  #log full path every N new points
LOOP_SLEEP_DURATION = 0.005  #~200Hz loop rate

#rerun initialization
rr.init("marker_tracker", spawn=True)

#ideal traj generation
t = np.linspace(0, 2 * np.pi, 100)
A, B, Z0 = 1.0, 2.0, 1.0
ideal_points = np.column_stack((A * np.sin(t), B * np.sin(t) * np.cos(t), np.ones_like(t) * Z0))
rr.log("world/ideal_path", rr.LineStrips3D(ideal_points, colors=[176, 196, 222]))

#monitor setup
monitor = NatNetRigidBodyMonitor()
monitor.start()
time.sleep(2)


actual_trajectory = []  #store the entire history
last_pos_np = None  #store last logged pos
log_counter = 0

try:
    while True:
        pos = monitor.get_position(ID)
        if pos is not None:
            current_pos_np = np.array(pos)

            if last_pos_np is None or np.linalg.norm(current_pos_np-last_pos_np) >= THRESHOLD:
                actual_trajectory.append(pos)
                last_pos_np = current_pos_np
                rr.log("world/marker", rr.Points3D([pos], colors=[255, 0, 0], radii=0.05))

                #log full path periodically
                log_counter += 1
                if log_counter % LOG_PATH_FREQUENCY == 0: # Log only last MAX_TRAJECTORY_POINTS
                    rr.log("world/actual_path", rr.LineStrips3D(actual_trajectory[-MAX_TRAJECTORY_POINTS:], colors=[255, 0, 0]))
        time.sleep(LOOP_SLEEP_DURATION)

except KeyboardInterrupt:
    print("\nStopping tracker...")

finally:
    #save the entire recorded trajectory to a file
    if actual_trajectory:
        print(f"\nSaving full trajectory with {len(actual_trajectory)} points...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_dir = Path(__file__).parent / "saved_trajectories"
        user = input("Enter a name for the trajectory (or press Enter to use default): ").strip()
        base_name = user if user else f"trajectory_{timestamp}"
        filename = save_dir / f"{base_name}.csv"

        save_waypoints(np.array(actual_trajectory), filename)
    else:
        print("\nNo trajectory data to save.")



        """
        
        
        
[Init] Listening to all Rigid Bodies
resetting requested version to 3 1 0 0 from 0 0 0 0
MESA-INTEL: error: ../src/intel/vulkan/anv_batch_chain.c:2053: execbuf2 failed: Invalid argument (VK_ERROR_DEVICE_LOST)

thread 'main' panicked at 'Error in Surface::present: Validation Error

Caused by:
  Parent device is lost
'
wgpu-27.0.1/src/backend/wgpu_core.rs:3858
stack backtrace:
   6: core::panicking::panic_fmt
   7: wgpu::backend::wgpu_core::ContextWgpuCore::handle_error_fatal
   8: wgpu::api::surface_texture::SurfaceTexture::present
   9: egui_wgpu::winit::Painter::paint_and_update_textures
  10: <eframe::native::wgpu_integration::WgpuWinitApp as eframe::native::winit_integration::WinitApp>::run_ui_and_paint
  11: <eframe::native::run::WinitAppWrapper<T> as winit::application::ApplicationHandler<eframe::native::winit_integration::UserEvent>>::window_event
  12: eframe::native::run::run_wgpu

Troubleshooting Rerun: https://www.rerun.io/docs/getting-started/troubleshooting 
Report bugs: https://github.com/rerun-io/rerun/issues
[2026-04-02T13:37:47Z ERROR re_grpc_client::write] Write messages call failed: gRPC error, message: "transport error"
"""