# Demo A Offline: Trajectory Recording, Processing, and Flight

This document outlines the structure and usage of the Demo A offline demonstration. The demo is divided into four main scripts, each responsible for a specific step in the process of recording, evaluating, processing, and flying a trajectory with a Crazyflie drone using an OptiTrack motion capture system.

## Project Structure

The demo consists of the following Python scripts:

- **`s01_recording.py`**: Handles the recording of trajectories using the OptiTrack system.
- **`s02_scoring.py`**: Evaluates the accuracy of a recorded trajectory against a predefined ideal path.
- **`s03_processing.py`**: Processes the raw trajectory data to prepare it for flight. This includes filtering, smoothing, and adding yaw information.
- **`s04_flying.py`**: Executes the flight of the Crazyflie drone along the processed trajectory.
- **`utils.py`**: Contains utility functions for plotting, file I/O, and other common tasks.

The trajectories are stored as CSV files in the `data/recorded_trajectories` and `data/processed_trajectories` directories.

## How It Works

The demo follows a four-step process:

### 1. Recording (`s01_recording.py`)

This script captures the drone's movement as a sequence of 3D waypoints.

- **Controls**:
    - `u`: Update the filename for the trajectory.
    - `s`: Start recording.
    - `e`: Stop recording and save the trajectory.
    - `q`: Quit the script.
- **Output**: A CSV file containing the raw trajectory data is saved in the `data/recorded_trajectories` directory.

### 2. Scoring (`s02_scoring.py`)

This script provides an accuracy score for the recorded trajectory by comparing it to an ideal trajectory.

- **Functionality**:
    - Calculates the deviation of the recorded path from the ideal path.
    - Provides an overall accuracy score and a visual plot of the comparison.
- **Usage**: This script can be run independently to evaluate a recorded trajectory.

### 3. Processing (`s03_processing.py`)

This script refines the raw trajectory to make it suitable for flight.

- **Process**:
    - **Filtering**: Removes redundant waypoints.
    - **Smoothing**: Applies a moving average filter to create a smoother flight path.
    - **Yaw Calculation**: Adds yaw angles to the trajectory to ensure the drone faces the direction of travel.
    - **Safety Cage**: Enforces a virtual cage to keep the drone within safe operating bounds.
- **Output**: A new CSV file with the processed trajectory is saved in the `data/processed_trajectories` directory.

### 4. Flying (`s04_flying.py`)

This script loads a processed trajectory and commands the Crazyflie to fly it.

- **Functionality**:
    - Prompts the user for the filename of the trajectory to fly.
    - If a processed version of the trajectory exists, it will be used. Otherwise, the script will process the raw trajectory on the fly.
    - Connects to the Crazyflie and the OptiTrack system.
    - Executes the flight and lands the drone upon completion.

## Configuration

Before running the demo, you may need to configure the following variables in the respective scripts' `CONFIG BEFORE USAGE` blocks:

- **`s01_recording.py`**:
    - `ID`: The wand rigid body ID of the drone.
    - `UPDATE_RATE`: Hz for averaging points.
    - `MIN_RECORDING_DIST`: Controls distance between points that will be recorded.
- **`s04_flying.py`**:
    - `URI`: The URI of the Crazyflie drone to connect to.
    - `ID`: The rigid body ID of the drone in the OptiTrack system.
    - `cage`: The dimensions of the virtual safety cage instantiated as a `VirtualCage`.

## How to Run

To run the demo, execute the scripts in the following order:

1.  **Record a trajectory**:
    ```bash
    python s01_recording.py
    ```
    Follow the on-screen instructions to record and save a trajectory.

2.  **(Optional) Score the trajectory**:
    ```bash
    python s02_scoring.py
    ```
    Enter the filename of the trajectory you want to evaluate.

3.  **Process the trajectory**:
    The processing step is integrated into the flying script. If you run `s04_flying.py` with a raw trajectory, it will be processed automatically. You can also run `s03_processing.py` independently to process a trajectory and save it.

4.  **Fly the trajectory**:
    ```bash
    python s04_flying.py
    ```
    Enter the filename of the trajectory you want to fly. The script will handle the rest.