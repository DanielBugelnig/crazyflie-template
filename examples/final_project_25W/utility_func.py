from pathlib import Path
import sys, os, matplotlib.pyplot as plt
from math import sin,cos,radians
import pandas as pd, os

# add project root 
sys.path.append(str(Path(__file__).resolve().parents[2]))
from crazyflie import bitcraze


def create_trajectory(calculator:bitcraze.trajectory, list_of_pos,no_yaw=False) -> list:
    result=[]
    result.append(calculator.get_position(x=0,y=0,z=0.8, yaw=0, pitch=0, roll=0))
    for item in list_of_pos:
        result.append(calculator.get_position(x=item[0],y=item[1],z=item[2], yaw=item[3] if not no_yaw else 0, pitch=0, roll=0))
    return result


def save_data(cf_data, opti_data, controller_type_id):
    """
    Saves flight data to CSV.
    Args:
        cf_data (list): Drone logs
        opti_data (list): Optitrack logs
        controller_type_id (int): 1=PID, 2=Mel, 3=INDI...
    """
    if not cf_data:
        print("No flight data to save.")
        return
    
    comment = input('Log comment: ').lower().strip().replace(" ", "_")

    df_opti = pd.DataFrame(opti_data)
    df_cf = pd.DataFrame(cf_data)

    ctrl_names = ['PID', 'Mel', 'INDI', 'Bres', 'Lee']
    ctrl_folder_name = ctrl_names[controller_type_id - 1]

    base_path = Path(__file__).resolve().parents[0]
    save_dir = base_path / 'logs' / ctrl_folder_name
    os.makedirs(save_dir, exist_ok=True)

    opti_path = save_dir / f"opti_log_{comment}.csv"
    cf_path = save_dir / f"cf_log_{comment}.csv"
    
    df_opti.to_csv(opti_path, index=False)
    df_cf.to_csv(cf_path, index=False)
    
    print(f"Data saved to: {save_dir}")


def visualise_planned_path_2D(positions):
    """Generates 2D graph x versus y from trajectory (list[State])

    Args:
        positions (list[State]): trajectory
    """
    # Handle both raw lists and State objects
    if hasattr(positions[0], 'x'):
        xs = [p.x for p in positions]
        ys = [p.y for p in positions]
    else:
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]
    
    plt.figure(figsize=(8, 6))
    plt.plot(xs, ys, 'ro--', label='Planned Path')
    plt.xlabel('X (m)')
    plt.ylabel('Y (m)')
    plt.grid(True)
    plt.axis('equal')
    plt.legend()
    plt.show()


def visualise_planned_path_3D(positions):
    """Generates 3D graph of trajectory (list[State]) where yaw is shown by vectors

    Args:
        positions (list[State]): trajectory
    """
    plt.figure(figsize=(10, 8))
    ax = plt.axes(projection="3d")
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.set_zlabel("Z [m]")

    # Handle both raw lists and State objects
    if hasattr(positions[0], 'x'):
        xs = [s.x for s in positions]
        ys = [s.y for s in positions]
        zs = [s.z for s in positions]
        yaws = [s.yaw for s in positions]
    else:
        xs = [s[0] for s in positions]
        ys = [s[1] for s in positions]
        zs = [s[2] for s in positions]
        yaws = [s[3] for s in positions]
    
    ax.plot(xs, ys, zs, color='lightsteelblue', linewidth=1)
    ax.scatter(xs, ys, zs, color='cyan', s=10, alpha=0.6)   

    skip_step = 2
    for i in range(0, len(xs), skip_step):
        u = 0.1* cos(radians(yaws[i]))
        v =  0.1* sin(radians(yaws[i]))
        ax.quiver(xs[i], ys[i], zs[i], u, v, 0, color='crimson', length=0.1, normalize=True)

    plt.show()