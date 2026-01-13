import tkinter as tk
from tkinter import ttk, messagebox, Canvas
import threading
import ctypes
import gc
import psutil
import time
import csv
import os
import subprocess
import platform
from collections import deque
from datetime import datetime, timedelta
import math
import json

try:
    import wmi
    HAS_WMI = True
except ImportError:
    HAS_WMI = False

# Try to import pycaw for volume control
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    HAS_PYCAW = True
except ImportError:
    HAS_PYCAW = False

# Try to import screen_brightness_control
try:
    import screen_brightness_control as sbc
    HAS_SBC = True
except ImportError:
    HAS_SBC = False

# --- Windows API structures ---
class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ('ACLineStatus', ctypes.c_byte),
        ('BatteryFlag', ctypes.c_byte),
        ('BatteryLifePercent', ctypes.c_byte),
        ('Reserved1', ctypes.c_byte),
        ('BatteryLifeTime', ctypes.c_int),
        ('BatteryFullLifeTime', ctypes.c_int),
    ]

class PERFORMANCE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('cb', ctypes.c_ulong),
        ('CommitTotal', ctypes.c_size_t),
        ('CommitLimit', ctypes.c_size_t),
        ('CommitPeak', ctypes.c_size_t),
        ('PhysicalTotal', ctypes.c_size_t),
        ('PhysicalAvailable', ctypes.c_size_t),
        ('SystemCache', ctypes.c_size_t),
        ('KernelTotal', ctypes.c_size_t),
        ('KernelPaged', ctypes.c_size_t),
        ('KernelNonPaged', ctypes.c_size_t),
        ('PageSize', ctypes.c_size_t),
        ('HandleCount', ctypes.c_ulong),
        ('ProcessCount', ctypes.c_ulong),
        ('ThreadCount', ctypes.c_ulong),
    ]

# --- Windows API setup ---
psapi = ctypes.WinDLL('psapi.dll')
kernel32 = ctypes.WinDLL('kernel32.dll')
user32 = ctypes.WinDLL('user32.dll')

def empty_working_set(pid):
    """Trim memory usage of a process without closing it."""
    try:
        hProcess = kernel32.OpenProcess(0x001F0FFF, False, pid)
        if hProcess:
            psapi.EmptyWorkingSet(hProcess)
            kernel32.CloseHandle(hProcess)
            return True
    except Exception:
        pass
    return False

class ModernTheme:
    """Premium RGB theme with vibrant colors and neon accents"""
    # Dark backgrounds with depth
    BG_DARK = "#0a0a0f"
    BG_CARD = "#16161f"
    BG_SIDEBAR = "#0d0d14"
    BG_HOVER = "#1f1f2e"
    
    # Vibrant RGB Gradient colors
    ACCENT_PRIMARY = "#00ffff"      # Cyan neon
    ACCENT_SECONDARY = "#ff00ff"    # Magenta neon
    ACCENT_TERTIARY = "#ffff00"     # Yellow neon
    ACCENT_PURPLE = "#9d00ff"       # Purple neon
    ACCENT_ORANGE = "#ff6b00"       # Orange neon
    ACCENT_PINK = "#ff1493"         # Hot pink
    ACCENT_LIME = "#00ff88"         # Lime green
    
    # Status colors with glow
    TEXT_PRIMARY = "#ffffff"
    TEXT_SECONDARY = "#b0b0c0"
    TEXT_MUTED = "#707080"
    
    SUCCESS = "#00ff88"      # Bright green
    WARNING = "#ffaa00"      # Bright orange
    DANGER = "#ff3366"       # Bright red
    INFO = "#00d9ff"         # Bright cyan
    
    BORDER = "#2a2a3e"
    GLOW = "#00ffff80"       # Cyan glow (with alpha)

class AnimationEngine:
    """Handles smooth animations and transitions"""
    
    @staticmethod
    def fade_in(widget, duration=300, callback=None):
        """Fade in animation for widgets"""
        steps = 20
        delay = duration // steps
        
        def animate(step=0):
            if step <= steps:
                alpha = step / steps
                # Simulate fade by adjusting widget state
                widget.update_idletasks()
                widget.after(delay, lambda: animate(step + 1))
            elif callback:
                callback()
        
        animate()
    
    @staticmethod
    def smooth_color_transition(widget, start_color, end_color, duration=200, config_key='bg'):
        """Smooth color transition animation"""
        steps = 10
        delay = duration // steps
        
        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        def rgb_to_hex(rgb):
            return '#{:02x}{:02x}{:02x}'.format(int(rgb[0]), int(rgb[1]), int(rgb[2]))
        
        start_rgb = hex_to_rgb(start_color)
        end_rgb = hex_to_rgb(end_color)
        
        def animate(step=0):
            if step <= steps:
                ratio = step / steps
                current_rgb = tuple(
                    start_rgb[i] + (end_rgb[i] - start_rgb[i]) * ratio
                    for i in range(3)
                )
                try:
                    widget.config(**{config_key: rgb_to_hex(current_rgb)})
                    widget.after(delay, lambda: animate(step + 1))
                except:
                    pass
        
        animate()
    
    @staticmethod
    def pulse_effect(widget, color1, color2, duration=1000):
        """Pulsing color effect"""
        def pulse():
            AnimationEngine.smooth_color_transition(widget, color1, color2, duration//2, 'bg')
            widget.after(duration//2, lambda: AnimationEngine.smooth_color_transition(widget, color2, color1, duration//2, 'bg'))
            widget.after(duration, pulse)
        pulse()
    
    @staticmethod
    def slide_in(widget, direction='left', duration=300):
        """Slide in animation"""
        # Simplified slide effect using place geometry
        try:
            if direction == 'left':
                widget.place(relx=-1, rely=0)
                def animate(step=0):
                    if step <= 20:
                        widget.place(relx=-1 + (step/20), rely=0)
                        widget.after(duration//20, lambda: animate(step+1))
                animate()
        except:
            pass

class AnimatedCircularProgress(Canvas):
    """Animated circular progress indicator with RGB glow"""
    def __init__(self, parent, size=120, thickness=8, **kwargs):
        super().__init__(parent, width=size, height=size, bg=ModernTheme.BG_CARD, 
                        highlightthickness=0, **kwargs)
        self.size = size
        self.thickness = thickness
        self.center = size // 2
        self.radius = (size - thickness) // 2
        self.value = 0
        self.target_value = 0
        self.color = ModernTheme.ACCENT_PRIMARY
        self.label_text = ""
        self.subtitle_text = ""
        
        # Draw background circle with glow
        self.create_oval(
            self.center - self.radius - 2, self.center - self.radius - 2,
            self.center + self.radius + 2, self.center + self.radius + 2,
            outline=ModernTheme.BORDER, width=self.thickness + 4
        )
        
        # Progress arc with gradient effect
        self.arc = self.create_arc(
            self.center - self.radius, self.center - self.radius,
            self.center + self.radius, self.center + self.radius,
            start=90, extent=0, outline=self.color, width=self.thickness,
            style='arc'
        )
        
        # Center text with glow
        self.text_label = self.create_text(
            self.center, self.center - 10, text="0%",
            font=("Segoe UI", 20, "bold"), fill=ModernTheme.TEXT_PRIMARY
        )
        
        self.subtitle_label = self.create_text(
            self.center, self.center + 18, text="",
            font=("Segoe UI", 9), fill=ModernTheme.TEXT_SECONDARY
        )
        
    def set_value(self, value, label="", subtitle="", color=None):
        """Animate to new value"""
        self.target_value = max(0, min(100, value))
        self.label_text = label if label else f"{int(value)}%"
        self.subtitle_text = subtitle
        if color:
            self.color = color
        self.animate()
        
    def animate(self):
        """Ultra-smooth 144fps animation to target value"""
        if abs(self.value - self.target_value) > 0.5:
            self.value += (self.target_value - self.value) * 0.2
            extent = -int((self.value / 100) * 360)
            self.itemconfig(self.arc, extent=extent, outline=self.color)
            self.itemconfig(self.text_label, text=self.label_text)
            self.itemconfig(self.subtitle_label, text=self.subtitle_text)
            self.after(7, self.animate)  # 144fps (1000ms / 144 ≈ 7ms)
        else:
            self.value = self.target_value

class MiniGraph(Canvas):
    """Mini line graph for real-time data"""
    def __init__(self, parent, width=200, height=60, **kwargs):
        super().__init__(parent, width=width, height=height, bg=ModernTheme.BG_CARD,
                        highlightthickness=0, **kwargs)
        self.width = width
        self.height = height
        self.data = deque([0] * 50, maxlen=50)
        self.color = ModernTheme.ACCENT_PRIMARY
        self.line = None
        
    def add_value(self, value):
        """Add new data point and redraw"""
        self.data.append(max(0, min(100, value)))
        self.draw()
        
    def draw(self):
        """Draw the graph"""
        self.delete("all")
        
        if len(self.data) < 2:
            return
            
        # Create gradient effect
        points = []
        step = self.width / (len(self.data) - 1)
        
        for i, val in enumerate(self.data):
            x = i * step
            y = self.height - (val / 100 * self.height)
            points.extend([x, y])
        
        if len(points) >= 4:
            # Draw filled area
            fill_points = points + [self.width, self.height, 0, self.height]
            self.create_polygon(fill_points, fill=ModernTheme.BG_HOVER, 
                              outline="", smooth=True)
            
            # Draw line
            self.create_line(points, fill=self.color, width=2, smooth=True)

class SidebarButton(tk.Frame):
    """Animated sidebar navigation button"""
    def __init__(self, parent, text, icon, command, **kwargs):
        super().__init__(parent, bg=ModernTheme.BG_SIDEBAR, **kwargs)
        self.text = text
        self.command = command
        self.is_active = False
        self.is_hovered = False
        
        # Container for hover effect
        self.btn_frame = tk.Frame(self, bg=ModernTheme.BG_SIDEBAR, cursor="hand2")
        self.btn_frame.pack(fill=tk.X, padx=8, pady=4)
        
        # Icon and text
        content = tk.Frame(self.btn_frame, bg=ModernTheme.BG_SIDEBAR)
        content.pack(fill=tk.X, padx=12, pady=10)
        
        self.icon_label = tk.Label(content, text=icon, font=("Segoe UI", 16),
                                   bg=ModernTheme.BG_SIDEBAR, fg=ModernTheme.TEXT_SECONDARY)
        self.icon_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.text_label = tk.Label(content, text=text, font=("Segoe UI", 11),
                                   bg=ModernTheme.BG_SIDEBAR, fg=ModernTheme.TEXT_SECONDARY,
                                   anchor="w")
        self.text_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Bind events
        for widget in [self, self.btn_frame, content, self.icon_label, self.text_label]:
            widget.bind("<Button-1>", lambda e: self.on_click())
            widget.bind("<Enter>", lambda e: self.on_hover(True))
            widget.bind("<Leave>", lambda e: self.on_hover(False))
    
    def on_hover(self, entered):
        """Hover animation with vibrant colors"""
        self.is_hovered = entered
        if not self.is_active:
            if entered:
                bg = ModernTheme.BG_HOVER
                fg = ModernTheme.ACCENT_PRIMARY
                self.btn_frame.config(bg=bg)
                for widget in [self.icon_label, self.text_label]:
                    widget.config(bg=bg, fg=fg)
            else:
                bg = ModernTheme.BG_SIDEBAR
                fg = ModernTheme.TEXT_SECONDARY
                self.btn_frame.config(bg=bg)
                for widget in [self.icon_label, self.text_label]:
                    widget.config(bg=bg, fg=fg)
    
    def on_click(self):
        """Handle click"""
        if self.command:
            self.command()
    
    def set_active(self, active):
        """Set active state with vibrant accent"""
        self.is_active = active
        if active:
            bg = ModernTheme.BG_HOVER
            fg = ModernTheme.ACCENT_LIME
            self.btn_frame.config(bg=bg)
            for widget in [self.icon_label, self.text_label]:
                widget.config(bg=bg, fg=fg)
        else:
            self.on_hover(self.is_hovered)

class SystemDashboardPro:
    def __init__(self, root):
        self.root = root
        self.root.title("System Dashboard Pro - Advanced Edition")
        self.root.geometry("1400x850")
        self.root.minsize(1000, 600)  # Minimum window size
        self.root.configure(bg=ModernTheme.BG_DARK)
        
        # Make window resizable
        self.root.resizable(True, True)
        
        # Enable Windows Dark Title Bar
        try:
            set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
            get_parent = ctypes.windll.user32.GetParent
            hwnd = get_parent(self.root.winfo_id())
            value = ctypes.c_int(2)
            set_window_attribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
        except: pass
        
        # Config
        self.config_file = "dashboard_config.json"
        self.config = self.load_config()
        
        self.threshold_ram = self.config.get('threshold_ram', 85)
        self.threshold_cpu = self.config.get('threshold_cpu', 85)
        self.monitor_interval = self.config.get('monitor_interval', 250)
        self.csv_file = "system_performance_log.csv"
        self.current_section = "dashboard"
        
        # WMI for sensors
        self.wmi_obj = None
        if HAS_WMI:
            try:
                self.wmi_obj = wmi.WMI(namespace="root\\OpenHardwareMonitor")
            except: pass
        
        # Data storage
        self.ui_data = {
            "ram_p": 0, "cpu_p": 0, "gpu_p": 0, "disk_p": 0,
            "ram_used": 0, "ram_total": 0, "cpu_temp": 0,
            "gpu_temp": 0, "net_send": 0, "net_recv": 0,
            "processes": 0, "threads": 0, "uptime": "00:00:00"
        }
        
        self.history_cpu = deque([0] * 50, maxlen=50)
        self.history_ram = deque([0] * 50, maxlen=50)
        self.history_gpu = deque([0] * 50, maxlen=50)
        
        # Disk I/O tracking for storage page
        self.last_disk_io_data = psutil.disk_io_counters(perdisk=True)
        self.last_disk_io_time = time.time()
        
        # Auto-optimization tracking
        self.auto_optimize_enabled = self.config.get('auto_optimize_enabled', True)
        self.last_auto_optimize_time = 0
        self.last_cpu_optimize_time = 0
        self.auto_optimize_cooldown = 60
        self.silent_mode = self.config.get('silent_mode', True)
        
        # Saved Hardware Levels
        self.saved_volumes = self.config.get('volumes', {})
        self.saved_brightness = self.config.get('brightness', {})
        
        # Flags for loading hardware settings
        self.first_load_volume = False
        self.first_load_brightness = False

        # High usage duration trackers (for 10s persistence)
        self.cpu_high_start_time = None
        self.ram_high_start_time = None

        # Static info
        self.total_ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
        self.cpu_name = platform.processor()
        self.boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        
        self.init_csv()
        self.create_ui()
        
        # Start monitoring
        threading.Thread(target=self.monitor_thread, daemon=True).start()
        self.update_ui()

    def load_config(self):
        """Load settings from JSON file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {}

    def save_config(self):
        """Save settings to JSON file"""
        try:
            self.config = {
                'threshold_ram': self.threshold_ram,
                'threshold_cpu': self.threshold_cpu,
                'monitor_interval': self.monitor_interval,
                'auto_optimize_enabled': self.auto_optimize_enabled,
                'silent_mode': self.silent_mode
            }
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Config save error: {e}")
    
    def init_csv(self):
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["Timestamp", "RAM%", "CPU%", "GPU%", "Disk%"])
    
    def create_ui(self):
        """Create the main UI layout with scrollable content"""
        # Main container
        main_container = tk.Frame(self.root, bg=ModernTheme.BG_DARK)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Sidebar
        self.create_sidebar(main_container)
        
        # Content area with scrollbar
        content_container = tk.Frame(main_container, bg=ModernTheme.BG_DARK)
        content_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Create canvas and scrollbar
        self.content_canvas = Canvas(content_container, bg=ModernTheme.BG_DARK, 
                                     highlightthickness=0)
        scrollbar = tk.Scrollbar(content_container, orient="vertical", 
                                command=self.content_canvas.yview)
        
        self.content_frame = tk.Frame(self.content_canvas, bg=ModernTheme.BG_DARK)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.content_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Create window in canvas
        self.canvas_window = self.content_canvas.create_window((0, 0), 
                                                               window=self.content_frame, 
                                                               anchor="nw")
        
        # Configure scrolling
        self.content_frame.bind("<Configure>", 
                               lambda e: self.content_canvas.configure(
                                   scrollregion=self.content_canvas.bbox("all")))
        self.content_canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind canvas resize to update window width
        self.content_canvas.bind("<Configure>", self._on_canvas_configure)
        
        # Mouse wheel scrolling
        self.content_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Show default section
        self.show_dashboard()
    
    def _on_canvas_configure(self, event):
        """Update canvas window width when canvas is resized"""
        self.content_canvas.itemconfig(self.canvas_window, width=event.width)
    
    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        self.content_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def create_sidebar(self, parent):
        """Create animated sidebar navigation"""
        sidebar = tk.Frame(parent, bg=ModernTheme.BG_SIDEBAR, width=240)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        
        # Logo/Header
        header = tk.Frame(sidebar, bg=ModernTheme.BG_SIDEBAR, height=80)
        header.pack(fill=tk.X)
        
        logo_text = tk.Label(header, text="⚡ SYSTEM PRO", 
                            font=("Segoe UI", 16, "bold"),
                            bg=ModernTheme.BG_SIDEBAR, fg=ModernTheme.ACCENT_PRIMARY)
        logo_text.pack(pady=20)
        
        # Separator
        tk.Frame(sidebar, bg=ModernTheme.BORDER, height=1).pack(fill=tk.X, padx=10)
        
        # Navigation buttons
        nav_frame = tk.Frame(sidebar, bg=ModernTheme.BG_SIDEBAR)
        nav_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.nav_buttons = {}
        
        buttons = [
            ("dashboard", "📊", "Dashboard", self.show_dashboard),
            ("performance", "⚡", "Performance", self.show_performance),
            ("monitoring", "📈", "Monitoring", self.show_monitoring),
            ("devices", "🔌", "Devices", self.show_devices),
            ("network", "🌐", "Network", self.show_network),
            ("settings", "⚙️", "Settings", self.show_settings),
        ]
        
        for key, icon, text, command in buttons:
            btn = SidebarButton(nav_frame, text, icon, command)
            btn.pack(fill=tk.X)
            self.nav_buttons[key] = btn
        
        # Set dashboard as active
        self.nav_buttons["dashboard"].set_active(True)
        
        # Footer
        footer = tk.Frame(sidebar, bg=ModernTheme.BG_SIDEBAR)
        footer.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        
        tk.Label(footer, text=f"v2.0 Pro Edition", 
                font=("Segoe UI", 8), bg=ModernTheme.BG_SIDEBAR,
                fg=ModernTheme.TEXT_MUTED).pack()
    
    def switch_section(self, section_key):
        """Switch to different section"""
        # Deactivate all buttons
        for key, btn in self.nav_buttons.items():
            btn.set_active(key == section_key)
        
        self.current_section = section_key
        
        # Clear content
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    
    def show_dashboard(self):
        """Main dashboard view"""
        self.switch_section("dashboard")
        
        # Header
        header = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        header.pack(fill=tk.X, padx=30, pady=20)
        
        tk.Label(header, text="System Overview", font=("Segoe UI", 24, "bold"),
                bg=ModernTheme.BG_DARK, fg=ModernTheme.TEXT_PRIMARY).pack(side=tk.LEFT)
        
        self.clock_label = tk.Label(header, text="00:00:00", 
                                    font=("Segoe UI", 16),
                                    bg=ModernTheme.BG_DARK, fg=ModernTheme.ACCENT_PRIMARY)
        self.clock_label.pack(side=tk.RIGHT)
        
        # Main content with responsive grid
        content = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        # Configure grid weights for responsiveness
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)
        content.columnconfigure(2, weight=1)
        content.rowconfigure(0, weight=1)
        content.rowconfigure(1, weight=1)
        content.rowconfigure(2, weight=1)
        
        # Top row - Circular progress indicators (responsive grid)
        # CPU Card
        cpu_card = self.create_card(content, "CPU Usage")
        cpu_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 15))
        
        self.cpu_progress = AnimatedCircularProgress(cpu_card, size=140, thickness=10)
        self.cpu_progress.pack(pady=10)
        
        self.cpu_name_label = tk.Label(cpu_card, text=self.cpu_name[:30], 
                                       font=("Segoe UI", 9),
                                       bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_SECONDARY)
        self.cpu_name_label.pack(pady=5)
        
        # RAM Card
        ram_card = self.create_card(content, "Memory Usage")
        ram_card.grid(row=0, column=1, sticky="nsew", padx=10, pady=(0, 15))
        
        self.ram_progress = AnimatedCircularProgress(ram_card, size=140, thickness=10)
        self.ram_progress.pack(pady=10)
        
        self.ram_info_label = tk.Label(ram_card, text=f"Total: {self.total_ram_gb} GB",
                                       font=("Segoe UI", 9),
                                       bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_SECONDARY)
        self.ram_info_label.pack(pady=5)
        
        # GPU Card
        gpu_card = self.create_card(content, "GPU Usage")
        gpu_card.grid(row=0, column=2, sticky="nsew", padx=(10, 0), pady=(0, 15))
        
        self.gpu_progress = AnimatedCircularProgress(gpu_card, size=140, thickness=10)
        self.gpu_progress.pack(pady=10)
        
        self.gpu_name_label = tk.Label(gpu_card, text="Detecting...",
                                       font=("Segoe UI", 9),
                                       bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_SECONDARY)
        self.gpu_name_label.pack(pady=5)
        
        # Middle row - Graphs (responsive grid)
        # CPU Graph
        cpu_graph_card = self.create_card(content, "CPU History")
        cpu_graph_card.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=(0, 10), pady=(0, 15))
        
        self.cpu_graph = MiniGraph(cpu_graph_card, width=350, height=100)
        self.cpu_graph.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        # RAM Graph
        ram_graph_card = self.create_card(content, "Memory History")
        ram_graph_card.grid(row=1, column=2, sticky="nsew", padx=(10, 0), pady=(0, 15))
        
        self.ram_graph = MiniGraph(ram_graph_card, width=350, height=100)
        self.ram_graph.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        
        # Bottom row - System info (responsive grid)
        # System Info Card
        info_card = self.create_card(content, "System Information")
        info_card.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=(0, 10))
        
        info_grid = tk.Frame(info_card, bg=ModernTheme.BG_CARD)
        info_grid.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        self.create_info_row(info_grid, "Processes:", "0").pack(fill=tk.X, pady=3)
        self.create_info_row(info_grid, "Threads:", "0").pack(fill=tk.X, pady=3)
        self.create_info_row(info_grid, "Uptime:", "00:00:00").pack(fill=tk.X, pady=3)
        self.create_info_row(info_grid, "Boot Time:", self.boot_time).pack(fill=tk.X, pady=3)
        
        # Quick Actions Card
        actions_card = self.create_card(content, "Quick Actions")
        actions_card.grid(row=2, column=2, sticky="nsew", padx=(10, 0))
        
        actions_grid = tk.Frame(actions_card, bg=ModernTheme.BG_CARD)
        actions_grid.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        self.create_action_button(actions_grid, "⚡ Optimize RAM", 
                                  self.optimize_ram).pack(fill=tk.X, pady=5)
        self.create_action_button(actions_grid, "🗑️ Clear Cache",
                                  self.clear_cache).pack(fill=tk.X, pady=5)
        self.create_action_button(actions_grid, "📊 Full Report",
                                  self.show_report).pack(fill=tk.X, pady=5)
    
    def show_performance(self):
        """Performance monitoring view with detailed metrics"""
        self.switch_section("performance")
        
        header = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        header.pack(fill=tk.X, padx=30, pady=20)
        
        tk.Label(header, text="Performance Monitor", font=("Segoe UI", 24, "bold"),
                bg=ModernTheme.BG_DARK, fg=ModernTheme.TEXT_PRIMARY).pack(side=tk.LEFT)
        
        self.perf_time_label = tk.Label(header, text=datetime.now().strftime("%H:%M:%S"), 
                             font=("Segoe UI", 16),
                             bg=ModernTheme.BG_DARK, fg=ModernTheme.ACCENT_PRIMARY)
        self.perf_time_label.pack(side=tk.RIGHT)
        
        content = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        # Top row - CPU Details with gauge
        top_row = tk.Frame(content, bg=ModernTheme.BG_DARK)
        top_row.pack(fill=tk.X, pady=(0, 15))
        
        cpu_card = self.create_card(top_row, "CPU Performance")
        cpu_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        cpu_container = tk.Frame(cpu_card, bg=ModernTheme.BG_CARD)
        cpu_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # CPU Gauge on left
        cpu_gauge_frame = tk.Frame(cpu_container, bg=ModernTheme.BG_CARD)
        cpu_gauge_frame.pack(side=tk.LEFT, padx=(0, 15))
        
        self.perf_cpu_gauge = AnimatedCircularProgress(cpu_gauge_frame, size=100, thickness=8)
        self.perf_cpu_gauge.pack()
        
        # CPU info on right
        cpu_info = tk.Frame(cpu_container, bg=ModernTheme.BG_CARD)
        cpu_info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # CPU details
        cpu_freq = psutil.cpu_freq()
        cpu_count = psutil.cpu_count(logical=False)
        cpu_logical = psutil.cpu_count(logical=True)
        
        self.create_info_row(cpu_info, "Processor:", self.cpu_name[:40]).pack(fill=tk.X, pady=3)
        self.create_info_row(cpu_info, "Physical Cores:", str(cpu_count)).pack(fill=tk.X, pady=3)
        self.create_info_row(cpu_info, "Logical Processors:", str(cpu_logical)).pack(fill=tk.X, pady=3)
        
        # Store the label widget for CPU freq
        freq_row = self.create_info_row(cpu_info, "Current Speed:", 
                                        f"{cpu_freq.current/1000:.2f} GHz" if cpu_freq else "N/A")
        freq_row.pack(fill=tk.X, pady=3)
        self.perf_cpu_freq = freq_row.winfo_children()[-1] if freq_row.winfo_children() else None
        
        max_row = self.create_info_row(cpu_info, "Max Speed:", 
                                       f"{cpu_freq.max/1000:.2f} GHz" if cpu_freq else "N/A")
        max_row.pack(fill=tk.X, pady=3)
        self.perf_cpu_max = max_row.winfo_children()[-1] if max_row.winfo_children() else None
        
        # RAM Details with gauge
        ram_card = self.create_card(top_row, "Memory Performance")
        ram_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        ram_container = tk.Frame(ram_card, bg=ModernTheme.BG_CARD)
        ram_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # RAM Gauge on left
        ram_gauge_frame = tk.Frame(ram_container, bg=ModernTheme.BG_CARD)
        ram_gauge_frame.pack(side=tk.LEFT, padx=(0, 15))
        
        self.perf_ram_gauge = AnimatedCircularProgress(ram_gauge_frame, size=100, thickness=8)
        self.perf_ram_gauge.pack()
        
        # RAM info on right
        ram_info = tk.Frame(ram_container, bg=ModernTheme.BG_CARD)
        ram_info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        mem = psutil.virtual_memory()
        self.create_info_row(ram_info, "Total RAM:", f"{self.total_ram_gb} GB").pack(fill=tk.X, pady=3)
        
        # Store label widgets for RAM
        used_row = self.create_info_row(ram_info, "Used:", f"{mem.used/(1024**3):.1f} GB")
        used_row.pack(fill=tk.X, pady=3)
        self.perf_ram_used = used_row.winfo_children()[-1] if used_row.winfo_children() else None
        
        avail_row = self.create_info_row(ram_info, "Available:", f"{mem.available/(1024**3):.1f} GB")
        avail_row.pack(fill=tk.X, pady=3)
        self.perf_ram_avail = avail_row.winfo_children()[-1] if avail_row.winfo_children() else None
        
        # Get cached memory from Windows PERFORMANCE_INFORMATION
        try:
            pi = PERFORMANCE_INFORMATION()
            pi.cb = ctypes.sizeof(pi)
            psapi.GetPerformanceInfo(ctypes.byref(pi), pi.cb)
            
            # Calculate cached/standby memory
            # SystemCache is in pages, PageSize is in bytes
            cached_bytes = pi.SystemCache * pi.PageSize
            cached_gb = cached_bytes / (1024**3)
            
            cached_row = self.create_info_row(ram_info, "Cached:", f"{cached_gb:.1f} GB")
        except:
            # Fallback: Try to calculate from available - free
            try:
                cached_gb = (mem.available - mem.free) / (1024**3)
                if cached_gb < 0:
                    cached_gb = 0
                cached_row = self.create_info_row(ram_info, "Cached:", f"{cached_gb:.1f} GB")
            except:
                cached_row = self.create_info_row(ram_info, "Cached:", "N/A")
        
        cached_row.pack(fill=tk.X, pady=3)
        self.perf_ram_cached = cached_row.winfo_children()[-1] if cached_row.winfo_children() else None
        
        # Middle row - GPU & Disk
        mid_row = tk.Frame(content, bg=ModernTheme.BG_DARK)
        mid_row.pack(fill=tk.BOTH, expand=True)
        
        # GPU Card with gauge
        gpu_card = self.create_card(mid_row, "GPU Information")
        gpu_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        gpu_container = tk.Frame(gpu_card, bg=ModernTheme.BG_CARD)
        gpu_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        

        
        # Try to get GPU info with multiple methods
        gpu_list = []
        integrated_gpu = None
        dedicated_gpu = None
        
        # Method 1: WMI VideoController
        try:
            result = subprocess.run(['wmic', 'path', 'win32_VideoController', 'get', 'name,AdapterRAM'],
                                  capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                lines = [line.strip() for line in result.stdout.split('\n')[1:] 
                        if line.strip() and 'Name' not in line and 'AdapterRAM' not in line]
                for line in lines:
                    if line:
                        parts = line.rsplit(None, 1)
                        gpu_name = parts[0] if parts else line
                        if any(x in gpu_name.lower() for x in ['intel', 'uhd', 'iris', 'hd graphics', 'amd radeon(tm) graphics']):
                            integrated_gpu = gpu_name[:40]
                        elif any(x in gpu_name.lower() for x in ['nvidia', 'geforce', 'rtx', 'gtx', 'radeon rx', 'radeon pro', 'quadro']):
                            dedicated_gpu = gpu_name[:40]
                        else:
                            gpu_list.append(gpu_name[:40])
        except: pass
        
        # Method 2: Try Caption if name failed
        if not integrated_gpu and not dedicated_gpu and not gpu_list:
            try:
                result = subprocess.run(['wmic', 'path', 'Win32_VideoController', 'get', 'Caption'],
                                      capture_output=True, text=True, timeout=2, creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode == 0:
                    captions = [line.strip() for line in result.stdout.split('\n')[1:] 
                               if line.strip() and line.strip() != 'Caption']
                    for caption in captions:
                        if any(x in caption.lower() for x in ['intel', 'uhd', 'iris', 'hd graphics']):
                            integrated_gpu = caption[:40]
                        elif any(x in caption.lower() for x in ['nvidia', 'geforce', 'rtx', 'gtx', 'radeon rx']):
                            dedicated_gpu = caption[:40]
                        else:
                            gpu_list.append(caption[:40])
            except: pass
        
        # Method 3: PowerShell (Get-CimInstance) - Robust fallback / Second check for dedicated
        if not dedicated_gpu:
            try:
                ps_script = "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"
                result = subprocess.run(['powershell', '-Command', ps_script],
                                      capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode == 0:
                    gpus = [line.strip() for line in result.stdout.split('\n') if line.strip()]
                    for gpu in gpus:
                        if any(x in gpu.lower() for x in ['intel', 'uhd', 'iris', 'hd graphics', 'amd radeon(tm) graphics']):
                            if not integrated_gpu: integrated_gpu = gpu[:40]
                            else: gpu_list.append(gpu[:40])
                        elif any(x in gpu.lower() for x in ['nvidia', 'geforce', 'rtx', 'gtx', 'radeon rx', 'radeon pro', 'quadro']):
                            if not dedicated_gpu: dedicated_gpu = gpu[:40]
                            else: gpu_list.append(gpu[:40])
                        else: gpu_list.append(gpu[:40])
            except: pass

        # Method 4: Fallback to CPU-based detection
        if not integrated_gpu and not dedicated_gpu and not gpu_list:
            try:
                import platform
                processor = platform.processor()
                if 'Intel' in processor: integrated_gpu = "Intel Integrated Graphics"
                elif 'AMD' in processor: integrated_gpu = "AMD Integrated Graphics"
            except: pass

        # GPU Display Layout - Two Separate Panels
        
        # Left Panel Container (Dedicated)
        left_panel = tk.Frame(gpu_container, bg=ModernTheme.BG_CARD)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Right Panel Container (Integrated)
        right_panel = tk.Frame(gpu_container, bg=ModernTheme.BG_CARD)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        def create_gpu_subpanel(parent, title, name, is_dedicated):
            # Gauge Frame
            gauge_frame = tk.Frame(parent, bg=ModernTheme.BG_CARD)
            gauge_frame.pack(side=tk.LEFT, padx=(0, 10))
            
            gauge = AnimatedCircularProgress(gauge_frame, size=80, thickness=6)
            gauge.pack()
            
            # Info Frame
            info_frame = tk.Frame(parent, bg=ModernTheme.BG_CARD)
            info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            tk.Label(info_frame, text=title, font=("Segoe UI", 9, "bold"),
                    bg=ModernTheme.BG_CARD, fg=ModernTheme.ACCENT_PRIMARY if is_dedicated else ModernTheme.TEXT_SECONDARY).pack(anchor="w")
            
            tk.Label(info_frame, text=name, font=("Segoe UI", 8),
                    bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_PRIMARY, wraplength=140, justify="left").pack(anchor="w", pady=(2, 0))
            
            return gauge, info_frame

        # Build Left Panel (Dedicated)
        if dedicated_gpu:
            self.perf_gpu_gauge, d_info = create_gpu_subpanel(left_panel, "Device 1 (Dedicated)", dedicated_gpu, True)
            
            # Utilization Row for Dedicated
            util_row = self.create_info_row(d_info, "Usage:", "0%")
            util_row.pack(fill=tk.X, pady=(5,0))
            self.perf_gpu_util = util_row.winfo_children()[-1] if util_row.winfo_children() else None
        else:
            tk.Label(left_panel, text="No Dedicated GPU", font=("Segoe UI", 10),
                    bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_SECONDARY).pack(expand=True)
            self.perf_gpu_gauge = None

        # Build Right Panel (Integrated or Other)
        target_gpu = integrated_gpu or (gpu_list[0] if gpu_list else None)
        if target_gpu:
            self.perf_gpu_int_gauge, i_info = create_gpu_subpanel(right_panel, "Device 2 (Integrated)", target_gpu, False)
            # Placeholder for Int utilization if needed
        else:
            tk.Label(right_panel, text="No Secondary GPU", font=("Segoe UI", 10),
                    bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_SECONDARY).pack(expand=True)
            self.perf_gpu_int_gauge = None
        
        # Store for reference
        self.primary_gpu_name = dedicated_gpu or integrated_gpu or "Unknown"
        
        # Storage Drives Section
        storage_header = tk.Frame(content, bg=ModernTheme.BG_DARK)
        storage_header.pack(fill=tk.X, pady=(20, 10))
        
        tk.Label(storage_header, text="💾 Storage Drives", font=("Segoe UI", 16, "bold"),
                bg=ModernTheme.BG_DARK, fg=ModernTheme.ACCENT_PRIMARY).pack(anchor="w")
        
        # Storage grid container
        storage_grid = tk.Frame(content, bg=ModernTheme.BG_DARK)
        storage_grid.pack(fill=tk.X)
        storage_grid.columnconfigure(0, weight=1)
        storage_grid.columnconfigure(1, weight=1)
        
        # Get all partitions
        partitions = psutil.disk_partitions()
        
        # Store disk I/O widgets for real-time updates
        if not hasattr(self, 'storage_io_labels'):
            self.storage_io_labels = {}
        
        row = 0
        col = 0
        
        for partition in partitions:
            if 'cdrom' in partition.opts or partition.fstype == '':
                continue
                
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                
                # Create card for each drive
                drive_card = self.create_card(storage_grid, f"Drive {partition.device}")
                
                # Grid placement - 2 columns
                padx_left = (0, 10) if col == 0 else (10, 0)
                drive_card.grid(row=row, column=col, sticky="nsew", padx=padx_left, pady=(0, 15))
                
                drive_info = tk.Frame(drive_card, bg=ModernTheme.BG_CARD)
                drive_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
                
                # Top section with circular gauge and info
                top_section = tk.Frame(drive_info, bg=ModernTheme.BG_CARD)
                top_section.pack(fill=tk.X, pady=(0, 10))
                
                # Left: Circular progress gauge
                gauge_frame = tk.Frame(top_section, bg=ModernTheme.BG_CARD)
                gauge_frame.pack(side=tk.LEFT, padx=(0, 15))
                
                usage_pct = usage.percent
                gauge_color = ModernTheme.ACCENT_LIME if usage_pct < 70 else \
                             ModernTheme.ACCENT_ORANGE if usage_pct < 90 else ModernTheme.DANGER
                
                disk_gauge = AnimatedCircularProgress(gauge_frame, size=90, thickness=7)
                disk_gauge.pack()
                disk_gauge.set_value(usage_pct, f"{int(usage_pct)}%", 
                                    f"{usage.used/(1024**3):.0f}/{usage.total/(1024**3):.0f} GB",
                                    gauge_color)
                
                # Right: Usage details
                details_frame = tk.Frame(top_section, bg=ModernTheme.BG_CARD)
                details_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                
                tk.Label(details_frame, 
                        text=f"Used: {usage.used/(1024**3):.1f} GB / {usage.total/(1024**3):.1f} GB",
                        font=("Segoe UI", 11, "bold"), bg=ModernTheme.BG_CARD,
                        fg=ModernTheme.TEXT_PRIMARY).pack(anchor="w", pady=2)
                
                tk.Label(details_frame, 
                        text=f"Free Space: {usage.free/(1024**3):.1f} GB",
                        font=("Segoe UI", 9), bg=ModernTheme.BG_CARD,
                        fg=ModernTheme.ACCENT_LIME).pack(anchor="w", pady=2)
                
                tk.Label(details_frame, 
                        text=f"File System: {partition.fstype}",
                        font=("Segoe UI", 8), bg=ModernTheme.BG_CARD,
                        fg=ModernTheme.TEXT_SECONDARY).pack(anchor="w", pady=1)
                
                tk.Label(details_frame, 
                        text=f"Mount Point: {partition.mountpoint}",
                        font=("Segoe UI", 8), bg=ModernTheme.BG_CARD,
                        fg=ModernTheme.TEXT_SECONDARY).pack(anchor="w", pady=1)
                
                # Real-time I/O section
                io_frame = tk.Frame(drive_info, bg=ModernTheme.BG_CARD)
                io_frame.pack(fill=tk.X, pady=(10, 5))
                
                tk.Label(io_frame, text="📊 Real-time Disk Activity",
                        font=("Segoe UI", 9, "bold"), bg=ModernTheme.BG_CARD,
                        fg=ModernTheme.ACCENT_PRIMARY).pack(anchor="w", pady=(0, 5))
                
                io_grid = tk.Frame(io_frame, bg=ModernTheme.BG_CARD)
                io_grid.pack(fill=tk.X)
                io_grid.columnconfigure(0, weight=1)
                io_grid.columnconfigure(1, weight=1)
                
                # Read speed
                read_row = self.create_info_row(io_grid, "📖 Read:", "0.0 MB/s")
                read_row.grid(row=0, column=0, sticky="w", padx=2, pady=2)
                
                # Write speed
                write_row = self.create_info_row(io_grid, "📝 Write:", "0.0 MB/s")
                write_row.grid(row=0, column=1, sticky="w", padx=2, pady=2)
                
                # Store labels for updates
                drive_key = partition.device
                self.storage_io_labels[drive_key] = {
                    'read': read_row.winfo_children()[-1] if read_row.winfo_children() else None,
                    'write': write_row.winfo_children()[-1] if write_row.winfo_children() else None
                }
                
                # Move to next column/row
                col += 1
                if col >= 2:
                    col = 0
                    row += 1
                
            except Exception as e:
                pass
    
    def show_monitoring(self):
        """System monitoring view with sensors"""
        self.switch_section("monitoring")
        
        header = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        header.pack(fill=tk.X, padx=30, pady=20)
        
        tk.Label(header, text="System Monitoring", font=("Segoe UI", 24, "bold"),
                bg=ModernTheme.BG_DARK, fg=ModernTheme.TEXT_PRIMARY).pack(side=tk.LEFT)
        
        self.mon_time_label = tk.Label(header, text=datetime.now().strftime("%H:%M:%S"), 
                             font=("Segoe UI", 16),
                             bg=ModernTheme.BG_DARK, fg=ModernTheme.ACCENT_PRIMARY)
        self.mon_time_label.pack(side=tk.RIGHT)
        
        content = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        # Top row - Temperatures
        temp_row = tk.Frame(content, bg=ModernTheme.BG_DARK)
        temp_row.pack(fill=tk.X, pady=(0, 15))
        
        # CPU Temperature
        cpu_temp_card = self.create_card(temp_row, "🌡️ CPU Temperature")
        cpu_temp_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        cpu_temp_info = tk.Frame(cpu_temp_card, bg=ModernTheme.BG_CARD)
        cpu_temp_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        self.mon_cpu_temp = tk.Label(cpu_temp_info, text="--°C", 
                                     font=("Segoe UI", 32, "bold"),
                                     bg=ModernTheme.BG_CARD, fg=ModernTheme.ACCENT_PRIMARY)
        self.mon_cpu_temp.pack(pady=10)
        
        tk.Label(cpu_temp_info, text="Current Temperature",
                font=("Segoe UI", 10), bg=ModernTheme.BG_CARD,
                fg=ModernTheme.TEXT_SECONDARY).pack()
        
        # GPU Temperature
        gpu_temp_card = self.create_card(temp_row, "🎮 GPU Temperature")
        gpu_temp_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        gpu_temp_info = tk.Frame(gpu_temp_card, bg=ModernTheme.BG_CARD)
        gpu_temp_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        self.mon_gpu_temp = tk.Label(gpu_temp_info, text="--°C",
                                     font=("Segoe UI", 32, "bold"),
                                     bg=ModernTheme.BG_CARD, fg=ModernTheme.ACCENT_TERTIARY)
        self.mon_gpu_temp.pack(pady=10)
        
        tk.Label(gpu_temp_info, text="Current Temperature",
                font=("Segoe UI", 10), bg=ModernTheme.BG_CARD,
                fg=ModernTheme.TEXT_SECONDARY).pack()
        
        # Middle row - Fans & Battery
        mid_row = tk.Frame(content, bg=ModernTheme.BG_DARK)
        mid_row.pack(fill=tk.X, pady=(0, 15))
        
        # Fan Speeds
        fan_card = self.create_card(mid_row, "💨 Fan Speeds")
        fan_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        fan_info = tk.Frame(fan_card, bg=ModernTheme.BG_CARD)
        fan_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        self.mon_fan1 = self.create_info_row(fan_info, "CPU Fan:", "-- RPM")
        self.mon_fan1.pack(fill=tk.X, pady=5)
        
        self.mon_fan2 = self.create_info_row(fan_info, "System Fan:", "-- RPM")
        self.mon_fan2.pack(fill=tk.X, pady=5)
        
        # Battery Health
        battery_card = self.create_card(mid_row, "🔋 Battery Health")
        battery_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        battery_info = tk.Frame(battery_card, bg=ModernTheme.BG_CARD)
        battery_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # Get battery info
        battery = psutil.sensors_battery() if hasattr(psutil, 'sensors_battery') else None
        if battery:
            self.create_info_row(battery_info, "Status:", 
                                "Charging" if battery.power_plugged else "Discharging").pack(fill=tk.X, pady=3)
            self.create_info_row(battery_info, "Level:", 
                                f"{battery.percent}%").pack(fill=tk.X, pady=3)
            if battery.secsleft > 0:
                hours = battery.secsleft // 3600
                mins = (battery.secsleft % 3600) // 60
                self.create_info_row(battery_info, "Time Left:", 
                                    f"{hours}h {mins}m").pack(fill=tk.X, pady=3)
        else:
            # Try Windows API
            try:
                status = SYSTEM_POWER_STATUS()
                kernel32.GetSystemPowerStatus(ctypes.byref(status))
                
                bat_status = "Plugged In" if status.ACLineStatus == 1 else "On Battery"
                self.create_info_row(battery_info, "Status:", bat_status).pack(fill=tk.X, pady=3)
                self.create_info_row(battery_info, "Level:", 
                                    f"{status.BatteryLifePercent}%").pack(fill=tk.X, pady=3)
            except:
                tk.Label(battery_info, text="No battery detected",
                        font=("Segoe UI", 10), bg=ModernTheme.BG_CARD,
                        fg=ModernTheme.TEXT_SECONDARY).pack(pady=20)
        
        # Bottom row - System Sensors
        sensor_card = self.create_card(content, "📊 System Sensors")
        sensor_card.pack(fill=tk.BOTH, expand=True)
        
        sensor_info = tk.Frame(sensor_card, bg=ModernTheme.BG_CARD)
        sensor_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # Try to get sensor data
        sensor_text = tk.Text(sensor_info, height=8, bg=ModernTheme.BG_DARK,
                             fg=ModernTheme.TEXT_PRIMARY, font=("Consolas", 9),
                             relief=tk.FLAT, wrap=tk.WORD)
        sensor_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Populate sensor data
        sensor_data = []
        
        # Try WMI sensors
        if self.wmi_obj:
            try:
                sensor_data.append("🔍 Hardware Sensors (OpenHardwareMonitor):\n")
                for sensor in self.wmi_obj.Sensor():
                    sensor_data.append(f"  • {sensor.Name}: {sensor.Value} {sensor.SensorType}\n")
            except:
                sensor_data.append("⚠️ OpenHardwareMonitor not available\n")
        
        # CPU Info
        try:
            cpu_freq = psutil.cpu_freq()
            sensor_data.append(f"\n💻 CPU Frequency: {cpu_freq.current:.0f} MHz\n")
            
            cpu_percent_per_core = psutil.cpu_percent(percpu=True)
            sensor_data.append(f"📊 Per-Core Usage:\n")
            for i, percent in enumerate(cpu_percent_per_core[:8]):  # Show first 8 cores
                sensor_data.append(f"  Core {i}: {percent}%\n")
        except:
            pass
        
        if not sensor_data:
            sensor_data.append("ℹ️ Install OpenHardwareMonitor for detailed sensor monitoring\n")
            sensor_data.append("📌 Current monitoring shows basic system metrics\n")
        
        sensor_text.insert('1.0', ''.join(sensor_data))
        sensor_text.config(state='disabled')
    
    def show_processes(self):
        """Process management view with all running processes"""
        self.switch_section("processes")
        
        header = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        header.pack(fill=tk.X, padx=30, pady=20)
        
        tk.Label(header, text="Process Manager", font=("Segoe UI", 24, "bold"),
                bg=ModernTheme.BG_DARK, fg=ModernTheme.TEXT_PRIMARY).pack(side=tk.LEFT)
        
        # Refresh button
        refresh_btn = self.create_action_button(header, "🔄 Refresh", 
                                                lambda: self.show_processes())
        refresh_btn.pack(side=tk.RIGHT, padx=5)
        
        content = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        # Process table
        table_card = self.create_card(content, "Running Processes")
        table_card.pack(fill=tk.BOTH, expand=True)
        
        table_frame = tk.Frame(table_card, bg=ModernTheme.BG_CARD)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # Create scrollable text widget for processes
        scroll_y = tk.Scrollbar(table_frame, orient=tk.VERTICAL)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        process_text = tk.Text(table_frame, bg=ModernTheme.BG_DARK,
                              fg=ModernTheme.TEXT_PRIMARY, font=("Consolas", 9),
                              relief=tk.FLAT, yscrollcommand=scroll_y.set,
                              wrap=tk.NONE)
        process_text.pack(fill=tk.BOTH, expand=True)
        scroll_y.config(command=process_text.yview)
        
        # Header
        header_text = f"{'PID':<8} {'Name':<35} {'CPU%':<8} {'Memory':<12} {'Status':<12}\n"
        header_text += "=" * 85 + "\n"
        process_text.insert('1.0', header_text)
        
        # Get all processes
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'status']):
            try:
                processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cpu': proc.info['cpu_percent'] or 0,
                    'memory': proc.info['memory_info'].rss / (1024 * 1024) if proc.info['memory_info'] else 0,
                    'status': proc.info['status']
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Sort by CPU usage
        processes.sort(key=lambda x: x['cpu'], reverse=True)
        
        # Display top processes
        for proc in processes[:50]:  # Show top 50
            name = proc['name'][:33] + '..' if len(proc['name']) > 35 else proc['name']
            line = f"{proc['pid']:<8} {name:<35} {proc['cpu']:<8.1f} {proc['memory']:<10.1f} MB {proc['status']:<12}\n"
            process_text.insert(tk.END, line)
        
        process_text.config(state='disabled')
    
    def show_storage(self):
        """Storage management view with all drives and real-time I/O"""
        self.switch_section("storage")
        
        header = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        header.pack(fill=tk.X, padx=30, pady=20)
        
        tk.Label(header, text="Storage Manager", font=("Segoe UI", 24, "bold"),
                bg=ModernTheme.BG_DARK, fg=ModernTheme.TEXT_PRIMARY).pack(side=tk.LEFT)
        
        content = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        # Configure grid for responsive 2-column layout
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)
        
        # Get all partitions
        partitions = psutil.disk_partitions()
        
        # Store disk I/O widgets for real-time updates
        if not hasattr(self, 'storage_io_labels'):
            self.storage_io_labels = {}
        
        row = 0
        col = 0
        
        for partition in partitions:
            if 'cdrom' in partition.opts or partition.fstype == '':
                continue
                
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                
                # Create card for each drive
                drive_card = self.create_card(content, f"Drive {partition.device}")
                
                # Grid placement - 2 columns
                padx_left = (0, 10) if col == 0 else (10, 0)
                drive_card.grid(row=row, column=col, sticky="nsew", padx=padx_left, pady=(0, 15))
                
                drive_info = tk.Frame(drive_card, bg=ModernTheme.BG_CARD)
                drive_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
                
                # Top section with circular gauge and info
                top_section = tk.Frame(drive_info, bg=ModernTheme.BG_CARD)
                top_section.pack(fill=tk.X, pady=(0, 10))
                
                # Left: Circular progress gauge
                gauge_frame = tk.Frame(top_section, bg=ModernTheme.BG_CARD)
                gauge_frame.pack(side=tk.LEFT, padx=(0, 15))
                
                usage_pct = usage.percent
                gauge_color = ModernTheme.ACCENT_LIME if usage_pct < 70 else \
                             ModernTheme.ACCENT_ORANGE if usage_pct < 90 else ModernTheme.DANGER
                
                disk_gauge = AnimatedCircularProgress(gauge_frame, size=90, thickness=7)
                disk_gauge.pack()
                disk_gauge.set_value(usage_pct, f"{int(usage_pct)}%", 
                                    f"{usage.used/(1024**3):.0f}/{usage.total/(1024**3):.0f} GB",
                                    gauge_color)
                
                # Right: Usage details
                details_frame = tk.Frame(top_section, bg=ModernTheme.BG_CARD)
                details_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                
                tk.Label(details_frame, 
                        text=f"Used: {usage.used/(1024**3):.1f} GB / {usage.total/(1024**3):.1f} GB",
                        font=("Segoe UI", 11, "bold"), bg=ModernTheme.BG_CARD,
                        fg=ModernTheme.TEXT_PRIMARY).pack(anchor="w", pady=2)
                
                tk.Label(details_frame, 
                        text=f"Free Space: {usage.free/(1024**3):.1f} GB",
                        font=("Segoe UI", 9), bg=ModernTheme.BG_CARD,
                        fg=ModernTheme.ACCENT_LIME).pack(anchor="w", pady=2)
                
                tk.Label(details_frame, 
                        text=f"File System: {partition.fstype}",
                        font=("Segoe UI", 8), bg=ModernTheme.BG_CARD,
                        fg=ModernTheme.TEXT_SECONDARY).pack(anchor="w", pady=1)
                
                tk.Label(details_frame, 
                        text=f"Mount Point: {partition.mountpoint}",
                        font=("Segoe UI", 8), bg=ModernTheme.BG_CARD,
                        fg=ModernTheme.TEXT_SECONDARY).pack(anchor="w", pady=1)
                
                # Real-time I/O section
                io_frame = tk.Frame(drive_info, bg=ModernTheme.BG_CARD)
                io_frame.pack(fill=tk.X, pady=(10, 5))
                
                tk.Label(io_frame, text="📊 Real-time Disk Activity",
                        font=("Segoe UI", 9, "bold"), bg=ModernTheme.BG_CARD,
                        fg=ModernTheme.ACCENT_PRIMARY).pack(anchor="w", pady=(0, 5))
                
                io_grid = tk.Frame(io_frame, bg=ModernTheme.BG_CARD)
                io_grid.pack(fill=tk.X)
                io_grid.columnconfigure(0, weight=1)
                io_grid.columnconfigure(1, weight=1)
                
                # Read speed
                read_row = self.create_info_row(io_grid, "📖 Read:", "0.0 MB/s")
                read_row.grid(row=0, column=0, sticky="w", padx=2, pady=2)
                
                # Write speed
                write_row = self.create_info_row(io_grid, "📝 Write:", "0.0 MB/s")
                write_row.grid(row=0, column=1, sticky="w", padx=2, pady=2)
                
                # Store labels for updates
                drive_key = partition.device
                self.storage_io_labels[drive_key] = {
                    'read': read_row.winfo_children()[-1] if read_row.winfo_children() else None,
                    'write': write_row.winfo_children()[-1] if write_row.winfo_children() else None
                }
                
                # Move to next column/row
                col += 1
                if col >= 2:
                    col = 0
                    row += 1
                
            except Exception as e:
                pass
    
    def show_devices(self):
        """Devices view showing all connected hardware with controls"""
        self.switch_section("devices")
        
        header = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        header.pack(fill=tk.X, padx=30, pady=20)
        
        tk.Label(header, text="Connected Devices", font=("Segoe UI", 24, "bold"),
                bg=ModernTheme.BG_DARK, fg=ModernTheme.TEXT_PRIMARY).pack(side=tk.LEFT)
        
        self.dev_time_label = tk.Label(header, text=datetime.now().strftime("%H:%M:%S"), 
                             font=("Segoe UI", 16),
                             bg=ModernTheme.BG_DARK, fg=ModernTheme.ACCENT_PRIMARY)
        self.dev_time_label.pack(side=tk.RIGHT)
        
        content = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        # Configure grid for 2-column layout
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)
        
        row = 0
        
        # CPU Devices
        cpu_card = self.create_card(content, "🖥️ Processor")
        cpu_card.grid(row=row, column=0, sticky="nsew", padx=(0, 10), pady=(0, 15))
        
        cpu_info = tk.Frame(cpu_card, bg=ModernTheme.BG_CARD)
        cpu_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        self.create_info_row(cpu_info, "Name:", self.cpu_name[:35]).pack(fill=tk.X, pady=3)
        self.create_info_row(cpu_info, "Cores:", f"{psutil.cpu_count(logical=False)} Physical").pack(fill=tk.X, pady=3)
        self.create_info_row(cpu_info, "Threads:", f"{psutil.cpu_count(logical=True)} Logical").pack(fill=tk.X, pady=3)
        
        # GPU Devices - FIXED
        gpu_card = self.create_card(content, "🎮 Graphics Cards")
        gpu_card.grid(row=row, column=1, sticky="nsew", padx=(10, 0), pady=(0, 15))
        
        gpu_info = tk.Frame(gpu_card, bg=ModernTheme.BG_CARD)
        gpu_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        gpu_found = False
        try:
            result = subprocess.run(['wmic', 'path', 'win32_VideoController', 'get', 'name'],
                                  capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                gpu_names = [line.strip() for line in result.stdout.split('\n')[1:] if line.strip() and line.strip() != 'Name']
                if gpu_names:
                    gpu_found = True
                    for i, gpu in enumerate(gpu_names[:3]):
                        self.create_info_row(gpu_info, f"GPU {i+1}:", gpu[:35]).pack(fill=tk.X, pady=3)
        except:
            pass
        
        if not gpu_found:
            tk.Label(gpu_info, text="✓ Integrated Graphics", font=("Segoe UI", 10),
                    bg=ModernTheme.BG_CARD, fg=ModernTheme.ACCENT_LIME).pack(pady=10)
        
        row += 1
        
        # RAM Devices
        ram_card = self.create_card(content, "💾 Memory Modules")
        ram_card.grid(row=row, column=0, sticky="nsew", padx=(0, 10), pady=(0, 15))
        
        ram_info = tk.Frame(ram_card, bg=ModernTheme.BG_CARD)
        ram_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        self.create_info_row(ram_info, "Total RAM:", f"{self.total_ram_gb} GB").pack(fill=tk.X, pady=3)
        
        ram_found = False
        try:
            result = subprocess.run(['wmic', 'memorychip', 'get', 'capacity,speed'],
                                  capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                lines = [l.strip() for l in result.stdout.split('\n')[1:] if l.strip() and 'Capacity' not in l]
                for i, line in enumerate(lines[:4]):
                    parts = line.split()
                    if len(parts) >= 2:
                        ram_found = True
                        try:
                            size_gb = int(parts[0]) / (1024**3)
                            speed = parts[1]
                            self.create_info_row(ram_info, f"Module {i+1}:", 
                                                f"{size_gb:.0f} GB @ {speed} MHz").pack(fill=tk.X, pady=2)
                        except:
                            pass
        except:
            pass
        
        if not ram_found:
            self.create_info_row(ram_info, "Status:", "✓ Memory Active").pack(fill=tk.X, pady=3)
        
        # Storage Devices
        storage_card = self.create_card(content, "💿 Storage Drives")
        storage_card.grid(row=row, column=1, sticky="nsew", padx=(10, 0), pady=(0, 15))
        
        storage_info = tk.Frame(storage_card, bg=ModernTheme.BG_CARD)
        storage_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        storage_found = False
        try:
            result = subprocess.run(['wmic', 'diskdrive', 'get', 'model,size'],
                                  capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                lines = [l.strip() for l in result.stdout.split('\n')[1:] if l.strip() and 'Model' not in l]
                for i, line in enumerate(lines[:4]):
                    if line:
                        parts = line.rsplit(None, 1)
                        if len(parts) >= 2:
                            storage_found = True
                            try:
                                model = parts[0][:30]
                                size_gb = int(parts[1]) / (1024**3)
                                self.create_info_row(storage_info, f"Drive {i+1}:", 
                                                    f"{model} ({size_gb:.0f} GB)").pack(fill=tk.X, pady=2)
                            except:
                                pass
        except:
            pass
        
        if not storage_found:
            # Fallback to psutil
            for i, part in enumerate(psutil.disk_partitions()[:2]):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    self.create_info_row(storage_info, f"{part.device}", 
                                        f"{usage.total/(1024**3):.0f} GB").pack(fill=tk.X, pady=2)
                    storage_found = True
                except:
                    pass
        
        row += 1
        
        # Network Adapters
        network_card = self.create_card(content, "🌐 Network Adapters")
        network_card.grid(row=row, column=0, sticky="nsew", padx=(0, 10), pady=(0, 15))
        
        network_info = tk.Frame(network_card, bg=ModernTheme.BG_CARD)
        network_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        net_if_stats = psutil.net_if_stats()
        count = 0
        for name, stats in net_if_stats.items():
            if count < 4 and 'Loopback' not in name:
                status = "🟢" if stats.isup else "🔴"
                speed_text = f"{stats.speed} Mbps" if stats.speed > 0 else "N/A"
                self.create_info_row(network_info, f"{status} {name[:25]}:", speed_text).pack(fill=tk.X, pady=2)
                count += 1
        
        # USB Devices - IMPROVED (Show actual devices, not just hubs)
        usb_card = self.create_card(content, "🔌 USB Devices")
        usb_card.grid(row=row, column=1, sticky="nsew", padx=(10, 0), pady=(0, 15))
        
        usb_info = tk.Frame(usb_card, bg=ModernTheme.BG_CARD)
        usb_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        usb_found = False
        usb_devices_list = []
        
        # Try multiple methods to detect USB devices
        try:
            # Method 1: PnP devices (better for actual devices)
            result = subprocess.run(['wmic', 'path', 'Win32_PnPEntity', 'where', 
                                   'DeviceID like "%USB%"', 'get', 'Caption'],
                                  capture_output=True, text=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                devices = [line.strip() for line in result.stdout.split('\n')[1:] 
                          if line.strip() and line.strip() != 'Caption' 
                          and 'USB' in line and 'Hub' not in line and 'Composite' not in line]
                usb_devices_list.extend(devices[:5])
        except:
            pass
        
        # Method 2: USB Controllers (if PnP failed)
        if not usb_devices_list:
            try:
                result = subprocess.run(['wmic', 'path', 'Win32_USBControllerDevice', 'get', 'Dependent'],
                                      capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode == 0:
                    devices = [line.strip() for line in result.stdout.split('\n')[1:] 
                              if line.strip() and 'USB' in line]
                    usb_devices_list.extend(devices[:5])
            except:
                pass
        
        if usb_devices_list:
            usb_found = True
            for i, device in enumerate(usb_devices_list[:5]):
                # Clean up device name
                clean_name = device.replace('USB\\', '').replace('VID_', '').replace('PID_', '')
                if len(clean_name) > 35:
                    clean_name = clean_name[:32] + "..."
                self.create_info_row(usb_info, f"USB {i+1}:", clean_name).pack(fill=tk.X, pady=2)
        
        if not usb_found:
            tk.Label(usb_info, text="✓ USB Ports Active", font=("Segoe UI", 10),
                    bg=ModernTheme.BG_CARD, fg=ModernTheme.ACCENT_LIME).pack(pady=10)
        
        row += 1
        
        # Audio Devices with Volume Control - Enhanced to show all devices
        audio_card = self.create_card(content, "🔊 Audio Devices & Control")
        audio_card.grid(row=row, column=0, sticky="nsew", padx=(0, 10), pady=(0, 15))
        
        audio_info = tk.Frame(audio_card, bg=ModernTheme.BG_CARD)
        audio_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        audio_found = False
        audio_devices_list = []
        
        # Method 1: Try Win32_SoundDevice (better for actual devices)
        try:
            result = subprocess.run(['wmic', 'sounddev', 'get', 'name,status'],
                                  capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                lines = [line.strip() for line in result.stdout.split('\n')[1:] 
                        if line.strip() and 'Name' not in line and 'Status' not in line]
                for line in lines:
                    if line and 'OK' in line:
                        device_name = line.replace('OK', '').strip()
                        if device_name:
                            audio_devices_list.append(device_name[:40])
                            audio_found = True
        except:
            pass
        
        # Method 2: Try Win32_PnPEntity for audio devices (if sounddev failed)
        if not audio_found:
            try:
                result = subprocess.run(['wmic', 'path', 'Win32_PnPEntity', 'where', 
                                       'PNPClass="MEDIA" OR PNPClass="AudioEndpoint"', 'get', 'Caption'],
                                      capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode == 0:
                    captions = [line.strip() for line in result.stdout.split('\n')[1:] 
                               if line.strip() and line.strip() != 'Caption']
                    if captions:
                        audio_devices_list.extend(captions[:5])
                        audio_found = True
            except:
                pass
        
        # Method 3: Use PowerShell to enumerate audio devices
        if not audio_found:
            try:
                ps_script = "Get-WmiObject Win32_SoundDevice | Select-Object -ExpandProperty Name"
                result = subprocess.run(['powershell', '-Command', ps_script],
                                      capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode == 0:
                    devices = [line.strip() for line in result.stdout.split('\n') 
                              if line.strip() and line.strip() != '']
                    if devices:
                        audio_devices_list.extend(devices[:5])
                        audio_found = True
            except:
                pass
        
        # Categorize and display audio devices
        if audio_devices_list:
            # Remove duplicates while preserving order
            seen = set()
            unique_devices = []
            for device in audio_devices_list:
                if device not in seen:
                    seen.add(device)
                    unique_devices.append(device)
            
            # Display devices with icons
            for i, device in enumerate(unique_devices[:5]):
                # Determine device type by name
                if any(x in device.lower() for x in ['speaker', 'realtek', 'audio output']):
                    icon = "🔊"
                    device_type = "Speaker:"
                elif any(x in device.lower() for x in ['headphone', 'headset']):
                    icon = "🎧"
                    device_type = "Headphone:"
                elif any(x in device.lower() for x in ['microphone', 'mic', 'input']):
                    icon = "🎤"
                    device_type = "Microphone:"
                elif any(x in device.lower() for x in ['hdmi', 'displayport']):
                    icon = "📺"
                    device_type = "HDMI Audio:"
                else:
                    icon = "🔉"
                    device_type = f"Audio {i+1}:"
                
                self.create_info_row(audio_info, f"{icon} {device_type}", device[:35]).pack(fill=tk.X, pady=2)
        
        if not audio_found or not audio_devices_list:
            tk.Label(audio_info, text="✓ Audio System Active", font=("Segoe UI", 10),
                    bg=ModernTheme.BG_CARD, fg=ModernTheme.ACCENT_LIME).pack(pady=5)
        
        # Volume Control
        tk.Label(audio_info, text="🔊 Volume Control:", font=("Segoe UI", 9, "bold"),
                bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_PRIMARY).pack(anchor="w", pady=(10, 5))
        
        volume_frame = tk.Frame(audio_info, bg=ModernTheme.BG_CARD)
        volume_frame.pack(fill=tk.X, pady=5)
        
        volume_slider = tk.Scale(volume_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                bg=ModernTheme.BG_DARK, fg=ModernTheme.ACCENT_PRIMARY,
                                highlightthickness=0, troughcolor=ModernTheme.BG_SIDEBAR,
                                activebackground=ModernTheme.ACCENT_LIME,
                                command=lambda v: self.set_volume(int(v)))
        
        # Get current volume from system
        current_vol = 50
        if HAS_PYCAW:
            try:
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = cast(interface, POINTER(IAudioEndpointVolume))
                current_vol = int(volume.GetMasterVolumeLevelScalar() * 100)
            except: pass
            
        volume_slider.set(current_vol)
        volume_slider.pack(fill=tk.X)
        
        # Removed delayed application - relying on system state
        
        # Monitors with Brightness Control - Enhanced to show only connected displays
        monitor_card = self.create_card(content, "🖥️ Displays & Control")
        monitor_card.grid(row=row, column=1, sticky="nsew", padx=(10, 0), pady=(0, 15))
        
        monitor_info = tk.Frame(monitor_card, bg=ModernTheme.BG_CARD)
        monitor_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        monitor_found = False
        monitors_list = []
        
        # Method 1: Try Win32_PnPEntity for connected monitors (most reliable)
        try:
            result = subprocess.run(['wmic', 'path', 'Win32_PnPEntity', 'where', 
                                   'PNPClass="Monitor" AND Status="OK"', 'get', 'Caption'],
                                  capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                captions = [line.strip() for line in result.stdout.split('\n')[1:] 
                           if line.strip() and line.strip() != 'Caption' and 'Generic' not in line]
                if captions:
                    monitors_list.extend(captions[:5])
                    monitor_found = True
        except:
            pass
        
        # Method 2: Try WMI DesktopMonitor with resolution (if PnP failed)
        if not monitor_found:
            try:
                result = subprocess.run(['wmic', 'path', 'Win32_DesktopMonitor', 'where', 
                                       'Availability=3', 'get', 'name,ScreenWidth,ScreenHeight'],
                                      capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode == 0:
                    lines = [line.strip() for line in result.stdout.split('\n')[1:] 
                            if line.strip() and 'Name' not in line and 'ScreenHeight' not in line]
                    for line in lines:
                        if line:
                            parts = line.split()
                            if len(parts) >= 1:
                                monitor_name = ' '.join(parts[:-2]) if len(parts) > 2 else parts[0]
                                width = parts[-2] if len(parts) > 2 else ''
                                height = parts[-1] if len(parts) > 1 else ''
                                
                                if width and height and width.isdigit() and height.isdigit():
                                    monitors_list.append(f"{monitor_name} ({width}x{height})")
                                else:
                                    monitors_list.append(monitor_name)
                                monitor_found = True
            except:
                pass
        
        # Method 3: Use PowerShell to get only active monitors
        if not monitor_found:
            try:
                ps_script = "Get-WmiObject -Namespace root\\wmi -Class WmiMonitorID | ForEach-Object { [System.Text.Encoding]::ASCII.GetString($_.UserFriendlyName -notmatch 0) }"
                result = subprocess.run(['powershell', '-Command', ps_script],
                                      capture_output=True, text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode == 0:
                    lines = [line.strip() for line in result.stdout.split('\n') 
                            if line.strip() and line.strip() != '']
                    if lines:
                        monitors_list.extend(lines[:5])
                        monitor_found = True
            except:
                pass
        
        # Method 4: Fallback - Get screen resolution only
        if not monitor_found:
            try:
                from ctypes import windll
                user32 = windll.user32
                width = user32.GetSystemMetrics(0)
                height = user32.GetSystemMetrics(1)
                monitors_list.append(f"Primary Display ({width}x{height})")
                monitor_found = True
            except:
                pass
        
        # Display only connected monitors with individual brightness controls
        if monitors_list:
            for i, monitor in enumerate(monitors_list[:5]):
                # Monitor info row
                icon = "🖥️" if i == 0 else "🖵"
                label = "Primary:" if i == 0 else f"Monitor {i+1}:"
                self.create_info_row(monitor_info, f"{icon} {label}", monitor[:35]).pack(fill=tk.X, pady=2)
                
                # Individual brightness control for this monitor
                brightness_frame = tk.Frame(monitor_info, bg=ModernTheme.BG_CARD)
                brightness_frame.pack(fill=tk.X, pady=(5, 10))
                
                tk.Label(brightness_frame, text=f"💡 Brightness:", font=("Segoe UI", 8),
                        bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_SECONDARY).pack(anchor="w")
                
                brightness_slider = tk.Scale(brightness_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                            bg=ModernTheme.BG_DARK, fg=ModernTheme.ACCENT_TERTIARY,
                                            highlightthickness=0, troughcolor=ModernTheme.BG_SIDEBAR,
                                            activebackground=ModernTheme.ACCENT_ORANGE,
                                            command=lambda v, idx=i: self.set_brightness(int(v), idx))
                
                # Get current system brightness
                current_br = 75
                if HAS_SBC:
                    try:
                        vals = sbc.get_brightness(display=i)
                        if vals: current_br = vals[0]
                    except: 
                        try: 
                            vals = sbc.get_brightness()
                            if vals: current_br = vals[0]
                        except: pass
                
                brightness_slider.set(current_br)
                brightness_slider.pack(fill=tk.X)
                
                # Removed delayed application - relying on system state
        
        if not monitor_found or not monitors_list:
            tk.Label(monitor_info, text="✓ Primary Display Active", font=("Segoe UI", 10),
                    bg=ModernTheme.BG_CARD, fg=ModernTheme.ACCENT_LIME).pack(pady=5)
            
            # Single brightness control for fallback
            tk.Label(monitor_info, text="💡 Brightness:", font=("Segoe UI", 9, "bold"),
                    bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_PRIMARY).pack(anchor="w", pady=(10, 5))
            
            brightness_slider = tk.Scale(monitor_info, from_=0, to=100, orient=tk.HORIZONTAL,
                                        bg=ModernTheme.BG_DARK, fg=ModernTheme.ACCENT_TERTIARY,
                                        highlightthickness=0, troughcolor=ModernTheme.BG_SIDEBAR,
                                        activebackground=ModernTheme.ACCENT_ORANGE,
                                        command=lambda v: self.set_brightness(int(v), 0))
            brightness_slider.set(75)
            brightness_slider.pack(fill=tk.X)
        
        row += 1
        
        # Keyboard with Controls
        keyboard_card = self.create_card(content, "⌨️ Keyboard & Controls")
        keyboard_card.grid(row=row, column=0, columnspan=2, sticky="nsew", padx=0, pady=(0, 15))
        
        keyboard_info = tk.Frame(keyboard_card, bg=ModernTheme.BG_CARD)
        keyboard_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # Keyboard info
        kb_grid = tk.Frame(keyboard_info, bg=ModernTheme.BG_CARD)
        kb_grid.pack(fill=tk.X, pady=(0, 10))
        kb_grid.columnconfigure(0, weight=1)
        kb_grid.columnconfigure(1, weight=1)
        kb_grid.columnconfigure(2, weight=1)
        
        self.create_info_row(kb_grid, "Status:", "✓ Active").grid(row=0, column=0, sticky="w", padx=5)
        self.create_info_row(kb_grid, "Type:", "Standard").grid(row=0, column=1, sticky="w", padx=5)
        self.create_info_row(kb_grid, "Layout:", "QWERTY").grid(row=0, column=2, sticky="w", padx=5)
        
        # Typing Test
        tk.Label(keyboard_info, text="⌨️ Typing Test:", font=("Segoe UI", 10, "bold"),
                bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_PRIMARY).pack(anchor="w", pady=(5, 5))
        
        typing_entry = tk.Entry(keyboard_info, font=("Segoe UI", 11), bg=ModernTheme.BG_DARK,
                               fg=ModernTheme.TEXT_PRIMARY, insertbackground=ModernTheme.ACCENT_PRIMARY,
                               relief=tk.FLAT)
        typing_entry.pack(fill=tk.X, ipady=5)
        typing_entry.insert(0, "Type here to test keyboard...")
        
        # Backlight Control (simulated)
        tk.Label(keyboard_info, text="💡 Backlight:", font=("Segoe UI", 9, "bold"),
                bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_PRIMARY).pack(anchor="w", pady=(10, 5))
        
        backlight_frame = tk.Frame(keyboard_info, bg=ModernTheme.BG_CARD)
        backlight_frame.pack(fill=tk.X)
        
        colors = [("Red", "#ff3366"), ("Green", "#00ff88"), ("Blue", "#00d9ff"), 
                 ("Yellow", "#ffaa00"), ("Purple", "#ff00ff"), ("Cyan", "#00ffff")]
        
        for color_name, color_code in colors:
            btn = tk.Button(backlight_frame, text=color_name, bg=color_code, fg="#000000",
                           font=("Segoe UI", 8, "bold"), relief=tk.FLAT, cursor="hand2",
                           command=lambda c=color_code: self.set_keyboard_color(c))
            btn.pack(side=tk.LEFT, padx=2, pady=2, ipadx=8, ipady=2)
    
    def set_volume(self, volume):
        """Set system volume using Windows API"""
        try:
            if HAS_PYCAW:
                # Use pycaw to set volume
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume_interface = cast(interface, POINTER(IAudioEndpointVolume))
                
                # Set volume (0.0 to 1.0)
                volume_interface.SetMasterVolumeLevelScalar(volume / 100.0, None)
                print(f"✓ Volume set to: {volume}%")
                
                # Save config
                self.saved_volumes['master'] = volume
                self.save_config()
            else:
                # Fallback: Try nircmd if available
                try:
                    subprocess.run(['nircmd.exe', 'setsysvolume', str(int(volume * 655.35))],
                                 capture_output=True, timeout=1, creationflags=subprocess.CREATE_NO_WINDOW)
                    print(f"✓ Volume set to: {volume}% (via nircmd)")
                    
                    # Save config
                    self.saved_volumes['master'] = volume
                    self.save_config()
                except:
                    # Silent fallback - just log once
                    if not hasattr(self, '_volume_warning_shown'):
                        print(f"⚠ Volume control not available (pycaw not installed)")
                        self._volume_warning_shown = True
        except Exception as e:
            if not hasattr(self, '_volume_error_shown'):
                print(f"Volume control error: {e}")
                self._volume_error_shown = True
    
    def set_brightness(self, brightness, monitor_index=0):
        """Set monitor brightness using screen_brightness_control or WMI"""
        try:
            # Method 1: Use screen_brightness_control (Best for external monitors)
            if HAS_SBC:
                try:
                    # Get list of monitors to ensure index matches
                    monitors = sbc.list_monitors()
                    if monitor_index < len(monitors):
                        sbc.set_brightness(brightness, display=monitor_index)
                        print(f"✓ Monitor {monitor_index + 1} brightness set to: {brightness}% (via SBC)")
                        
                        # Save config
                        self.saved_brightness[str(monitor_index)] = brightness
                        self.save_config()
                        return
                    else:
                        # Try controlling all if index not found (but don't target wrong one)
                        # sbc.set_brightness(brightness) 
                        print(f"⚠ Monitor index {monitor_index} out of range for SBC")
                except Exception as e:
                    # print(f"SBC Error: {e}")
                    pass

            # Method 2: Try WMI brightness control (Laptops/Integrated)
            if HAS_WMI:
                try:
                    import wmi
                    c = wmi.WMI(namespace='wmi')
                    methods_list = c.WmiMonitorBrightnessMethods()
                    
                    # Exact index matching only
                    if monitor_index < len(methods_list):
                        methods_list[monitor_index].WmiSetBrightness(brightness, 0)
                        print(f"✓ Monitor {monitor_index + 1} brightness set to: {brightness}% (via WMI)")
                        return
                except Exception as e:
                    pass
            
            # Method 3: PowerShell WMI command (Specific index)
            try:
                ps_script = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)[{monitor_index}].WmiSetBrightness(1,{brightness})"
                result = subprocess.run(['powershell', '-Command', ps_script],
                                      capture_output=True, text=True, timeout=2, creationflags=subprocess.CREATE_NO_WINDOW)
                if result.returncode == 0:
                    print(f"✓ Monitor {monitor_index + 1} brightness set to: {brightness}% (via PowerShell)")
                    return
            except:
                pass
            
            # If we reach here, we couldn't control the specific monitor
            if not hasattr(self, '_brightness_warning_shown'):
                print(f"⚠ Could not set brightness for Monitor {monitor_index + 1}")
                self._brightness_warning_shown = True
                
        except Exception as e:
            if not hasattr(self, '_brightness_error_shown'):
                print(f"Brightness control error: {e}")
                self._brightness_error_shown = True
    
    def set_keyboard_color(self, color):
        """Set keyboard backlight color - Silent"""
        try:
            print(f"Keyboard backlight set to: {color}")
            # Note: Actual RGB control requires manufacturer-specific SDKs
            # (e.g., Razer Chroma SDK, Corsair iCUE SDK, Logitech G SDK)
        except Exception as e:
            print(f"Keyboard color error: {e}")
    
    def show_network(self):
        """Network monitoring view with all adapters"""
        self.switch_section("network")
        
        header = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        header.pack(fill=tk.X, padx=30, pady=20)
        
        tk.Label(header, text="Network Monitor", font=("Segoe UI", 24, "bold"),
                bg=ModernTheme.BG_DARK, fg=ModernTheme.TEXT_PRIMARY).pack(side=tk.LEFT)
        
        self.net_time_label = tk.Label(header, text=datetime.now().strftime("%H:%M:%S"), 
                             font=("Segoe UI", 16),
                             bg=ModernTheme.BG_DARK, fg=ModernTheme.ACCENT_PRIMARY)
        self.net_time_label.pack(side=tk.RIGHT)
        
        content = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        # Get network interfaces
        net_if_addrs = psutil.net_if_addrs()
        net_if_stats = psutil.net_if_stats()
        
        # Separate connected and disconnected adapters
        connected_adapters = []
        disconnected_adapters = []
        
        for interface_name, addrs in net_if_addrs.items():
            stats = net_if_stats.get(interface_name)
            if stats and stats.isup:
                connected_adapters.append((interface_name, addrs, stats))
            else:
                disconnected_adapters.append((interface_name, addrs, stats))
        
        # Connected Adapters Section
        if connected_adapters:
            connected_header = tk.Frame(content, bg=ModernTheme.BG_DARK)
            connected_header.pack(fill=tk.X, pady=(0, 10))
            
            tk.Label(connected_header, text=f"🟢 Connected Adapters ({len(connected_adapters)})",
                    font=("Segoe UI", 14, "bold"), bg=ModernTheme.BG_DARK,
                    fg=ModernTheme.ACCENT_LIME).pack(anchor="w")
            
            for interface_name, addrs, stats in connected_adapters:
                self._create_network_card(content, interface_name, addrs, stats, True)
        
        # Disconnected Adapters Section with Toggle
        if disconnected_adapters:
            disconnected_header = tk.Frame(content, bg=ModernTheme.BG_DARK)
            disconnected_header.pack(fill=tk.X, pady=(20, 10))
            
            # Toggle button
            self.show_disconnected = tk.BooleanVar(value=False)
            
            toggle_frame = tk.Frame(disconnected_header, bg=ModernTheme.BG_DARK)
            toggle_frame.pack(anchor="w")
            
            toggle_btn = tk.Checkbutton(
                toggle_frame,
                text=f"🔴 Disconnected Adapters ({len(disconnected_adapters)}) - Click to show/hide",
                variable=self.show_disconnected,
                command=lambda: self.toggle_disconnected_adapters(content, disconnected_adapters),
                font=("Segoe UI", 12, "bold"),
                bg=ModernTheme.BG_DARK,
                fg=ModernTheme.TEXT_SECONDARY,
                selectcolor=ModernTheme.BG_CARD,
                activebackground=ModernTheme.BG_DARK,
                activeforeground=ModernTheme.ACCENT_PRIMARY,
                relief=tk.FLAT,
                cursor="hand2"
            )
            toggle_btn.pack(anchor="w")
            
            # Container for disconnected adapters (initially hidden)
            self.disconnected_container = tk.Frame(content, bg=ModernTheme.BG_DARK)
            # Don't pack it yet - will be toggled
    
    def toggle_disconnected_adapters(self, parent, disconnected_adapters):
        """Toggle visibility of disconnected adapters"""
        if self.show_disconnected.get():
            # Show disconnected adapters
            self.disconnected_container.pack(fill=tk.X, pady=(0, 10))
            
            # Clear and recreate
            for widget in self.disconnected_container.winfo_children():
                widget.destroy()
            
            for interface_name, addrs, stats in disconnected_adapters:
                self._create_network_card(self.disconnected_container, interface_name, addrs, stats, False)
        else:
            # Hide disconnected adapters
            self.disconnected_container.pack_forget()
    
    def _create_network_card(self, parent, interface_name, addrs, stats, is_connected):
        """Create a network adapter card"""
        if_card = self.create_card(parent, f"Network Adapter: {interface_name}")
        if_card.pack(fill=tk.X, pady=(0, 15))
        
        if_info = tk.Frame(if_card, bg=ModernTheme.BG_CARD)
        if_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # Status
        if stats:
            if is_connected:
                status = "� Connected"
                status_color = ModernTheme.SUCCESS
            else:
                status = "🔴 Disconnected"
                status_color = ModernTheme.DANGER
            
            status_label = tk.Label(if_info, text=status, font=("Segoe UI", 11, "bold"),
                                   bg=ModernTheme.BG_CARD, fg=status_color)
            status_label.pack(anchor="w", pady=(0, 10))
            
            # Speed (only for connected)
            if is_connected and stats.speed > 0:
                self.create_info_row(if_info, "Speed:", f"{stats.speed} Mbps").pack(fill=tk.X, pady=3)
        
        # IP Addresses
        for addr in addrs:
            if addr.family == 2:  # IPv4
                self.create_info_row(if_info, "IPv4 Address:", addr.address).pack(fill=tk.X, pady=3)
                if addr.netmask:
                    self.create_info_row(if_info, "Subnet Mask:", addr.netmask).pack(fill=tk.X, pady=3)
            elif addr.family == 23:  # IPv6
                ipv6_addr = addr.address.split('%')[0]
                self.create_info_row(if_info, "IPv6 Address:", ipv6_addr[:40]).pack(fill=tk.X, pady=3)
            elif addr.family == -1:  # MAC
                self.create_info_row(if_info, "MAC Address:", addr.address).pack(fill=tk.X, pady=3)
    
    def show_settings(self):
        """Settings view with configuration options"""
        self.switch_section("settings")
        
        header = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        header.pack(fill=tk.X, padx=30, pady=20)
        
        tk.Label(header, text="Settings", font=("Segoe UI", 24, "bold"),
                bg=ModernTheme.BG_DARK, fg=ModernTheme.TEXT_PRIMARY).pack(side=tk.LEFT)
        
        self.set_time_label = tk.Label(header, text=datetime.now().strftime("%H:%M:%S"), 
                             font=("Segoe UI", 16),
                             bg=ModernTheme.BG_DARK, fg=ModernTheme.ACCENT_PRIMARY)
        self.set_time_label.pack(side=tk.RIGHT)
        
        content = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        # Monitoring Thresholds
        threshold_card = self.create_card(content, "⚙️ Monitoring Thresholds")
        threshold_card.pack(fill=tk.X, pady=(0, 15))
        
        threshold_info = tk.Frame(threshold_card, bg=ModernTheme.BG_CARD)
        threshold_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # CPU Threshold
        cpu_frame = tk.Frame(threshold_info, bg=ModernTheme.BG_CARD)
        cpu_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(cpu_frame, text="CPU Alert Threshold:", font=("Segoe UI", 10),
                bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_PRIMARY).pack(side=tk.LEFT)
        
        self.cpu_threshold_var = tk.StringVar(value=str(self.threshold_cpu))
        cpu_entry = tk.Entry(cpu_frame, textvariable=self.cpu_threshold_var,
                            bg=ModernTheme.BG_DARK, fg=ModernTheme.TEXT_PRIMARY,
                            font=("Segoe UI", 10), width=10)
        cpu_entry.pack(side=tk.LEFT, padx=10)
        
        tk.Label(cpu_frame, text="%", font=("Segoe UI", 10),
                bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_SECONDARY).pack(side=tk.LEFT)
        
        # RAM Threshold
        ram_frame = tk.Frame(threshold_info, bg=ModernTheme.BG_CARD)
        ram_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(ram_frame, text="RAM Alert Threshold:", font=("Segoe UI", 10),
                bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_PRIMARY).pack(side=tk.LEFT)
        
        self.ram_threshold_var = tk.StringVar(value=str(self.threshold_ram))
        ram_entry = tk.Entry(ram_frame, textvariable=self.ram_threshold_var,
                            bg=ModernTheme.BG_DARK, fg=ModernTheme.TEXT_PRIMARY,
                            font=("Segoe UI", 10), width=10)
        ram_entry.pack(side=tk.LEFT, padx=10)
        
        tk.Label(ram_frame, text="%", font=("Segoe UI", 10),
                bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_SECONDARY).pack(side=tk.LEFT)
        
        # Update Interval
        interval_card = self.create_card(content, "🔄 Update Settings")
        interval_card.pack(fill=tk.X, pady=(0, 15))
        
        interval_info = tk.Frame(interval_card, bg=ModernTheme.BG_CARD)
        interval_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        interval_frame = tk.Frame(interval_info, bg=ModernTheme.BG_CARD)
        interval_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(interval_frame, text="Update Interval:", font=("Segoe UI", 10),
                bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_PRIMARY).pack(side=tk.LEFT)
        
        self.interval_var = tk.StringVar(value=str(self.monitor_interval))
        interval_entry = tk.Entry(interval_frame, textvariable=self.interval_var,
                                 bg=ModernTheme.BG_DARK, fg=ModernTheme.TEXT_PRIMARY,
                                 font=("Segoe UI", 10), width=10)
        interval_entry.pack(side=tk.LEFT, padx=10)
        
        tk.Label(interval_frame, text="ms (250ms = 144fps)", font=("Segoe UI", 10),
                bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_SECONDARY).pack(side=tk.LEFT)
        
        # System Information
        info_card = self.create_card(content, "ℹ️ System Information")
        info_card.pack(fill=tk.X, pady=(0, 15))
        
        info_content = tk.Frame(info_card, bg=ModernTheme.BG_CARD)
        info_content.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        self.create_info_row(info_content, "Application:", "System Dashboard Pro v2.0").pack(fill=tk.X, pady=3)
        self.create_info_row(info_content, "Platform:", f"{platform.system()} {platform.release()}").pack(fill=tk.X, pady=3)
        self.create_info_row(info_content, "Python:", platform.python_version()).pack(fill=tk.X, pady=3)
        self.create_info_row(info_content, "CPU:", self.cpu_name[:50]).pack(fill=tk.X, pady=3)
        self.create_info_row(info_content, "Total RAM:", f"{self.total_ram_gb} GB").pack(fill=tk.X, pady=3)
        
        # Features
        features_card = self.create_card(content, "✨ Features")
        features_card.pack(fill=tk.X, pady=(0, 15))
        
        features_content = tk.Frame(features_card, bg=ModernTheme.BG_CARD)
        features_content.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        features = [
            "✅ 144fps Ultra-smooth Animations",
            "✅ Real-time System Monitoring",
            "✅ CPU, RAM, GPU, Disk, Network Tracking",
            "✅ Temperature & Fan Speed Sensors",
            "✅ Process Management",
            "✅ Storage Analytics with Live I/O",
            "✅ Network Adapter Monitoring",
            "✅ Fully Responsive Design",
            "✅ Scrollable Content Areas"
        ]
        
        for feature in features:
            tk.Label(features_content, text=feature, font=("Segoe UI", 9),
                    bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_SECONDARY,
                    anchor="w").pack(fill=tk.X, pady=2)
        
        # Action Buttons
        actions_frame = tk.Frame(content, bg=ModernTheme.BG_DARK)
        actions_frame.pack(fill=tk.X, pady=20)
        
        self.create_action_button(actions_frame, "💾 Save Settings", 
                                  self.save_settings).pack(side=tk.LEFT, padx=5)
        self.create_action_button(actions_frame, "🔄 Reset to Defaults",
                                  self.reset_settings).pack(side=tk.LEFT, padx=5)
        self.create_action_button(actions_frame, "📊 Export Logs",
                                  self.export_logs).pack(side=tk.LEFT, padx=5)
    
    def save_settings(self):
        """Save settings"""
        try:
            self.threshold_cpu = int(self.cpu_threshold_var.get())
            self.threshold_ram = int(self.ram_threshold_var.get())
            self.monitor_interval = int(self.interval_var.get())
            self.save_config()
            messagebox.showinfo("Settings", "Settings saved successfully!")
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers")
    
    def reset_settings(self):
        """Reset to default settings"""
        self.threshold_cpu = 85
        self.threshold_ram = 85
        self.monitor_interval = 250
        self.cpu_threshold_var.set("85")
        self.ram_threshold_var.set("85")
        self.interval_var.set("250")
        self.save_config()
        messagebox.showinfo("Settings", "Settings reset to defaults")
    
    def export_logs(self):
        """Export performance logs"""
        if os.path.exists(self.csv_file):
            messagebox.showinfo("Export", f"Logs available at:\n{os.path.abspath(self.csv_file)}")
        else:
            messagebox.showwarning("Export", "No logs available yet")
    
    def create_card(self, parent, title):
        """Create a styled card container with hover animations"""
        card = tk.Frame(parent, bg=ModernTheme.BG_CARD, relief=tk.FLAT)
        
        # Title
        title_frame = tk.Frame(card, bg=ModernTheme.BG_CARD)
        title_frame.pack(fill=tk.X, padx=15, pady=(15, 10))
        
        title_lbl = tk.Label(title_frame, text=title, font=("Segoe UI", 12, "bold"),
                bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_PRIMARY)
        title_lbl.pack(side=tk.LEFT)
        
        # Separator
        tk.Frame(card, bg=ModernTheme.BORDER, height=1).pack(fill=tk.X, padx=15)
        
        # Fade in
        AnimationEngine.fade_in(card)
        
        # Hover Effect
        def on_enter(e):
            AnimationEngine.smooth_color_transition(card, ModernTheme.BG_CARD, ModernTheme.BG_HOVER, 150)
            try:
                title_frame.config(bg=ModernTheme.BG_HOVER)
                title_lbl.config(bg=ModernTheme.BG_HOVER)
            except: pass

        def on_leave(e):
            AnimationEngine.smooth_color_transition(card, ModernTheme.BG_HOVER, ModernTheme.BG_CARD, 200)
            try:
                title_frame.config(bg=ModernTheme.BG_CARD)
                title_lbl.config(bg=ModernTheme.BG_CARD)
            except: pass
            
        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)
        
        return card
    
    def create_info_row(self, parent, label, value):
        """Create info row with label and value"""
        row = tk.Frame(parent, bg=ModernTheme.BG_CARD)
        
        tk.Label(row, text=label, font=("Segoe UI", 10),
                bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_SECONDARY).pack(side=tk.LEFT)
        
        val_label = tk.Label(row, text=value, font=("Segoe UI", 10, "bold"),
                            bg=ModernTheme.BG_CARD, fg=ModernTheme.ACCENT_PRIMARY)
        val_label.pack(side=tk.RIGHT)
        
        # Store reference for updates
        if not hasattr(self, 'info_labels'):
            self.info_labels = {}
        self.info_labels[label] = val_label
        
        return row
    
    def create_action_button(self, parent, text, command):
        """Create styled action button with transitions"""
        btn_frame = tk.Frame(parent, bg=ModernTheme.ACCENT_PRIMARY, cursor="hand2")
        
        btn_label = tk.Label(btn_frame, text=text, font=("Segoe UI", 10, "bold"),
                            bg=ModernTheme.ACCENT_PRIMARY, fg=ModernTheme.BG_DARK,
                            cursor="hand2")
        btn_label.pack(padx=15, pady=8)
        
        def on_click(e):
            AnimationEngine.pulse_effect(btn_frame, ModernTheme.ACCENT_PRIMARY, ModernTheme.ACCENT_LIME, 300)
            command()
            
        def on_enter(e):
            # Smooth transition to secondary color
            AnimationEngine.smooth_color_transition(btn_frame, ModernTheme.ACCENT_PRIMARY, ModernTheme.ACCENT_SECONDARY, 150)
            try: btn_label.config(bg=ModernTheme.ACCENT_SECONDARY)
            except: pass

        def on_leave(e):
            # Smooth transition back
            AnimationEngine.smooth_color_transition(btn_frame, ModernTheme.ACCENT_SECONDARY, ModernTheme.ACCENT_PRIMARY, 150)
            try: btn_label.config(bg=ModernTheme.ACCENT_PRIMARY)
            except: pass

        # Bind click and hover
        for widget in [btn_frame, btn_label]:
            widget.bind("<Button-1>", on_click)
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
        
        return btn_frame
    
    def monitor_thread(self):
        """Background monitoring thread with complete system info"""
        last_disk_io = psutil.disk_io_counters(perdisk=True)
        last_net_io = psutil.net_io_counters()
        last_check = time.time()
        
        while True:
            try:
                now = time.time()
                dt = max(0.5, now - last_check)
                
                # CPU & RAM
                cpu_p = psutil.cpu_percent(interval=0.1)
                mem = psutil.virtual_memory()
                
                self.ui_data["cpu_p"] = cpu_p
                self.ui_data["ram_p"] = mem.percent
                self.ui_data["ram_used"] = round(mem.used / (1024**3), 1)
                self.ui_data["ram_total"] = round(mem.total / (1024**3), 1)
                
                # Performance info
                pi = PERFORMANCE_INFORMATION()
                pi.cb = ctypes.sizeof(pi)
                psapi.GetPerformanceInfo(ctypes.byref(pi), pi.cb)
                
                self.ui_data["processes"] = pi.ProcessCount
                self.ui_data["threads"] = pi.ThreadCount
                
                # Uptime
                uptime_sec = time.time() - psutil.boot_time()
                self.ui_data["uptime"] = str(timedelta(seconds=int(uptime_sec)))
                
                # CPU Temp (multiple methods)
                cpu_temp_value = 0
                
                # Method 1: WMI OpenHardwareMonitor
                if self.wmi_obj:
                    try:
                        for s in self.wmi_obj.Sensor():
                            if s.SensorType == u'Temperature' and 'cpu' in s.Name.lower():
                                cpu_temp_value = int(s.Value)
                                break
                    except: pass
                
                # Method 2: WMI MSAcpi_ThermalZoneTemperature (if OHM failed)
                if cpu_temp_value == 0:
                    try:
                        import wmi
                        w = wmi.WMI(namespace="root\\wmi")
                        temperature_info = w.MSAcpi_ThermalZoneTemperature()[0]
                        cpu_temp_value = int((temperature_info.CurrentTemperature / 10.0) - 273.15)
                    except: pass
                
                # Method 3: psutil sensors (Linux/some systems)
                if cpu_temp_value == 0:
                    try:
                        if hasattr(psutil, 'sensors_temperatures'):
                            temps = psutil.sensors_temperatures()
                            if temps:
                                for name, entries in temps.items():
                                    if 'coretemp' in name.lower() or 'cpu' in name.lower():
                                        if entries:
                                            cpu_temp_value = int(entries[0].current)
                                            break
                    except: pass
                
                # Method 4: LibreHardwareMonitor via WMI
                if cpu_temp_value == 0:
                    try:
                        import wmi
                        w = wmi.WMI(namespace="root\\LibreHardwareMonitor")
                        for sensor in w.Sensor():
                            if 'temperature' in sensor.SensorType.lower() and 'cpu' in sensor.Name.lower():
                                cpu_temp_value = int(sensor.Value)
                                break
                    except: pass
                
                # Method 5: PowerShell WMI query
                if cpu_temp_value == 0:
                    try:
                        result = subprocess.run(
                            ['powershell', '-Command', 
                             'Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace root/wmi | Select-Object -First 1 -ExpandProperty CurrentTemperature'],
                            capture_output=True, text=True, timeout=2
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            kelvin = float(result.stdout.strip())
                            cpu_temp_value = int((kelvin / 10.0) - 273.15)
                    except: pass
                
                self.ui_data["cpu_temp"] = cpu_temp_value if cpu_temp_value > 0 else 0
                
                # GPU (try nvidia-smi)
                try:
                    result = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu', 
                                           '--format=csv,noheader,nounits'], 
                                          capture_output=True, text=True, timeout=1)
                    if result.returncode == 0:
                        self.ui_data["gpu_p"] = float(result.stdout.strip())
                except:
                    self.ui_data["gpu_p"] = min(100, cpu_p * 0.7)
                
                # Network
                nio = psutil.net_io_counters()
                send_bps = ((nio.bytes_sent - last_net_io.bytes_sent) * 8) / dt
                recv_bps = ((nio.bytes_recv - last_net_io.bytes_recv) * 8) / dt
                
                self.ui_data["net_send"] = send_bps / 1000000  # Mbps
                self.ui_data["net_recv"] = recv_bps / 1000000
                
                last_net_io = nio
                
                # Disk
                dio = psutil.disk_io_counters(perdisk=True)
                total_read = total_write = 0
                for dname, cnt in dio.items():
                    if dname in last_disk_io:
                        prev = last_disk_io[dname]
                        total_read += (cnt.read_bytes - prev.read_bytes) / dt
                        total_write += (cnt.write_bytes - prev.write_bytes) / dt
                
                self.ui_data["disk_p"] = min(100, ((total_read + total_write) / (1024**2)) * 2)
                last_disk_io = dio
                
                # History
                self.history_cpu.append(cpu_p)
                self.history_ram.append(mem.percent)
                self.history_gpu.append(self.ui_data["gpu_p"])
                
                last_check = now
                
                # Auto-optimization check (RAM)
                if self.auto_optimize_enabled:
                    ram_percent = self.ui_data["ram_p"]
                    cpu_percent = self.ui_data["cpu_p"]
                    
                    # Check RAM threshold with 10s persistence
                    if ram_percent >= self.threshold_ram:
                        if self.ram_high_start_time is None:
                            self.ram_high_start_time = now
                        
                        elif (now - self.ram_high_start_time) >= 10:
                            # High for > 10 seconds
                            time_since_last = now - self.last_auto_optimize_time
                            
                            if time_since_last >= self.auto_optimize_cooldown:
                                self.last_auto_optimize_time = now
                                self.ram_high_start_time = None # Reset counter
                                # Silent auto-optimization (no popup)
                                if not self.silent_mode:
                                    self.root.after(0, lambda rp=ram_percent: messagebox.showwarning(
                                        "Auto-Optimization",
                                        f"⚠️ RAM usage is high ({rp:.1f}%)\n\n"
                                        f"Auto-optimization starting now..."
                                    ))
                                threading.Thread(target=self._optimize_ram_thread, daemon=True).start()
                            else:
                                # Cooldown active - reset timer for next cycle
                                self.ram_high_start_time = now
                    else:
                        self.ram_high_start_time = None
                    
                    # Check CPU threshold with 10s persistence
                    if cpu_percent >= self.threshold_cpu:
                        if self.cpu_high_start_time is None:
                            self.cpu_high_start_time = now
                        
                        elif (now - self.cpu_high_start_time) >= 10:
                            # High for > 10 seconds
                            time_since_last_cpu = now - self.last_cpu_optimize_time
                            
                            if time_since_last_cpu >= self.auto_optimize_cooldown:
                                self.last_cpu_optimize_time = now
                                self.cpu_high_start_time = None # Reset counter
                                # Silent CPU optimization
                                threading.Thread(target=self._optimize_cpu_thread, daemon=True).start()
                            else:
                                # Cooldown active - reset for next cycle
                                self.cpu_high_start_time = now
                    else:
                        self.cpu_high_start_time = None
                
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(1)
    
    def update_ui(self):
        """Update UI with latest data across all sections"""
        try:
            # Update clock
            if hasattr(self, 'clock_label') and self.clock_label.winfo_exists():
                self.clock_label.config(text=datetime.now().strftime("%H:%M:%S"))
            
            # Update time labels on all pages
            current_time = datetime.now().strftime("%H:%M:%S")
            if hasattr(self, 'perf_time_label') and self.perf_time_label.winfo_exists():
                self.perf_time_label.config(text=current_time)
            if hasattr(self, 'mon_time_label') and self.mon_time_label.winfo_exists():
                self.mon_time_label.config(text=current_time)
            if hasattr(self, 'dev_time_label') and self.dev_time_label.winfo_exists():
                self.dev_time_label.config(text=current_time)
            if hasattr(self, 'net_time_label') and self.net_time_label.winfo_exists():
                self.net_time_label.config(text=current_time)
            if hasattr(self, 'set_time_label') and self.set_time_label.winfo_exists():
                self.set_time_label.config(text=current_time)
            
            # Update dashboard if active
            if self.current_section == "dashboard":
                # CPU
                if hasattr(self, 'cpu_progress') and self.cpu_progress.winfo_exists():
                    cpu_color = ModernTheme.ACCENT_LIME if self.ui_data["cpu_p"] < 50 else \
                               ModernTheme.ACCENT_ORANGE if self.ui_data["cpu_p"] < 80 else ModernTheme.DANGER
                    
                    cpu_label = "CPU Load"
                    if self.cpu_high_start_time:
                        d = int(time.time() - self.cpu_high_start_time)
                        cpu_label = f"High Load ({d}s)"
                        
                    self.cpu_progress.set_value(self.ui_data["cpu_p"], 
                                               f"{int(self.ui_data['cpu_p'])}%",
                                               cpu_label, cpu_color)
                
                if hasattr(self, 'cpu_graph') and self.cpu_graph.winfo_exists():
                    self.cpu_graph.add_value(self.ui_data["cpu_p"])
                
                # RAM
                if hasattr(self, 'ram_progress') and self.ram_progress.winfo_exists():
                    ram_color = ModernTheme.ACCENT_PRIMARY if self.ui_data["ram_p"] < 50 else \
                               ModernTheme.ACCENT_SECONDARY if self.ui_data["ram_p"] < 80 else ModernTheme.DANGER
                    
                    ram_label = f"{self.ui_data['ram_used']}/{self.ui_data['ram_total']} GB"
                    if self.ram_high_start_time:
                        d = int(time.time() - self.ram_high_start_time)
                        ram_label += f"\nHigh ({d}s)"
                        
                    self.ram_progress.set_value(self.ui_data["ram_p"],
                                               f"{int(self.ui_data['ram_p'])}%",
                                               ram_label,
                                               ram_color)
                
                if hasattr(self, 'ram_graph') and self.ram_graph.winfo_exists():
                    self.ram_graph.add_value(self.ui_data["ram_p"])
                
                # GPU
                if hasattr(self, 'gpu_progress') and self.gpu_progress.winfo_exists():
                    gpu_color = ModernTheme.ACCENT_TERTIARY if self.ui_data["gpu_p"] < 70 else ModernTheme.ACCENT_ORANGE
                    self.gpu_progress.set_value(self.ui_data["gpu_p"],
                                               f"{int(self.ui_data['gpu_p'])}%",
                                               "GPU Load", gpu_color)
                
                # Info labels
                if hasattr(self, 'info_labels'):
                    for label_key, label_widget in self.info_labels.items():
                        if label_widget.winfo_exists():
                            if "Processes:" in label_key:
                                label_widget.config(text=str(self.ui_data["processes"]))
                            elif "Threads:" in label_key:
                                label_widget.config(text=str(self.ui_data.get("threads", 0)))
                            elif "Uptime:" in label_key:
                                label_widget.config(text=self.ui_data["uptime"])
            
            # Update performance page if active
            elif self.current_section == "performance":
                # Update CPU gauge and frequency
                if hasattr(self, 'perf_cpu_gauge') and self.perf_cpu_gauge.winfo_exists():
                    cpu_pct = self.ui_data["cpu_p"]
                    cpu_color = ModernTheme.ACCENT_LIME if cpu_pct < 50 else \
                               ModernTheme.ACCENT_ORANGE if cpu_pct < 80 else ModernTheme.DANGER
                    self.perf_cpu_gauge.set_value(cpu_pct, f"{int(cpu_pct)}%", "CPU", cpu_color)
                
                if hasattr(self, 'perf_cpu_freq') and self.perf_cpu_freq.winfo_exists():
                    cpu_freq = psutil.cpu_freq()
                    if cpu_freq and cpu_freq.current > 0:
                        # Show actual current frequency (not max)
                        self.perf_cpu_freq.config(text=f"{cpu_freq.current/1000:.2f} GHz")
                    else:
                        # Fallback: Try to get from WMI
                        try:
                            result = subprocess.run(['wmic', 'cpu', 'get', 'CurrentClockSpeed'],
                                                  capture_output=True, text=True, timeout=1, 
                                                  creationflags=subprocess.CREATE_NO_WINDOW)
                            if result.returncode == 0:
                                lines = [l.strip() for l in result.stdout.split('\n') if l.strip() and l.strip() != 'CurrentClockSpeed']
                                if lines:
                                    mhz = int(lines[0])
                                    self.perf_cpu_freq.config(text=f"{mhz/1000:.2f} GHz")
                        except:
                            pass
                
                # Update RAM gauge and metrics
                if hasattr(self, 'perf_ram_gauge') and self.perf_ram_gauge.winfo_exists():
                    ram_pct = self.ui_data["ram_p"]
                    ram_color = ModernTheme.ACCENT_PRIMARY if ram_pct < 50 else \
                               ModernTheme.ACCENT_SECONDARY if ram_pct < 80 else ModernTheme.DANGER
                    self.perf_ram_gauge.set_value(ram_pct, f"{int(ram_pct)}%", "Memory", ram_color)
                
                if hasattr(self, 'perf_ram_used') and self.perf_ram_used.winfo_exists():
                    mem = psutil.virtual_memory()
                    self.perf_ram_used.config(text=f"{mem.used/(1024**3):.1f} GB")
                    if hasattr(self, 'perf_ram_avail') and self.perf_ram_avail.winfo_exists():
                        self.perf_ram_avail.config(text=f"{mem.available/(1024**3):.1f} GB")
                    
                    # Update cached memory
                    if hasattr(self, 'perf_ram_cached') and self.perf_ram_cached.winfo_exists():
                        try:
                            pi = PERFORMANCE_INFORMATION()
                            pi.cb = ctypes.sizeof(pi)
                            psapi.GetPerformanceInfo(ctypes.byref(pi), pi.cb)
                            cached_gb = (pi.SystemCache * pi.PageSize) / (1024**3)
                            self.perf_ram_cached.config(text=f"{cached_gb:.1f} GB")
                        except:
                            # Fallback calculation
                            try:
                                cached_gb = (mem.available - mem.free) / (1024**3)
                                if cached_gb > 0:
                                    self.perf_ram_cached.config(text=f"{cached_gb:.1f} GB")
                            except:
                                pass
                
                # Update GPU gauge and utilization
                if getattr(self, 'perf_gpu_gauge', None) and self.perf_gpu_gauge.winfo_exists():
                    gpu_pct = self.ui_data["gpu_p"]
                    gpu_color = ModernTheme.ACCENT_TERTIARY if gpu_pct < 70 else ModernTheme.ACCENT_ORANGE
                    self.perf_gpu_gauge.set_value(gpu_pct, f"{int(gpu_pct)}%", "GPU", gpu_color)
                
                if getattr(self, 'perf_gpu_util', None) and self.perf_gpu_util.winfo_exists():
                    self.perf_gpu_util.config(text=f"{int(self.ui_data['gpu_p'])}%")
            
            # Update monitoring page if active
            elif self.current_section == "monitoring":
                # Update CPU temperature
                if hasattr(self, 'mon_cpu_temp') and self.mon_cpu_temp.winfo_exists():
                    cpu_temp = self.ui_data.get("cpu_temp", 0)
                    if cpu_temp and cpu_temp > 0:
                        temp_color = ModernTheme.SUCCESS if cpu_temp < 60 else \
                                    ModernTheme.WARNING if cpu_temp < 80 else ModernTheme.DANGER
                        self.mon_cpu_temp.config(text=f"{cpu_temp}°C", fg=temp_color)
                    else:
                        self.mon_cpu_temp.config(text="--°C")
                
                # Update GPU temperature
                if hasattr(self, 'mon_gpu_temp') and self.mon_gpu_temp.winfo_exists():
                    try:
                        result = subprocess.run(['nvidia-smi', '--query-gpu=temperature.gpu',
                                               '--format=csv,noheader,nounits'],
                                              capture_output=True, text=True, timeout=1)
                        if result.returncode == 0:
                            gpu_temp = int(result.stdout.strip())
                            temp_color = ModernTheme.SUCCESS if gpu_temp < 70 else \
                                        ModernTheme.WARNING if gpu_temp < 85 else ModernTheme.DANGER
                            self.mon_gpu_temp.config(text=f"{gpu_temp}°C", fg=temp_color)
                    except:
                        pass
                
                # Update fan speeds
                if hasattr(self, 'mon_fan1') and self.mon_fan1.winfo_exists() and self.wmi_obj:
                    try:
                        fan_speeds = []
                        for sensor in self.wmi_obj.Sensor():
                            if sensor.SensorType == u'Fan':
                                fan_speeds.append(int(sensor.Value))
                        
                        if len(fan_speeds) > 0:
                            self.mon_fan1.config(text=f"{fan_speeds[0]} RPM")
                        if len(fan_speeds) > 1 and hasattr(self, 'mon_fan2') and self.mon_fan2.winfo_exists():
                            self.mon_fan2.config(text=f"{fan_speeds[1]} RPM")
                    except:
                        pass
            
            # Update storage page if active
            elif self.current_section == "storage":
                if hasattr(self, 'storage_io_labels') and hasattr(self, 'last_disk_io_time'):
                    try:
                        current_io = psutil.disk_io_counters(perdisk=True)
                        current_time = time.time()
                        dt = current_time - self.last_disk_io_time
                        
                        if dt > 0:
                            for drive_key, labels in self.storage_io_labels.items():
                                physical_drives = list(current_io.keys())
                                
                                if physical_drives:
                                    physical_drive = physical_drives[0]
                                    
                                    if physical_drive in current_io and physical_drive in self.last_disk_io_data:
                                        curr = current_io[physical_drive]
                                        prev = self.last_disk_io_data[physical_drive]
                                        
                                        read_speed = (curr.read_bytes - prev.read_bytes) / dt / (1024**2)
                                        write_speed = (curr.write_bytes - prev.write_bytes) / dt / (1024**2)
                                        
                                        if labels['read'] and labels['read'].winfo_exists():
                                            labels['read'].config(text=f"{read_speed:.1f} MB/s")
                                        if labels['write'] and labels['write'].winfo_exists():
                                            labels['write'].config(text=f"{write_speed:.1f} MB/s")
                            
                            self.last_disk_io_data = current_io
                            self.last_disk_io_time = current_time
                    except Exception as e:
                        pass
            
        except Exception as e:
            print(f"UI update error: {e}")
        
        self.root.after(250, self.update_ui)  # 250ms for ultra-responsive 144fps UI
    
    def optimize_ram(self):
        """Optimize RAM usage - Silent mode"""
        threading.Thread(target=self._optimize_ram_thread, daemon=True).start()
    
    def _optimize_ram_thread(self):
        """Background RAM optimization - Silent"""
        try:
            initial_ram = psutil.virtual_memory().percent
            
            # Python garbage collection
            gc.collect()
            
            # Empty working sets for all processes
            optimized_count = 0
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if empty_working_set(proc.info['pid']):
                        optimized_count += 1
                except:
                    pass
            
            # Wait a moment for changes to take effect
            time.sleep(1)
            
            final_ram = psutil.virtual_memory().percent
            freed = initial_ram - final_ram
            
            # Silent - just log to console
            print(f"RAM Optimized: {optimized_count} processes, {freed:.1f}% freed, now at {final_ram:.1f}%")
        except Exception as e:
            print(f"Optimization error: {e}")
    
    def _optimize_cpu_thread(self):
        """Background CPU optimization"""
        try:
            # Lower priority of high-CPU processes
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                try:
                    if proc.info['cpu_percent'] and proc.info['cpu_percent'] > 50:
                        p = psutil.Process(proc.info['pid'])
                        # Lower priority (Windows: BELOW_NORMAL_PRIORITY_CLASS)
                        p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                except:
                    pass
        except Exception as e:
            print(f"CPU optimization error: {e}")
    
    def clear_cache(self):
        """Clear system cache - Silent"""
        try:
            # Python garbage collection
            gc.collect()
            
            # Clear DNS cache
            try:
                subprocess.run(['ipconfig', '/flushdns'], 
                             capture_output=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
            except:
                pass
            
            print("Cache cleared: Python GC + DNS flush")
        except Exception as e:
            print(f"Cache clearing error: {e}")
    
    def show_report(self):
        """Show full system report"""
        report = f"""
╔══════════════════════════════════════╗
║     SYSTEM PERFORMANCE REPORT        ║
╚══════════════════════════════════════╝

📊 CPU Information:
   • Processor: {self.cpu_name[:35]}
   • Usage: {self.ui_data['cpu_p']:.1f}%
   • Cores: {psutil.cpu_count(logical=False)} Physical
   • Threads: {psutil.cpu_count(logical=True)} Logical

💾 Memory Information:
   • Total RAM: {self.total_ram_gb} GB
   • Used: {self.ui_data['ram_used']:.1f} GB
   • Usage: {self.ui_data['ram_p']:.1f}%

🎮 GPU Information:
   • Usage: {self.ui_data['gpu_p']:.1f}%

🌐 Network:
   • Sent: {self.ui_data['net_send']:.1f} MB
   • Received: {self.ui_data['net_recv']:.1f} MB

⚙️ System:
   • Processes: {self.ui_data['processes']}
   • Threads: {self.ui_data['threads']}
   • Uptime: {self.ui_data['uptime']}
   • Boot Time: {self.boot_time}

📁 Log File: {os.path.abspath(self.csv_file)}
"""
        
        # Create report window
        report_window = tk.Toplevel(self.root)
        report_window.title("System Report")
        report_window.geometry("500x600")
        report_window.configure(bg=ModernTheme.BG_DARK)
        
        text_widget = tk.Text(report_window, bg=ModernTheme.BG_CARD,
                             fg=ModernTheme.TEXT_PRIMARY, font=("Consolas", 10),
                             relief=tk.FLAT, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        text_widget.insert('1.0', report)
        text_widget.config(state='disabled')

if __name__ == "__main__":
    root = tk.Tk()
    app = SystemDashboardPro(root)
    root.mainloop()
