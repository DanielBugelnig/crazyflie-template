"""
This script is dedicated for Maneuver A to read trajectory from OptiTrack and fly it offline

Usage:
1. Enter a trajectory name.
2. Press 's' to start recording the trajectory.
3. Press 'e' to stop recording (which saves it automatically).
4. Press 'u' to change the base filename for the next recording.
5. Press 'm' to plot the most recently saved trajectory (raw and enhanced).
6. Press 'f' to fly the trajectory defined by the current filename.
7. Press 'q' to quit the application.
"""

import csv, os, sys, time
from pathlib import Path
from threading import Lock, Thread
from pynput import keyboard

#add project root
sys.path.append(str(Path(__file__).resolve().parents[3]))

from crazyflie.bitcraze.optitrack_integration.optitrack import NatNetRigidBodyMonitor
import crazyflie.core.base_utils as base
from crazyflie import bitcraze
from crazyflie.bitcraze.trajectory import Trajectory
from crazyflie.bitcraze.crazyflie import CrazyFlie

#utility functions for plotting, saving and loading trajectories for the Maneuvers A
from utility_functions import plot_waypoints, load_waypoints, save_waypoints
#all logic for trajectory enhancements
from trajectory_processor import TrajectoryProcessor


class ManeuverAController:
    """Manages trajectory recording, saving and flying using keyboard commands"""
    def __init__(self, rigid_body_id=44, update_rate=10):
        self.base_path = Path(__file__).resolve().parent
        self.save_dir = self.base_path / 'trajectories'
        self.save_dir.mkdir(exist_ok=True)

        self.rigid_body_id = rigid_body_id
        self.update_rate = update_rate

        self.current_waypoints = [] #store recording trajectory
        self.base_filename = None #filename to save trajectory
        self.last_saved_filename = None #filename to load trajectory
        self.lock = Lock()

        self.is_recording = False #when True pos are saved for trajectory array
        self.is_running = True #when True info is taken from optitrack

        self.monitor = NatNetRigidBodyMonitor()
        self.processor = TrajectoryProcessor()
        self.listener = keyboard.Listener(on_press=self._on_press)


    def _track_object(self):
        while self.is_running:
            pos = self.monitor.get_position(self.rigid_body_id)
            if pos and self.is_recording:
                with self.lock:
                    self.current_waypoints.append(pos)
            time.sleep(1.0 / self.update_rate)


    def _get_unique_filename(self, base_name):
        if not base_name:   base_name = "unnamed_trajectory"
        filepath = self.save_dir / f'{base_name}.csv'
        if not filepath.exists():   return filepath
        counter = 1
        while True:
            new_filepath = self.save_dir / f'{base_name}_{counter}.csv'
            if not new_filepath.exists():
                return new_filepath
            counter += 1


    def _on_press(self, key):
        try:
            char = key.char
            if char == 's': self._start_recording()
            elif char == 'e': self._stop_and_save_recording()
            elif char == 'u': self._prompt_for_filename()
            elif char == 'm': self._plot_trajectory()
            elif char == 'f': self._fly_trajectory()
            elif char == 'q':
                self.is_running = False
                print("\nQuit command received. Shutting down...")
        except AttributeError:
            pass

    def _start_recording(self):
        if not self.base_filename:
            print("\nNo base filename set. Please set one first.")
            self._prompt_for_filename()
            if not self.base_filename: return
        if self.is_recording:
            print("Already recording. Press 'e' to end the current session.")
            return
        with self.lock:
            self.current_waypoints = []
            self.is_recording = True
        print("\n--- Recording started. Move the object now. ---")

    def _stop_and_save_recording(self):
        if not self.is_recording:
            print("\nNot recording. Press 's' to start.")
            return

        with self.lock:
            self.is_recording = False
            waypoints_to_save = self.current_waypoints.copy()

        #handle not valid trajectory
        if not waypoints_to_save:
            print("No waypoints were recorded. File not saved.")
            return

        #save valid trajectory
        save_path = self._get_unique_filename(self.base_filename)
        self.last_saved_filename = save_path
        print(f"--- Recording stopped ---")
        save_waypoints(waypoints_to_save, save_path)


    def _prompt_for_filename(self):
        try:
            new_name = input('\nEnter a base name for your trajectory file: ').lower().strip().replace(' ', '_')
            if new_name:
                self.base_filename = new_name
                self.last_saved_filename = new_name
                print(f"Base filename set to: '{self.base_filename}'")
            else:
                print("Invalid name. Please enter a valid filename.")
        except (EOFError, KeyboardInterrupt):
            print("\nFilename entry cancelled.")


    def _plot_trajectory(self):
        if not self.last_saved_filename or not self.last_saved_filename.exists():
            print("\nNo trajectory has been saved yet. Record one with 's' and 'e'.")
            return
        print(f"\nPlotting raw and processed data for {self.last_saved_filename}...")
        raw = load_waypoints(self.last_saved_filename)
        if raw is None or len(raw) == 0:
            print("Could not load or empty trajectory file.")
            return
        enhanced = self.processor.process(raw)
        plot_waypoints(trajectory=[enhanced, raw], labels=['Processed', 'Raw'])


    def _fly_trajectory(self):
        if not self.base_filename:
            print("\nNo base filename is set. Use 'u' to set one.")
            return
        files = sorted(self.save_dir.glob(f'{self.base_filename}*.csv'), reverse=True)
        if not files:
            print(f"No trajectory file found for base name '{self.base_filename}'.")
            return
        file_to_fly = files[0]
        print(f"\nPreparing to fly trajectory from: {file_to_fly}")
        raw_waypoints = load_waypoints(file_to_fly)
        if raw_waypoints is None or len(raw_waypoints) < 2:
            print("Trajectory is empty or too short to fly.")
            return
        enhanced_waypoints = self.processor.process(raw_waypoints)
        print(f"Processed trajectory has {len(enhanced_waypoints)} points.")
        cf = CrazyFlie()
        cf.set_natnet_monitor(self.monitor)
        calculator = Trajectory()
        calculator.set_count(1)
        positions = [
            calculator.get_position(x=item[0], y=item[1], z=item[2], yaw=item[3])
            for item in enhanced_waypoints
        ]
        try:
            cf.scan()
            cf.connect(start_flying=True)
            print("--- Starting flight ---")
            for pos_state in positions:
                cf.fly(pos_state)
                while not cf.arrived(pos_state):
                    time.sleep(0.1)
                time.sleep(0.2)
            cf.land()
            print("--- Flight complete ---")
        except (bitcraze.CrazyFlieError, KeyboardInterrupt) as e:
            print(f"\nFlight interrupted: {e}")
            cf.land()
        finally:
            cf.disconnect()


    def run(self):
        print("Starting OptiTrack monitor...")
        self.monitor.start()
        time.sleep(1)
        print("Starting object tracking thread...")
        tracker_thread = Thread(target=self._track_object, daemon=True)
        tracker_thread.start()
        self.listener.start()
        print("Keyboard listener started.")
        print("\n--- Maneuver A Controller Initialized ---")
        self._prompt_for_filename()

        print("Controls: [s]tart recording, [e]nd/save, [u]pdate filename, [m]ap plot, [f]ly, [q]uit")
        while self.is_running:
            time.sleep(0.1)

        self.listener.stop()
        print("Maneuver A has been shut down.")


if __name__ == '__main__':
    controller = ManeuverAController()
    controller.run()