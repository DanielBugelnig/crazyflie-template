"""
Utility base class focused on logging, command execution, simple filesystem helpers,
and minimal networking helpers.

This module defines:
- A custom log level ("MESSAGE" at level 25) and helpers to register it.
- A color helper for console output (ANSI escape codes).
- A `BaseClass` that provides:
  * configurable logging (file or console) with the custom MESSAGE level,
  * convenience `print()` wrapper that respects the selected log level,
  * progress bar printing,
  * basic filesystem helpers (create/delete directories, copy),
  * safe command execution wrapper,
  * minimal Wi-Fi hotspot helpers using `nmcli`,
  * a small constants export utility.

Notes
-----
- Colors are used only for console output; when logging to file, raw text is written
  and an additional colored line is printed to stdout for visibility.
- The code intentionally avoids changing your behavior or structure—only docstrings
  were added.
"""

import logging, datetime, os, sys, math, numpy, glob, shutil
from subprocess import Popen, PIPE  # command execution
from pynput import keyboard
from crazyflie.constants import OP_SYSTEM, ALICE_VISION_ROOT
from .shared_data import Flag, Lock, Counter
from multiprocessing.managers import BaseManager
import subprocess
import numpy as np
import re
try:
    import torch
    import torchvision
except:
    TORCH_INSTALLED = False
else:
    TORCH_INSTALLED = True


class _LogLevel:
    """Container for commonly used logging levels including a custom level.

    Attributes
    ----------
    debug : int
        Standard logging.DEBUG (10).
    critical : int
        Standard logging.CRITICAL (50).
    error : int
        Standard logging.ERROR (40).
    warning : int
        Standard logging.WARNING (30).
    info : int
        Standard logging.INFO (20).
    message : int
        Custom level (25), between INFO (20) and WARNING (30). Use for
        "important but not a warning" messages.
    """

    # define logging levels
    def __init__(self):
        self.debug = logging.DEBUG
        self.critical = logging.CRITICAL
        self.error = logging.ERROR
        self.warning = logging.WARNING
        self.info = logging.INFO
        self.message = 25  # importance between info and warning
        return


LogLevel = _LogLevel()

""" ---------------------------------------------------------------------------- """


class _colors:
    """ANSI color escape codes for pretty console output.

    Notes
    -----
    - Only used for console output. Files should remain free of escape sequences.
    - Set `to_file` to True to indicate that file logging is enabled; the class will
      then also print an extra colored line to stdout for human visibility.
    """

    # define print color sequences
    def __init__(self):
        self.red = "\033[91m"
        self.green = "\033[92m"
        self.yellow = "\033[93m"
        self.blue = "\033[94m"
        self.purple = "\033[95m"
        self.cyan = "\033[96m"
        self.end = "\033[0m"
        self.bold = "\033[1m"
        self.underline = "\033[4m"
        self.to_file = False
        return


""" ---------------------------------------------------------------------------- """


def _add_log_level(LogLevel: _LogLevel):
    """Register the custom MESSAGE log level and helper methods.

    This function adds:
    - The level name "MESSAGE" bound to `LogLevel.message` (25),
    - `Logger.message(self, message, *args, **kwargs)` for direct logger calls,
    - `logging.message(message, *args, **kwargs)` to log to the root logger.

    Parameters
    ----------
    LogLevel : _LogLevel
        Instance carrying the numeric value for the MESSAGE level.

    Notes
    -----
    Call this once per process before creating loggers that use the MESSAGE level.
    The function is not strictly idempotent in this form, mirroring your current
    behavior.
    """
    # add a logging level called MESSAGE
    def logForLevel(self, message, *args, **kwargs):
        if self.isEnabledFor(LogLevel.message):
            self._log(LogLevel.message, message, args, **kwargs)
        return

    def logToRoot(message, *args, **kwargs):
        logging.log(LogLevel.message, message, *args, **kwargs)
        return

    logging.addLevelName(LogLevel.message, "MESSAGE")
    setattr(logging, "MESSAGE", LogLevel.message)
    setattr(logging.getLoggerClass(), "message", logForLevel)
    setattr(logging, "message", logToRoot)
    return


""" ---------------------------------------------------------------------------- """


class BaseClass():
    """Minimal base class that provides logging, command execution, and file helpers.

    Responsibilities
    ----------------
    - Set up logging with a custom MESSAGE level (25) and optional colorized console output.
    - Provide `print()` wrapper that logs to file or console based on configuration.
    - Offer basic progress bar printing for long-running tasks.
    - Provide small filesystem helpers (create timestamped directories, recursive delete, copy).
    - Provide a convenience `_run_cmd()` wrapper to run external processes.
    - Provide simple network helpers to manage Wi-Fi hotspots via `nmcli`.
    - Export uppercase constants from a source file to a `configuration.txt` in the log directory.

    Notes
    -----
    - The class keeps behavior identical to your current implementation; only
      English docstrings were added for clarity and maintainability.
    """

    def __init__(self):
        """Initialize defaults for logging, colors, and environment flags."""
        self.LogLevel = _LogLevel()
        self.colors = _colors()
        self.color = [
            "red", "blue", "green", "orange", "purple", "brown", "pink", "gray", "olive", "cyan",
            "magenta", "lime", "teal", "gold", "navy", "maroon", "turquoise", "darkgreen", "orchid",
            "indigo", "salmon", "chocolate", "coral", "crimson", "skyblue", "khaki", "plum", "slategray"
        ]
        self._logging = False
        self._logging_level = self.LogLevel.message
        self._logging_file = True
        self._logging_directory = self.get_path()
        self.torch_installed = TORCH_INSTALLED
        self._state = Flag()
        return

    def logging(self, enable, file, level, name, directory: str = None):
        """Configure logging for this instance.

        Parameters
        ----------
        enable : bool
            Enable or disable logging in this instance (controls `print()` behavior).
        file : bool
            If True, write logs to a file; if False, log to console.
        level : int
            Logging level (e.g., logging.INFO, logging.DEBUG, or 25 for MESSAGE).
        name : str
            Base name for the logger and (when `file` is True) the log filename.
        directory : str, optional
            Directory to write log files into (created on demand). If None and
            `file` is True, a `logs/<timestamp>` directory is created in the current
            working directory.
        """
        self._logging = enable
        self._logging_file = file
        self._logging_level = level
        self._set_logging(file=file, level=level, child_name=name, directory=directory)
        return

    def get_time(self):
        """Return a filesystem-friendly timestamp string (YYYY-mm-dd-HH-MM-SS)."""
        # get the current timestamp
        return datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")

    def _get_timestamp(self):
        """Return a human-readable timestamp for inline prints (ms precision)."""
        # timestamp fro logging
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]

    def _set_logging(self, file, level, child_name, directory):
        """Internal helper to initialize logging handlers and formatter.

        Parameters
        ----------
        file : bool
            If True, create a file handler; otherwise a stream handler to stdout.
        level : int
            Logging level for the created logger.
        child_name : str
            Base name for the logger and the log file (if enabled).
        directory : str | None
            Directory for log files. When None and `file` is True, create a new
            timestamped directory under `<cwd>/logs/`.

        Notes
        -----
        - Registers the custom MESSAGE level before creating handlers.
        - When logging to file, an additional colored line is printed to stdout
          for certain levels to maintain visual feedback.
        """
        # set up logging - logs everything into a file by default
        timestamp = self.get_time()
        if file:
            if directory == None:
                self._logging_directory = self.create_directory(self.get_path() + os.sep + "logs")
            else:
                self._logging_directory = directory
                if not os.path.exists(self._logging_directory):
                    os.makedirs(self._logging_directory)
            filename = self._logging_directory + os.sep + child_name + ".log"
        else:
            filename = ""
        _add_log_level(self.LogLevel)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s: %(message)s")
        if filename != "":
            handler = logging.FileHandler(filename)
            self.console = False
        else:
            handler = logging.StreamHandler(sys.stdout)
            self.console = True
        handler.setFormatter(formatter)
        self.logger = logging.getLogger(child_name + "_logger")
        self.logger.setLevel(level)
        self.logger.addHandler(handler)
        self.colors.to_file = file
        return

    """ ---------------------------------------------------------------------------- """

    def print(self, data: str, level: int):
        """Log or print a message with the given log level.

        Parameters
        ----------
        data : str
            Message text to emit.
        level : int
            One of the levels from `self.LogLevel` (e.g., `self.LogLevel.info` or
            `self.LogLevel.message`).

        Notes
        -----
        - When file logging is enabled, the raw message is written to file and an
          extra colored line is printed to console for critical/error/warning/message.
        - When console logging is enabled, ANSI colors are embedded directly into
          the message sent to the logger.
        """
        if self._logging:
            if level == self.LogLevel.debug:
                self.logger.debug(data)
            elif level == self.LogLevel.critical:
                if self.colors.to_file:
                    self.logger.critical(data)
                    print(self._get_timestamp() + " - CRITICAL WARNING: " + self.colors.red + data + self.colors.end)
                else:
                    self.logger.critical(self.colors.red + data + self.colors.end)
            elif level == self.LogLevel.error:
                if self.colors.to_file:
                    self.logger.error(data)
                    print(self._get_timestamp() + " - ERROR: " + self.colors.red + data + self.colors.end)
                else:
                    self.logger.error(self.colors.red + data + self.colors.end)
            elif level == self.LogLevel.warning:
                if self.colors.to_file:
                    self.logger.warning(data)
                    print(self._get_timestamp() + " - WARNING: " + self.colors.yellow + data + self.colors.end)
                else:
                    self.logger.warning(self.colors.yellow + data + self.colors.end)
            elif level == self.LogLevel.info:
                self.logger.info(data)
            elif level == self.LogLevel.message:
                if self.colors.to_file:
                    self.logger.message(data)
                    print(self._get_timestamp() + " - MESSAGE: " + self.colors.green + data + self.colors.end)
                else:
                    self.logger.message(self.colors.green + data + self.colors.end)
        return
        # display a string with a preset logging
    def progress_bar(self, current, total):
        # display a progress bar
        bar_length = 100
        filled_up = int(round(bar_length * current / float(total)))
        percentage = round(100.0 * current / float(total), 1)
        bar = "=" * filled_up + "-" * (bar_length - filled_up)
        sys.stdout.write("\r[" + bar + "] " + str(percentage) + "%\r")
        sys.stdout.flush()
        return
    
    
    """ ---------------------------------------------------------------------------- """
    
    def create_directory(self, root):
        # create a directory named as a timestamp in the root folder, returns the name
        if not os.path.exists(root):
            os.makedirs(root)
        current_time = self.get_time()
        new_path = root + os.sep + current_time
        if not os.path.exists(new_path):
            os.makedirs(new_path)
        return new_path
    
    def delete_directory(self, directory):
        # recursively delete a directory
        if os.path.isfile(directory):
            os.remove(directory)
        else:
            # this is a directory
            subdirs = os.listdir(directory)
            if len(subdirs) == 0:
                os.rmdir(directory) # empty directory
            else:
                for subdir in subdirs:
                    self.delete_directory(directory + os.sep + subdir)
                os.rmdir(directory)
        return
    
    def _check_path(self, directory):
        # check if a directory exists and create it if not
        os.makedirs(directory, exist_ok=True)
        return
    
    def get_path(self):
        # return the absolute path to root
        return os.path.abspath(".")
    
    def _copy(self, source:str, folder:str, name:str):
        # copy a file or folder to another location
        # check if the source is a file or folder
        if os.path.isfile(source):
            extension = source[::-1].split(".", 1)[0][::-1]  # get extension
            self._check_path(folder)    # ensure that the folder exists
            new_name = folder + os.sep + name + "." + extension # get new name
            shutil.copy2(source, new_name)
        else:
            # create a new folder at the destination
            destination = folder + os.sep + name
            self._check_path(destination)
            # copy each member of the folder with the original name
            files = [file for file in os.listdir(source)]
            for file in files:
                name = file[::-1].split(".", 1)[-1][::-1]   # strip extension
                name = name[::-1].split(os.sep, 1)[0][::-1] # strip root directory
                self._copy(source=(source + os.sep + file), folder=destination, name=name)  # copy recursively
        return
    
    """ ---------------------------------------------------------------------------- """
    
    def _run_cmd(self, cmd:str, image_processing=None):
        # run an external command and return the results
        if image_processing:

            #  set environment variables
            env = os.environ.copy()
            env["LD_LIBRARY_PATH"] = ALICE_VISION_ROOT + "/lib:" + env.get("LD_LIBRARY_PATH", "")
            env["ALICEVISION_ROOT"] = ALICE_VISION_ROOT

            self.print("shell: " + cmd, self.LogLevel.debug)
            process = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True, env=env)
        else:
            self.print("shell: " + cmd, self.LogLevel.debug)
            process = Popen(cmd.split(), stdout=PIPE, stderr=PIPE, shell=True)

        stdout, stderr = process.communicate()
        stdout = stdout.decode("UTF-8")
        stderr = stderr.decode("UTF-8")
        if len(stdout) > 0:
            self.print(stdout, self.LogLevel.debug)
        if len(stderr) > 0:
            self.print(stderr, self.LogLevel.debug)
        return stdout, stderr
    
    """ ---------------------------------------------------------------------------- """
    # network configurations
    def get_wifi_interface(self):
        result = subprocess.run(["nmcli", "-t", "-f", "DEVICE,TYPE", "device"], capture_output=True, text=True)
        for line in result.stdout.strip().split("\n"):
            device, dev_type = line.split(":")
            if dev_type == "wifi":
                return device
        return None
    
    def start_hotspot(self, interface, ssid, password):
        result = subprocess.run([
            "nmcli", "dev", "wifi", "hotspot", 
            "ifname" , interface, "ssid", ssid, "password", password
        ], capture_output = True, text = True)
        if result.returncode !=0:
            raise OSError("Error while setting up the WIFI Hotspot")
        else:
            self.print(f"Started hotspot with SSID {ssid} and password {password}", level=LogLevel.message)
    
    def deactivate_hotspot(self):
        result = subprocess.run(["nmcli", "connection", "down", "Hotspot"], capture_output=True, text=True)
        if result.returncode != 0:
            raise OSError("Error occured while trying to deactivate Hotspot")
        else:
            self.print("Closed hotspot successfully", level=LogLevel.message)

        
   
    """ ---------------------------------------------------------------------------- """

            
    def extract_and_store_constants(self, source_file: str):
        """
        Liest eine Datei mit Konstanten ein und speichert alle Konstanten-Zuweisungen als String in eine Textdatei.
        
        Parameter:
            source_file (str): Pfad zur Datei mit den Konstanten (z. B. "config/constants.py").
            output_file (str): Pfad zur Ausgabedatei.
        """
        output_file = self._logging_directory + os.sep + "configuration.txt"
        with open(source_file, "r") as f:
            lines = f.readlines()

        constant_lines = []
        pattern = re.compile(r"^[A-Z_][A-Z0-9_]*\s*=")

        for line in lines:
            if pattern.match(line.strip()):
                constant_lines.append(line.rstrip())

        with open(output_file, "w") as f:
            f.write("# Exportierte Konstanten aus '{}'\n\n".format(source_file))
            f.write("\n".join(constant_lines))

        print(f"{len(constant_lines)} Konstanten wurden gespeichert in '{output_file}'.")
    
        

    
        
        