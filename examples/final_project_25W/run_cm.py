from pathlib import Path
import sys, time

# add project root 
sys.path.append(str(Path(__file__).resolve().parents[2]))
 
from crazyflie import bitcraze
from crazyflie.core.base_utils import LogLevel
from crazyflie.bitcraze.crazyflie import CrazyFlie
from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor
from crazyflie.bitcraze.trajectory import Trajectory

from generator import sinusoid, figure8curve
from utility_func import create_trajectory, save_data, visualise_planned_path_2D, visualise_planned_path_3D


# constants
DEFAULT_HEIGHT = 0.8
URI = 'radio://0/100/2M/E7E7E7E704'
STREAMIND_ID = 38
UPDATE_RATE = 10              # Hz (Streaming Rate)
DURATION = 2.0                # Seconds (Total Flight Time)

CONTROLLER_TYPE = 5 # 1 2 3 4 5 = PID, Mel, INDI, Bres, Lee
TRAJECTORY_COUNT = 2    #   (0=Hover, 1=Line, 2=Sine, 3=Fig8)
no_yaw = False


trajectories = {
    0: [[0, 0, DEFAULT_HEIGHT, 0]],
    1: [[0, 0, DEFAULT_HEIGHT, 0],[1.0, 0, DEFAULT_HEIGHT, 0]],
    2: sinusoid(
        amp=0.5, 
        wavelen=1.0, 
        altitude=DEFAULT_HEIGHT, 
        update_rate=UPDATE_RATE, 
        wave_period_s=DURATION,
        num_of_cycles=1
    ),
    3: figure8curve(
        amp_x=0.5, 
        amp_y=0.3, 
        altitude=DEFAULT_HEIGHT, 
        update_rate=UPDATE_RATE, 
        duration_of_curve=DURATION, 
        num_of_cycles=1
    )
}

cf_data, opti_data = [], []

if __name__ == '__main__':
    # calculating path
    calculator = Trajectory()
    calculator.logging(enable=False, file=False, level=calculator.LogLevel.message)
    calculator.set_count(1) # amount of CF

    positions = create_trajectory(calculator, trajectories[TRAJECTORY_COUNT],no_yaw)
    if TRAJECTORY_COUNT == 0: HOVER=True

    for pos in positions:
        print(pos)

    #visualise_planned_path(positions)
    #visualise_planned_path_2D(positions)
    visualise_planned_path_3D(positions)

    # setup optitrack
    nnm = NatNetRigidBodyMonitor() # NatNetMonitor
    nnm.start()

    while not nnm.is_running(): time.sleep(0.1)

    cf = CrazyFlie()
    cf.logging(enable=True, file=True, level=LogLevel.debug)
    cf.set_natnet_monitor(nnm)

    try:
        cf.scan(specific=URI)
        cf.connect(start_flying=True, localization_mode='Optitrack')
        cf.select_controller_type(CONTROLLER_TYPE)
        time.sleep(0.1)

        start_time = time.time()
        for pos in positions:
            cf.fly(pos)

            while not cf.arrived(pos):
                timestamp = time.time() - start_time

                state = cf._current_state 
                
                cf_data.append({
                    'timestamp': timestamp,
                    
                    'x': state.x, 'y': state.y, 'z': state.z,
                    'target_x': pos.x, 
                    'target_y': pos.y, 
                    'target_z': pos.z,
                    'roll': state.roll, 'pitch': state.pitch, 'yaw': state.yaw,
                    'controller': CONTROLLER_TYPE
                })

                curr_pos = nnm.get_position(STREAMIND_ID)
                if curr_pos:
                    opti_data.append({
                        'timestamp': timestamp,
                        'x': curr_pos[0], 'y': curr_pos[1], 'z': curr_pos[2]
                    }) 

                time.sleep(0.1)
            time.sleep(0.2)
        time.sleep(0.5)

        if HOVER:time.sleep(2.0)
        cf.land()

    except (bitcraze.CrazyFlieError, KeyboardInterrupt):
        pass

    cf.disconnect()
    save_data(cf_data, opti_data, CONTROLLER_TYPE)