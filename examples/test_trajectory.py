from pathlib import Path
import sys, time

sys.path.append(str(Path(__file__).resolve().parents[1]))

from crazyflie import bitcraze
import matplotlib.pyplot as plt

if __name__ == "__main__":
    calculator = bitcraze.trajectory()
    calculator.logging(enable=True, file=False, level=calculator.LogLevel.debug)
    calculator.set_count(1)   # number of dummy drones
    displacement = 0.05 # only used for displaying

    # initialize the plot
    figure = plt.figure("3D Trajectory")
    ax = figure.add_subplot(projection="3d")
    ax.set_xlabel("X [m]")
    ax.set_ylabel("Y [m]")
    ax.set_zlabel("Z [m]")
    colors = ["blue", "green", "black", "purple"]

    try:

        # display estimated object position in red
        calculator._get_object_position()
        circle_coordinates = calculator.circle(radius=1, positions=10, altitude=1.0)

        ax.scatter([calculator._object_placement.x], [calculator._object_placement.y], [calculator._object_placement.z], color="red", marker="o")

        # display trajectory in blue/green/black/purple
        for position_index in range(len(circle_coordinates)):
            verified_position = calculator.verify_position(circle_coordinates[position_index])
            for index in range(len(verified_position)):
                x = verified_position[index].x
                y = verified_position[index].y
                z = verified_position[index].z
                yaw = verified_position[index].yaw
                if position_index != 0:
                    ax.scatter([x], [y], [z + index * displacement], color=colors[index], marker="o")
                else:
                    ax.scatter([x], [y], [z + index * displacement], color="cyan", marker="o")
                if index == 0:
                    # annotate only once
                    ax.text(x, y, (z + index * displacement), str(yaw))
                    print(str(position_index) + ":\tx - " + str(round(x, 2)) + "\ty - " + str(round(y, 2)) + "\tyaw - " + str(round(yaw, 2)))

        # display anchors in magenta
        for anchor in calculator._anchors:
            ax.scatter([anchor.x], [anchor.y], [anchor.z], color="magenta", marker="o")

    except bitcraze.TrajectoryError:
        pass

    plt.show()
