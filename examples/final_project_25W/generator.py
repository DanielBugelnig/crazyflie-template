from math import sin, pi,atan2,cos,degrees


def sinusoid(amp:float, wavelen:float, altitude:float, update_rate:int, wave_period_s:float, num_of_cycles:int) -> list[list]:
    """Generates sinusoidal trajectory for one drone [x, y, z, yaw].

    Args:
        amp (float): sine amplitude
        wavelen (float): how much CF must cover in one cycle
        altitude (float): altitude at which to fly
        update_rate (int): frequency (Hz) with which commands must be send Hz
        wave_period_s (int): desired time for CF to fly whole 8 curve
        num_of_cycles (int): how many times to repeat one period of sine

    Returns:
        list[list]: 3D trajectory positions for one drone, pos defined as [x, y, z, yaw]
    """
    dt = 1.0 / update_rate                                  # time step (s)
    N = int(wave_period_s * update_rate) * num_of_cycles    # points per cycle
    
    omega = 2 * pi / wave_period_s                          # angular frequency (rad/s)
    vx = wavelen / wave_period_s                           
    
    result = []
    for k in range(N+1):
        t = k * dt                                          # time at step k
        x = vx * t                                          
        y = amp * sin(omega * t)                                     

        # yaw based on velocity
        dx = vx                                            
        dy = amp * omega * cos(omega * t)                  
        yaw = degrees(atan2(dy, dx))

        result.append([x, y, altitude, yaw])
    return result


def figure8curve(amp_x:float, amp_y:float, altitude:float, update_rate:int, duration_of_curve:float, num_of_cycles:int) -> list[list]:
    """Generates figure-eight curve (using Lissajous curve) for one drone [x, y, z, yaw].
    
    Args:
        amp_x (float): amplitude of 8 curve along X
        amp_y (float): amplitude of 8 curve along Y
        altitude (float): altitude at which to fly
        update_rate (int): frequency (Hz) with which commands must be send
        duration_of_curve (float): duration of one full figure-eight curve
        num_of_cycles (int): how many times to fly trajectory

    Returns:
        list[list]: 3D trajectory positions for one drone, pos defined as [x, y, z, yaw]
    """
    dt = 1.0 / update_rate                                              # time step (s)
    N = int(duration_of_curve * update_rate) * num_of_cycles            # total points

    omega = 2 * pi / duration_of_curve                                  # angular frequency (rad/s)
    result = []

    for k in range(N + 1):
        t = k * dt                                                      # time at step k
        x = amp_x * sin(omega * t)                                     
        y = amp_y * sin(2 * omega * t)                                 

        dx = amp_x * omega * cos(omega * t)                           
        dy = amp_y * (2 * omega) * cos(2 * omega * t)                  
        yaw = degrees(atan2(dy, dx))

        result.append([x, y, altitude, yaw])
    return result


if __name__ == '__main__':
    from utility_func import visualise_planned_path_2D, visualise_planned_path_3D
    from run_cm import trajectories

    print('\nStraight line trajectory')
    visualise_planned_path_2D(trajectories[1])

    print('\nSinusoid trajectory')
    visualise_planned_path_3D(trajectories[2])

    print('\nFigure 8 trajectory')
    visualise_planned_path_3D(trajectories[3])