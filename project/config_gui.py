#!/usr/bin/env python3
"""
Configuration GUI for Crazyflie Project Settings
A modern, user-friendly interface for managing project constants
Daniel Bugelnig, 2026
"""

import sys
import os
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict, Any


class ModernStyle:
    """Modern color scheme and styling constants"""
    BG_DARK = "#1a1a1a"
    BG_MEDIUM = "#252526"
    BG_LIGHT = "#1e1e1e"  # Much darker for better contrast
    ACCENT = "#0e7ade"
    ACCENT_HOVER = "#1e8dd6"
    TEXT_PRIMARY = "#ffffff"  # Pure white for maximum contrast
    TEXT_SECONDARY = "#d4d4d4"  # Brighter secondary text
    TEXT_DISABLED = "#858585"
    SUCCESS = "#4ec9b0"
    WARNING = "#ce9178"
    ERROR = "#f48771"


class ScrollableFrame(ttk.Frame):
    """A scrollable frame widget"""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        
        # Create canvas and scrollbar
        self.canvas = tk.Canvas(self, bg=ModernStyle.BG_MEDIUM, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)
    
    def _on_mousewheel(self, event):
        if event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")


class ConfigGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Crazyflie Configuration Manager")
        self.root.geometry("1400x900")
        
        # Configuration data
        self.config_data = {}
        self.widgets = {}
        self.advanced_mode = tk.BooleanVar(value=False)
        
        # Load current configuration
        self.load_current_config()
        
        # Setup UI
        self.setup_styles()
        self.create_main_layout()
        
    def setup_styles(self):
        """Configure modern ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors with larger fonts
        style.configure(".", background=ModernStyle.BG_MEDIUM, 
                       foreground=ModernStyle.TEXT_PRIMARY,
                       fieldbackground=ModernStyle.BG_LIGHT,
                       font=('Helvetica', 11))
        
        style.configure("TFrame", background=ModernStyle.BG_MEDIUM)
        style.configure("TLabel", background=ModernStyle.BG_MEDIUM, 
                       foreground=ModernStyle.TEXT_PRIMARY,
                       font=('Helvetica', 11))
        style.configure("TButton", background=ModernStyle.ACCENT,
                       foreground=ModernStyle.TEXT_PRIMARY, borderwidth=0,
                       font=('Helvetica', 11, 'bold'), padding=[15, 8])
        style.map("TButton", background=[('active', ModernStyle.ACCENT_HOVER)])
        
        style.configure("TEntry", fieldbackground=ModernStyle.BG_LIGHT,
                       foreground=ModernStyle.TEXT_PRIMARY,
                       insertcolor=ModernStyle.TEXT_PRIMARY,
                       font=('Helvetica', 11))
        
        style.configure("TCombobox", fieldbackground="#0d0d0d",
                       foreground=ModernStyle.TEXT_PRIMARY,
                       selectbackground=ModernStyle.ACCENT,
                       selectforeground=ModernStyle.TEXT_PRIMARY,
                       font=('Helvetica', 11),
                       background="#0d0d0d",
                       arrowcolor=ModernStyle.TEXT_PRIMARY)
        style.map("TCombobox", 
                 fieldbackground=[('readonly', '#0d0d0d')],
                 selectbackground=[('readonly', ModernStyle.ACCENT)],
                 foreground=[('readonly', ModernStyle.TEXT_PRIMARY)])
        
        style.configure("TCheckbutton", background=ModernStyle.BG_MEDIUM,
                       foreground=ModernStyle.TEXT_PRIMARY,
                       font=('Helvetica', 11))
        
        # Scrollbar styling - light grey
        style.configure("TScrollbar", 
                       background="#808080",
                       troughcolor=ModernStyle.BG_MEDIUM,
                       bordercolor=ModernStyle.BG_MEDIUM,
                       arrowcolor=ModernStyle.TEXT_PRIMARY)
        style.map("TScrollbar",
                 background=[('active', '#a0a0a0')])
        
        style.configure("TNotebook", background=ModernStyle.BG_DARK, borderwidth=0)
        style.configure("TNotebook.Tab", background=ModernStyle.BG_LIGHT,
                       foreground=ModernStyle.TEXT_SECONDARY, padding=[20, 12],
                       font=('Helvetica', 11, 'bold'))
        style.map("TNotebook.Tab", background=[('selected', ModernStyle.ACCENT)],
                 foreground=[('selected', ModernStyle.TEXT_PRIMARY)])
        
        style.configure("Header.TLabel", font=('Helvetica', 16, 'bold'))
        style.configure("Section.TLabel", font=('Helvetica', 12, 'bold'),
                       foreground=ModernStyle.ACCENT)
    
    def create_main_layout(self):
        """Create the main window layout"""
        # Header
        header_frame = ttk.Frame(self.root)
        header_frame.pack(fill=tk.X, padx=20, pady=(20, 10))
        
        title_label = ttk.Label(header_frame, text="Crazyflie Project Configuration",
                               style="Header.TLabel")
        title_label.pack(side=tk.LEFT)
        
        # Advanced mode toggle
        advanced_check = ttk.Checkbutton(header_frame, text="Advanced Mode",
                                        variable=self.advanced_mode,
                                        command=self.toggle_advanced_mode)
        advanced_check.pack(side=tk.RIGHT, padx=10)
        
        # Action buttons
        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT)
        
        ttk.Button(btn_frame, text="Save", command=self.save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Load", command=self.load_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Reset", command=self.reset_config).pack(side=tk.LEFT, padx=5)
        
        # Notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Create tabs
        self.create_basic_tab()
        self.create_hardware_tab()
        self.create_positioning_tab()
        self.create_control_tab()
        
        # Footer
        footer_frame = ttk.Frame(self.root)
        footer_frame.pack(fill=tk.X, padx=20, pady=(10, 20))
        
        status_label = ttk.Label(footer_frame, text="Ready", foreground=ModernStyle.SUCCESS)
        status_label.pack(side=tk.LEFT)
        self.status_label = status_label
        
        ttk.Button(footer_frame, text="Apply Configuration",
                  command=self.apply_config).pack(side=tk.RIGHT, padx=5)
    
    def create_basic_tab(self):
        """Basic settings tab"""
        tab = ScrollableFrame(self.notebook)
        self.notebook.add(tab, text="🏠 Basic")
        frame = tab.scrollable_frame
        
        # Operating System
        self.create_section(frame, "Operating System")
        self.create_combobox(frame, "OP_SYSTEM", "Operating System:", 
                           ["Linux", "Windows"], row=1)
        
        # Wi-Fi Settings
        self.create_section(frame, "Wi-Fi Settings", row=3)
        self.create_entry(frame, "WIFI_NAME", "Wi-Fi Network Name:", row=4)
        self.create_entry(frame, "WIFI_PASSWORD", "Wi-Fi Password:", row=5, show="*")
        
        # Camera
        self.create_section(frame, "Camera Settings", row=7)
        self.create_combobox(frame, "CAMERA", "Camera Type:", 
                           ["RGB", "Monochrome"], row=8)
        self.create_checkbox(frame, "DISPLAY_IMAGES", "Display Images", row=9)
        
        # Controller
        self.create_section(frame, "Controller", row=11)
        controller_opts = ["Auto", "PID", "Mellinger", "INDI", "Brescianini", "OOT"]
        self.create_combobox(frame, "CONTROLLER_TYPE", "Controller Type:", 
                           controller_opts, row=12, 
                           help_text="0=Auto, 1=PID, 2=Mellinger, 3=INDI, 4=Brescianini, 5=OOT")
    
    def create_hardware_tab(self):
        """Hardware configuration tab"""
        tab = ScrollableFrame(self.notebook)
        self.notebook.add(tab, text="🔧 Hardware")
        frame = tab.scrollable_frame
        
        # Crazyflies
        self.create_section(frame, "Crazyflie URIs")
        info_label = ttk.Label(frame, 
                              text="Enter one URI per line (e.g., radio://0/90/2M/E7E7E7E701)",
                              foreground=ModernStyle.TEXT_SECONDARY)
        info_label.grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=20, pady=5)
        
        self.create_text(frame, "CRAZYFLIES", "Crazyflie URIs:", row=2, height=8)
        
        # MAC Addresses
        self.create_section(frame, "AI Deck MAC Addresses", row=4)
        info_label_mac = ttk.Label(frame,
                                   text="Format: URI=MAC_ADDRESS (one per line)",
                                   foreground=ModernStyle.TEXT_SECONDARY)
        info_label_mac.grid(row=5, column=0, columnspan=2, sticky=tk.W, padx=20, pady=5)
        
        self.create_text(frame, "MAC_LOOKUP", "MAC Address Mapping:", row=6, height=6)
        
        # Rigid Body IDs
        self.create_section(frame, "Rigid Body IDs (OptiTrack)", row=8)
        info_label2 = ttk.Label(frame,
                               text="Format: URI=ID (one per line)",
                               foreground=ModernStyle.TEXT_SECONDARY)
        info_label2.grid(row=9, column=0, columnspan=2, sticky=tk.W, padx=20, pady=5)
        
        self.create_text(frame, "RIGID_BODY_ID_LOOKUP", "Rigid Body Mapping:", row=10, height=6)
        
        # Battery
        self.create_section(frame, "Battery Parameters", row=12)
        self.create_entry(frame, "LOW_BATTERY", "Low Battery Threshold (V):", row=13)
        self.create_entry(frame, "RATED_CURRENT", "Rated Current (Ah):", row=14)
    
    def create_positioning_tab(self):
        """Positioning system tab"""
        tab = ScrollableFrame(self.notebook)
        self.notebook.add(tab, text="📍 Positioning")
        frame = tab.scrollable_frame
        
        # Positioning System
        self.create_section(frame, "Positioning System")
        self.create_combobox(frame, "POSITIONING_SYSTEM", "System Type:", 
                           ["OptiTrack", "Flow", "Loco"], row=1)
        
        # OptiTrack Settings
        self.create_section(frame, "OptiTrack Configuration", row=3)
        self.create_entry(frame, "CLIENT_IP", "Client IP:", row=4)
        self.create_entry(frame, "SERVER_IP", "Server IP:", row=5)
        self.create_checkbox(frame, "USE_MULTICAST", "Use Multicast", row=6)
        
        # Timing (Advanced)
        self.create_section(frame, "Timing Settings", row=8, advanced=True)
        self.create_entry(frame, "MOCAP_TX_RATE_HZ", "TX Rate (Hz):", row=9, advanced=True)
        self.create_entry(frame, "MOCAP_FRESH_MS", "Fresh Threshold (ms):", row=10, advanced=True)
        self.create_entry(frame, "MOCAP_SETTLE_S", "Settle Time (s):", row=11, advanced=True)
        self.create_entry(frame, "TIMEOUT", "Timeout (s):", row=12, advanced=True)
        
        # Flying Area (Advanced)
        self.create_section(frame, "Flying Area Bounds", row=14, advanced=True)
        info_label2 = ttk.Label(frame,
                              text="Define 8 corner points (A0-A7) of the flying volume\nFormat: x,y,z (one per line)",
                              foreground=ModernStyle.TEXT_SECONDARY)
        info_label2.grid(row=15, column=0, columnspan=2, sticky=tk.W, padx=20, pady=5)
        self.widgets["flying_area_info"] = {"widget": info_label2, "advanced": True}
        info_label2.grid_remove()
        self.create_text(frame, "FLYING_AREA", "Area Coordinates:", row=16, height=10, advanced=True)
    
    def create_control_tab(self):
        """Control parameters tab"""
        tab = ScrollableFrame(self.notebook)
        self.notebook.add(tab, text="🎮 Control")
        frame = tab.scrollable_frame
        
        # Timing
        self.create_section(frame, "Timing")
        self.create_entry(frame, "DRONE_DELAY", "Drone Delay (s):", row=1)
        self.create_entry(frame, "DECK_DELAY", "Deck Delay (s):", row=2)
        
        # Position Thresholds
        self.create_section(frame, "Position Thresholds", row=4)
        self.create_entry(frame, "ARRIVAL_THRESHOLD_DISTANCE", "Distance (m):", row=5)
        self.create_entry(frame, "ARRIVAL_THRESHOLD_ANGLE", "Angle (deg):", row=6)
        self.create_entry(frame, "ARRIVAL_THRESHOLD_DISTANCE_ROUGH", "Rough Distance (m):", row=7)
        self.create_entry(frame, "ARRIVAL_THRESHOLD_ANGLE_ROUGH", "Rough Angle (deg):", row=8)
        self.create_entry(frame, "MAX_ANGLE_STEP", "Max Angle Step (deg):", row=9)
        
        # Potential Field Parameters (Advanced)
        self.create_section(frame, "Potential Field", row=11, advanced=True)
        self.create_entry(frame, "ATTRACTION_FACTOR", "Attraction Factor:", row=12, advanced=True)
        self.create_entry(frame, "REPULSION_FACTOR", "Repulsion Factor:", row=13, advanced=True)
        self.create_entry(frame, "REPULSION_FACTOR_OBJECT", "Object Repulsion:", row=14, advanced=True)
        self.create_entry(frame, "REPULSION_FACTOR_DRONE", "Drone Repulsion:", row=15, advanced=True)
        self.create_entry(frame, "REPULSION_FACTOR_WALL", "Wall Repulsion:", row=16, advanced=True)
        
        # Local Minima (Advanced)
        self.create_section(frame, "Local Minima Handling", row=18, advanced=True)
        self.create_entry(frame, "WINDOW_SIZE", "Window Size:", row=19, advanced=True)
        self.create_entry(frame, "THRESHOLD", "Threshold:", row=20, advanced=True)
        self.create_entry(frame, "RANDOM_WALK_FACTOR", "Random Walk Factor:", row=21, advanced=True)
        
        # Radii (Advanced)
        self.create_section(frame, "Radii", row=23, advanced=True)
        self.create_entry(frame, "OBJECT_RADIUS", "Object Radius (m):", row=24, advanced=True)
        self.create_entry(frame, "DRONE_RADIUS", "Drone Radius (m):", row=25, advanced=True)
        self.create_entry(frame, "WALL_RADIUS", "Wall Radius (m):", row=26, advanced=True)
        self.create_entry(frame, "GOAL_RADIUS", "Goal Radius (m):", row=27, advanced=True)
        
        # Navigation (Advanced)
        self.create_section(frame, "Navigation", row=29, advanced=True)
        self.create_entry(frame, "STEPSIZE", "Step Size:", row=30, advanced=True)
        self.create_entry(frame, "RESOLUTION", "Resolution:", row=31, advanced=True)
        self.create_entry(frame, "SPHERE_POINTS", "Sphere Points:", row=32, advanced=True)
    
    def create_section(self, parent, title, row=0, advanced=False):
        """Create a section header"""
        label = ttk.Label(parent, text=title, style="Section.TLabel")
        label.grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=20, pady=(15, 5))
        if advanced:
            label.grid_remove()
            self.widgets[f"section_{title}"] = {"widget": label, "advanced": True}
    
    def create_entry(self, parent, key, label_text, row=0, show=None, advanced=False):
        """Create a labeled entry widget"""
        label = ttk.Label(parent, text=label_text)
        label.grid(row=row, column=0, sticky=tk.W, padx=20, pady=8)
        
        entry = ttk.Entry(parent, width=45, show=show)
        entry.grid(row=row, column=1, sticky=tk.W, padx=20, pady=8)
        entry.insert(0, str(self.config_data.get(key, "")))
        
        self.widgets[key] = {"widget": entry, "type": "entry", "advanced": advanced, "label": label}
        
        if advanced:
            label.grid_remove()
            entry.grid_remove()
    
    def create_checkbox(self, parent, key, label_text, row=0, advanced=False):
        """Create a checkbox widget"""
        var = tk.BooleanVar(value=self.config_data.get(key, False))
        check = ttk.Checkbutton(parent, text=label_text, variable=var)
        check.grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=20, pady=8)
        
        self.widgets[key] = {"widget": check, "type": "checkbox", "var": var, "advanced": advanced}
        
        if advanced:
            check.grid_remove()
    
    def create_combobox(self, parent, key, label_text, values, row=0, 
                       help_text=None, advanced=False):
        """Create a combobox widget"""
        label = ttk.Label(parent, text=label_text)
        label.grid(row=row, column=0, sticky=tk.W, padx=20, pady=8)
        
        combo = ttk.Combobox(parent, values=values, state="readonly", width=42)
        combo.grid(row=row, column=1, sticky=tk.W, padx=20, pady=8)
        
        # Set current value
        current = self.config_data.get(key, "")
        if isinstance(current, int) and key == "CONTROLLER_TYPE":
            # Map controller type number to name
            controller_map = ["Auto", "PID", "Mellinger", "INDI", "Brescianini", "OOT"]
            if 0 <= current < len(controller_map):
                combo.set(controller_map[current])
        elif current in values:
            combo.set(current)
        elif values:
            combo.set(values[0])
        
        self.widgets[key] = {"widget": combo, "type": "combobox", "advanced": advanced, "label": label}
        
        if help_text:
            help_label = ttk.Label(parent, text=help_text, 
                                  foreground=ModernStyle.TEXT_SECONDARY,
                                  font=('Helvetica', 8))
            help_label.grid(row=row+1, column=1, sticky=tk.W, padx=20)
            if advanced:
                help_label.grid_remove()
                self.widgets[f"{key}_help"] = {"widget": help_label, "advanced": True}
        
        if advanced:
            label.grid_remove()
            combo.grid_remove()
    
    def create_text(self, parent, key, label_text, row=0, height=5, advanced=False):
        """Create a text widget for multi-line input"""
        label = ttk.Label(parent, text=label_text)
        label.grid(row=row, column=0, sticky=tk.NW, padx=20, pady=8)
        
        text_frame = ttk.Frame(parent)
        text_frame.grid(row=row, column=1, sticky=tk.W, padx=20, pady=8)
        
        text = tk.Text(text_frame, width=55, height=height, 
                      bg="#0d0d0d", fg=ModernStyle.TEXT_PRIMARY,
                      insertbackground=ModernStyle.TEXT_PRIMARY,
                      font=('Consolas', 11), relief=tk.FLAT,
                      selectbackground=ModernStyle.ACCENT,
                      selectforeground=ModernStyle.TEXT_PRIMARY,
                      padx=8, pady=8)
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Insert current value
        current = self.config_data.get(key, [])
        if isinstance(current, list):
            # Special handling for FLYING_AREA with State objects
            if key == "FLYING_AREA" and current and hasattr(current[0], 'x'):
                # Convert State objects to x,y,z format
                text.insert("1.0", "\n".join(f"{item.x},{item.y},{item.z}" for item in current))
            else:
                text.insert("1.0", "\n".join(str(item) for item in current))
        elif isinstance(current, dict):
            text.insert("1.0", "\n".join(f"{k}={v}" for k, v in current.items()))
        
        self.widgets[key] = {"widget": text, "type": "text", "advanced": advanced, 
                           "label": label, "parent_frame": text_frame}
        
        if advanced:
            label.grid_remove()
            text_frame.grid_remove()
    
    def toggle_advanced_mode(self):
        """Toggle visibility of advanced parameters"""
        show = self.advanced_mode.get()
        
        for key, widget_data in self.widgets.items():
            if widget_data.get("advanced", False):
                # Handle text widgets (with parent_frame) differently from other widgets
                if "parent_frame" in widget_data:
                    # Text widgets: only show/hide the parent frame and label
                    if show:
                        widget_data["parent_frame"].grid()
                    else:
                        widget_data["parent_frame"].grid_remove()
                    
                    if "label" in widget_data:
                        if show:
                            widget_data["label"].grid()
                        else:
                            widget_data["label"].grid_remove()
                elif key.startswith("section_") or key.endswith("_info"):
                    # Section headers and info labels: just show/hide the widget
                    if show:
                        widget_data["widget"].grid()
                    else:
                        widget_data["widget"].grid_remove()
                else:
                    # Entry, checkbox, combobox widgets: show/hide widget and label
                    if show:
                        widget_data["widget"].grid()
                    else:
                        widget_data["widget"].grid_remove()
                    
                    if "label" in widget_data:
                        if show:
                            widget_data["label"].grid()
                        else:
                            widget_data["label"].grid_remove()
    
    def load_current_config(self):
        """Load configuration from constants.py"""
        try:
            # Add parent directory to path
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from crazyflie import constants
            
            # Extract all uppercase constants
            for attr in dir(constants):
                if attr.isupper():
                    value = getattr(constants, attr)
                    self.config_data[attr] = value
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load configuration:\n{str(e)}")
    
    def get_widget_value(self, key):
        """Get value from a widget"""
        widget_data = self.widgets.get(key)
        if not widget_data:
            return None
        
        widget_type = widget_data["type"]
        widget = widget_data["widget"]
        
        if widget_type == "entry":
            return widget.get()
        elif widget_type == "checkbox":
            return widget_data["var"].get()
        elif widget_type == "combobox":
            value = widget.get()
            # Special handling for controller type
            if key == "CONTROLLER_TYPE":
                controller_map = {"Auto": 0, "PID": 1, "Mellinger": 2, 
                                "INDI": 3, "Brescianini": 4, "OOT": 5}
                return controller_map.get(value, 0)
            return value
        elif widget_type == "text":
            content = widget.get("1.0", tk.END).strip()
            # Parse based on key
            if key == "CRAZYFLIES":
                return [line.strip() for line in content.split("\n") if line.strip()]
            elif key == "RIGID_BODY_ID_LOOKUP":
                result = {}
                for line in content.split("\n"):
                    if "=" in line:
                        uri, rid = line.split("=", 1)
                        result[uri.strip()] = int(rid.strip())
                return result
            elif key == "MAC_LOOKUP":
                result = {}
                for line in content.split("\n"):
                    if "=" in line:
                        uri, mac = line.split("=", 1)
                        result[uri.strip()] = mac.strip()
                return result
            elif key == "FLYING_AREA":
                points = []
                for line in content.split("\n"):
                    if line.strip():
                        try:
                            # Skip lines that don't look like coordinates
                            if ":" in line or "state" in line.lower():
                                continue
                            coords = [float(x.strip()) for x in line.split(",")]
                            if len(coords) == 3:
                                points.append({"x": coords[0], "y": coords[1], "z": coords[2]})
                        except ValueError:
                            # Skip lines that can't be parsed as floats
                            continue
                return points
            return content
        
        return None
    
    def save_config(self):
        """Save configuration to JSON file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            config = {}
            for key in self.widgets.keys():
                if not key.startswith("section_") and not key.endswith("_help") and not key.endswith("_info"):
                    config[key] = self.get_widget_value(key)
            
            try:
                with open(filename, 'w') as f:
                    json.dump(config, f, indent=4)
                self.update_status("Configuration saved successfully", ModernStyle.SUCCESS)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save configuration:\n{str(e)}")
    
    def load_config(self):
        """Load configuration from JSON file"""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r') as f:
                    config = json.load(f)
                
                for key, value in config.items():
                    widget_data = self.widgets.get(key)
                    if widget_data:
                        widget_type = widget_data["type"]
                        widget = widget_data["widget"]
                        
                        if widget_type == "entry":
                            widget.delete(0, tk.END)
                            widget.insert(0, str(value))
                        elif widget_type == "checkbox":
                            widget_data["var"].set(bool(value))
                        elif widget_type == "combobox":
                            if key == "CONTROLLER_TYPE":
                                controller_map = ["Auto", "PID", "Mellinger", 
                                               "INDI", "Brescianini", "OOT"]
                                if 0 <= value < len(controller_map):
                                    widget.set(controller_map[value])
                            else:
                                widget.set(value)
                        elif widget_type == "text":
                            widget.delete("1.0", tk.END)
                            if isinstance(value, list):
                                # Special handling for FLYING_AREA with dict objects
                                if key == "FLYING_AREA" and value and isinstance(value[0], dict):
                                    formatted = "\n".join(f"{point['x']},{point['y']},{point['z']}" for point in value)
                                    widget.insert("1.0", formatted)
                                else:
                                    widget.insert("1.0", "\n".join(str(v) for v in value))
                            elif isinstance(value, dict):
                                widget.insert("1.0", "\n".join(f"{k}={v}" for k, v in value.items()))
                            else:
                                widget.insert("1.0", str(value))
                
                self.update_status("Configuration loaded successfully", ModernStyle.SUCCESS)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load configuration:\n{str(e)}")
    
    def reset_config(self):
        """Reset configuration to defaults"""
        if messagebox.askyesno("Reset Configuration", 
                              "Are you sure you want to reset all values to defaults?"):
            self.load_current_config()
            # Refresh all widgets
            for key, widget_data in self.widgets.items():
                if not key.startswith("section_") and not key.endswith("_help") and not key.endswith("_info"):
                    value = self.config_data.get(key, "")
                    widget_type = widget_data["type"]
                    widget = widget_data["widget"]
                    
                    if widget_type == "entry":
                        widget.delete(0, tk.END)
                        widget.insert(0, str(value))
                    elif widget_type == "checkbox":
                        widget_data["var"].set(bool(value))
                    elif widget_type == "combobox":
                        widget.set(str(value))
                    elif widget_type == "text":
                        widget.delete("1.0", tk.END)
                        if isinstance(value, list):
                            widget.insert("1.0", "\n".join(str(v) for v in value))
                        elif isinstance(value, dict):
                            widget.insert("1.0", "\n".join(f"{k}={v}" for k, v in value.items()))
            
            self.update_status("Configuration reset to defaults", ModernStyle.SUCCESS)
    
    def apply_config(self):
        """Apply configuration by writing to constants.py"""
        if not messagebox.askyesno("Apply Configuration", 
                                   "This will overwrite the constants.py file.\nContinue?"):
            return
        
        try:
            # Collect all values
            config = {}
            for key in self.widgets.keys():
                if not key.startswith("section_") and not key.endswith("_help") and not key.endswith("_info"):
                    config[key] = self.get_widget_value(key)
            
            # Generate Python code
            constants_path = Path(__file__).parent.parent / "crazyflie" / "constants.py"
            
            with open(constants_path, 'w') as f:
                f.write('"""\n')
                f.write('    store constants and settings here\n')
                f.write('        Daniel Bugelnig, 2025 (daniel.bugelnig@aau.at)\n')
                f.write('        Generated by Configuration GUI\n')
                f.write('"""\n\n')
                f.write('from .core.shared_data import State\n\n\n\n')
                f.write('"""        EXPOSED SETTINGS - MODIFY HERE (can be added to UI)        """\n\n')
                
                # Write basic settings
                f.write(f'# operating system\n')
                f.write(f'OP_SYSTEM = "{config.get("OP_SYSTEM", "Linux")}"\n\n')
                
                f.write(f'# Wi-Fi, set the settings of the access point created by the host computer\n')
                f.write(f'WIFI_NAME = "{config.get("WIFI_NAME", "")}"\n')
                f.write(f'WIFI_PASSWORD = "{config.get("WIFI_PASSWORD", "")}"\n\n\n\n\n')
                
                f.write('"""        OTHER CONSTANTS (hardcoded constants, shoudn\'t be changed from one run to another)        """\n')
                f.write('# List all crazyflies here with their URIs\n')
                f.write(f'CRAZYFLIES = {config.get("CRAZYFLIES", [])}\n\n')
                
                f.write('# Lookup table for AI deck MAC addresses and drone addresses\n')
                f.write('MAC = ["-", # placeholder\n')
                f.write('    "78:21:84:7b:0f:58", #1 rgb\n')
                f.write('    "78:21:84:7a:4f:70", #2 rgb\n')
                f.write('    "78:21:84:7a:50:c8", #3 rgb\n')
                f.write('    "78:21:84:7b:0b:8c", #4 mono\n')
                f.write(']\n')
                mac_lookup = config.get("MAC_LOOKUP", {})
                if mac_lookup:
                    f.write('MAC_LOOKUP = {\n')
                    for uri, mac in mac_lookup.items():
                        f.write(f'    "{uri}": "{mac}",\n')
                    f.write('}\n\n')
                else:
                    f.write('MAC_LOOKUP = {}\n\n')
                
                f.write(f'RIGID_BODY_ID_LOOKUP = {config.get("RIGID_BODY_ID_LOOKUP", {})}\n\n')
                
                # Positioning system
                f.write('# Positioning system settings\n')
                f.write(f'POSITIONING_SYSTEM = "{config.get("POSITIONING_SYSTEM", "OptiTrack")}"\n')
                f.write(f'CLIENT_IP = "{config.get("CLIENT_IP", "")}"\n')
                f.write(f'SERVER_IP = "{config.get("SERVER_IP", "")}"\n')
                f.write(f'USE_MULTICAST = {config.get("USE_MULTICAST", True)}\n\n')
                
                f.write(f'MOCAP_TX_RATE_HZ = {config.get("MOCAP_TX_RATE_HZ", 100)}\n')
                f.write(f'MOCAP_FRESH_MS = {config.get("MOCAP_FRESH_MS", 150)}\n')
                f.write(f'MOCAP_SETTLE_S = {config.get("MOCAP_SETTLE_S", 1.0)}\n')
                f.write(f'TIMEOUT = {config.get("TIMEOUT", 5)}\n\n')
                
                # Controller
                f.write(f'CONTROLLER_TYPE = {config.get("CONTROLLER_TYPE", 1)}\n\n')
                
                # Paths
                meshroom = config.get("MESHROOM_ROOT", "")
                alice = config.get("ALICE_VISION_ROOT", "")
                f.write(f'MESHROOM_ROOT = "{meshroom}"\n')
                f.write(f'ALICE_VISION_ROOT = "{alice}"\n\n')
                
                # Flying area
                flying_area = config.get("FLYING_AREA", [])
                f.write('FLYING_AREA = [')
                for i, point in enumerate(flying_area):
                    if isinstance(point, dict):
                        f.write(f'State(x={point.get("x", 0)}, y={point.get("y", 0)}, z={point.get("z", 0)})')
                    if i < len(flying_area) - 1:
                        f.write(', ')
                f.write(']\n\n')
                
                # Port (keep for backwards compatibility)
                f.write(f'WIFI_SOCKET_PORT = {config.get("WIFI_SOCKET_PORT", 5000)}\n\n')
                
                # Other constants
                numeric_keys = [
                    "LOW_BATTERY", "RATED_CURRENT",
                    "MAX_ANGLE_STEP", "ARRIVAL_THRESHOLD_DISTANCE", "ARRIVAL_THRESHOLD_ANGLE",
                    "ARRIVAL_THRESHOLD_DISTANCE_ROUGH", "ARRIVAL_THRESHOLD_ANGLE_ROUGH",
                    "POSITION_AVERAGE", "DRONE_DELAY", "DECK_DELAY",
                    "REPULSION_FACTOR", "ATTRACTION_FACTOR", "REPULSION_FACTOR_OBJECT",
                    "REPULSION_FACTOR_DRONE", "REPULSION_FACTOR_WALL",
                    "OBJECT_RADIUS", "WALL_RADIUS", "DRONE_RADIUS", "GOAL_RADIUS",
                    "OBJECT_NUMBER", "LINE_NUMBER", "GOAL_POSITIONS",
                    "SPHERE_POINTS", "STEPSIZE", "RESOLUTION",
                    "WINDOW_SIZE", "THRESHOLD", "RANDOM_WALK_FACTOR", "FILTER_FACTOR",
                    "EVALUATION_VOXEL_SIZE", "EVALUATION_SAMPLE_COUNT",
                    "EVALUATION_MAX_ITERATIONS", "EVALUATION_THRESHOLD",
                    "EVALUATION_RENDER_COUNT"
                ]
                
                for key in numeric_keys:
                    if key in config:
                        value = config[key]
                        try:
                            # Try to convert to number
                            if '.' in str(value):
                                value = float(value)
                            else:
                                value = int(value)
                        except:
                            pass
                        f.write(f'{key} = {value}\n')
                
                # String keys
                f.write(f'\nCAMERA = "{config.get("CAMERA", "RGB")}"\n')
                
                # Boolean keys
                bool_keys = ["DISPLAY_IMAGES", "EVALUATION_SAVE_PICTURES"]
                for key in bool_keys:
                    if key in config:
                        f.write(f'{key} = {config.get(key, False)}\n')
            
            self.update_status("Configuration applied successfully!", ModernStyle.SUCCESS)
            messagebox.showinfo("Success", "Configuration has been written to constants.py")
            
        except Exception as e:
            self.update_status("Error applying configuration", ModernStyle.ERROR)
            messagebox.showerror("Error", f"Failed to apply configuration:\n{str(e)}")
    
    def update_status(self, message, color=None):
        """Update status label"""
        self.status_label.config(text=message)
        if color:
            self.status_label.config(foreground=color)
        self.root.update_idletasks()


def main():
    root = tk.Tk()
    root.configure(bg=ModernStyle.BG_DARK)
    app = ConfigGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()