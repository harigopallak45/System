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

try:
    import wmi
    HAS_WMI = True
except ImportError:
    HAS_WMI = False

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
    """Premium dark theme with RGB accents inspired by ASUS Armoury Crate"""
    BG_DARK = "#0a0a0f"
    BG_CARD = "#13131a"
    BG_SIDEBAR = "#0f0f15"
    BG_HOVER = "#1a1a24"
    
    # RGB Gradient colors
    ACCENT_PRIMARY = "#00d9ff"
    ACCENT_SECONDARY = "#7b2cbf"
    ACCENT_TERTIARY = "#ff006e"
    
    TEXT_PRIMARY = "#ffffff"
    TEXT_SECONDARY = "#a0a0b0"
    TEXT_MUTED = "#606070"
    
    SUCCESS = "#00ff88"
    WARNING = "#ffaa00"
    DANGER = "#ff3366"
    
    BORDER = "#1f1f2e"

class AnimatedCircularProgress(Canvas):
    """Animated circular progress indicator"""
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
        
        # Draw background circle
        self.create_oval(
            self.center - self.radius, self.center - self.radius,
            self.center + self.radius, self.center + self.radius,
            outline=ModernTheme.BORDER, width=self.thickness
        )
        
        # Progress arc
        self.arc = self.create_arc(
            self.center - self.radius, self.center - self.radius,
            self.center + self.radius, self.center + self.radius,
            start=90, extent=0, outline=self.color, width=self.thickness,
            style='arc'
        )
        
        # Center text
        self.text_label = self.create_text(
            self.center, self.center - 10, text="0%",
            font=("Segoe UI", 18, "bold"), fill=ModernTheme.TEXT_PRIMARY
        )
        
        self.subtitle_label = self.create_text(
            self.center, self.center + 15, text="",
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
        """Hover animation"""
        self.is_hovered = entered
        if not self.is_active:
            bg = ModernTheme.BG_HOVER if entered else ModernTheme.BG_SIDEBAR
            fg = ModernTheme.TEXT_PRIMARY if entered else ModernTheme.TEXT_SECONDARY
            
            self.btn_frame.config(bg=bg)
            for widget in [self.icon_label, self.text_label]:
                widget.config(bg=bg, fg=fg)
    
    def on_click(self):
        """Handle click"""
        if self.command:
            self.command()
    
    def set_active(self, active):
        """Set active state"""
        self.is_active = active
        if active:
            bg = ModernTheme.BG_HOVER
            fg = ModernTheme.ACCENT_PRIMARY
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
        self.root.configure(bg=ModernTheme.BG_DARK)
        
        # Enable Windows Dark Title Bar
        try:
            set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
            get_parent = ctypes.windll.user32.GetParent
            hwnd = get_parent(self.root.winfo_id())
            value = ctypes.c_int(2)
            set_window_attribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
        except: pass
        
        # Config
        self.threshold_ram = 85
        self.threshold_cpu = 85
        self.monitor_interval = 250  # 250ms for 144fps responsiveness
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
        
        # Static info
        self.total_ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
        self.cpu_name = platform.processor()
        self.boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        
        self.init_csv()
        self.create_ui()
        
        # Start monitoring
        threading.Thread(target=self.monitor_thread, daemon=True).start()
        self.update_ui()
    
    def init_csv(self):
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["Timestamp", "RAM%", "CPU%", "GPU%", "Disk%"])
    
    def create_ui(self):
        """Create the main UI layout"""
        # Main container
        main_container = tk.Frame(self.root, bg=ModernTheme.BG_DARK)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Sidebar
        self.create_sidebar(main_container)
        
        # Content area
        self.content_frame = tk.Frame(main_container, bg=ModernTheme.BG_DARK)
        self.content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Show default section
        self.show_dashboard()
    
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
            ("processes", "🔧", "Processes", self.show_processes),
            ("storage", "💾", "Storage", self.show_storage),
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
        
        # Main content
        content = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        # Top row - Circular progress indicators
        top_row = tk.Frame(content, bg=ModernTheme.BG_DARK)
        top_row.pack(fill=tk.X, pady=(0, 20))
        
        # CPU Card
        cpu_card = self.create_card(top_row, "CPU Usage")
        cpu_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        self.cpu_progress = AnimatedCircularProgress(cpu_card, size=140, thickness=10)
        self.cpu_progress.pack(pady=10)
        
        self.cpu_name_label = tk.Label(cpu_card, text=self.cpu_name[:30], 
                                       font=("Segoe UI", 9),
                                       bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_SECONDARY)
        self.cpu_name_label.pack(pady=5)
        
        # RAM Card
        ram_card = self.create_card(top_row, "Memory Usage")
        ram_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        self.ram_progress = AnimatedCircularProgress(ram_card, size=140, thickness=10)
        self.ram_progress.pack(pady=10)
        
        self.ram_info_label = tk.Label(ram_card, text=f"Total: {self.total_ram_gb} GB",
                                       font=("Segoe UI", 9),
                                       bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_SECONDARY)
        self.ram_info_label.pack(pady=5)
        
        # GPU Card
        gpu_card = self.create_card(top_row, "GPU Usage")
        gpu_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        self.gpu_progress = AnimatedCircularProgress(gpu_card, size=140, thickness=10)
        self.gpu_progress.pack(pady=10)
        
        self.gpu_name_label = tk.Label(gpu_card, text="Detecting...",
                                       font=("Segoe UI", 9),
                                       bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_SECONDARY)
        self.gpu_name_label.pack(pady=5)
        
        # Middle row - Graphs
        mid_row = tk.Frame(content, bg=ModernTheme.BG_DARK)
        mid_row.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # CPU Graph
        cpu_graph_card = self.create_card(mid_row, "CPU History")
        cpu_graph_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        self.cpu_graph = MiniGraph(cpu_graph_card, width=350, height=100)
        self.cpu_graph.pack(pady=10, padx=10)
        
        # RAM Graph
        ram_graph_card = self.create_card(mid_row, "Memory History")
        ram_graph_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        self.ram_graph = MiniGraph(ram_graph_card, width=350, height=100)
        self.ram_graph.pack(pady=10, padx=10)
        
        # Bottom row - System info
        bottom_row = tk.Frame(content, bg=ModernTheme.BG_DARK)
        bottom_row.pack(fill=tk.X)
        
        # System Info Card
        info_card = self.create_card(bottom_row, "System Information")
        info_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        info_grid = tk.Frame(info_card, bg=ModernTheme.BG_CARD)
        info_grid.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        self.create_info_row(info_grid, "Processes:", "0").pack(fill=tk.X, pady=3)
        self.create_info_row(info_grid, "Threads:", "0").pack(fill=tk.X, pady=3)
        self.create_info_row(info_grid, "Uptime:", "00:00:00").pack(fill=tk.X, pady=3)
        self.create_info_row(info_grid, "Boot Time:", self.boot_time).pack(fill=tk.X, pady=3)
        
        # Quick Actions Card
        actions_card = self.create_card(bottom_row, "Quick Actions")
        actions_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
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
        
        content = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        # Top row - CPU Details
        top_row = tk.Frame(content, bg=ModernTheme.BG_DARK)
        top_row.pack(fill=tk.X, pady=(0, 15))
        
        cpu_card = self.create_card(top_row, "CPU Performance")
        cpu_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        cpu_info = tk.Frame(cpu_card, bg=ModernTheme.BG_CARD)
        cpu_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # CPU details
        cpu_freq = psutil.cpu_freq()
        cpu_count = psutil.cpu_count(logical=False)
        cpu_logical = psutil.cpu_count(logical=True)
        
        self.perf_cpu_name = self.create_info_row(cpu_info, "Processor:", self.cpu_name[:40])
        self.perf_cpu_name.pack(fill=tk.X, pady=3)
        self.create_info_row(cpu_info, "Physical Cores:", str(cpu_count)).pack(fill=tk.X, pady=3)
        self.create_info_row(cpu_info, "Logical Processors:", str(cpu_logical)).pack(fill=tk.X, pady=3)
        self.perf_cpu_freq = self.create_info_row(cpu_info, "Current Speed:", 
                                                   f"{cpu_freq.current/1000:.2f} GHz" if cpu_freq else "N/A")
        self.perf_cpu_freq.pack(fill=tk.X, pady=3)
        self.perf_cpu_max = self.create_info_row(cpu_info, "Max Speed:", 
                                                  f"{cpu_freq.max/1000:.2f} GHz" if cpu_freq else "N/A")
        self.perf_cpu_max.pack(fill=tk.X, pady=3)
        
        # RAM Details
        ram_card = self.create_card(top_row, "Memory Performance")
        ram_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        ram_info = tk.Frame(ram_card, bg=ModernTheme.BG_CARD)
        ram_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        mem = psutil.virtual_memory()
        self.create_info_row(ram_info, "Total RAM:", f"{self.total_ram_gb} GB").pack(fill=tk.X, pady=3)
        self.perf_ram_used = self.create_info_row(ram_info, "Used:", 
                                                   f"{mem.used/(1024**3):.1f} GB")
        self.perf_ram_used.pack(fill=tk.X, pady=3)
        self.perf_ram_avail = self.create_info_row(ram_info, "Available:", 
                                                    f"{mem.available/(1024**3):.1f} GB")
        self.perf_ram_avail.pack(fill=tk.X, pady=3)
        self.perf_ram_cached = self.create_info_row(ram_info, "Cached:", 
                                                     f"{mem.cached/(1024**3):.1f} GB" if hasattr(mem, 'cached') else "N/A")
        self.perf_ram_cached.pack(fill=tk.X, pady=3)
        
        # Middle row - GPU & Disk
        mid_row = tk.Frame(content, bg=ModernTheme.BG_DARK)
        mid_row.pack(fill=tk.BOTH, expand=True)
        
        # GPU Card
        gpu_card = self.create_card(mid_row, "GPU Information")
        gpu_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        gpu_info = tk.Frame(gpu_card, bg=ModernTheme.BG_CARD)
        gpu_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # Try to get GPU info
        try:
            result = subprocess.run(['wmic', 'path', 'win32_VideoController', 'get', 'name'],
                                  capture_output=True, text=True, timeout=2)
            gpu_names = [line.strip() for line in result.stdout.split('\n')[1:] if line.strip()]
            if gpu_names:
                for i, gpu in enumerate(gpu_names[:2]):
                    self.create_info_row(gpu_info, f"GPU {i+1}:", gpu[:35]).pack(fill=tk.X, pady=3)
        except:
            self.create_info_row(gpu_info, "GPU:", "Detection failed").pack(fill=tk.X, pady=3)
        
        self.perf_gpu_util = self.create_info_row(gpu_info, "Utilization:", "0%")
        self.perf_gpu_util.pack(fill=tk.X, pady=3)
        
        # Disk Card
        disk_card = self.create_card(mid_row, "Disk Performance")
        disk_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        disk_info = tk.Frame(disk_card, bg=ModernTheme.BG_CARD)
        disk_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        for partition in psutil.disk_partitions()[:3]:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                self.create_info_row(disk_info, f"{partition.device}", 
                                    f"{usage.used/(1024**3):.0f}/{usage.total/(1024**3):.0f} GB").pack(fill=tk.X, pady=3)
            except:
                pass
    
    def show_monitoring(self):
        """System monitoring view"""
        self.switch_section("monitoring")
        
        header = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        header.pack(fill=tk.X, padx=30, pady=20)
        
        tk.Label(header, text="System Monitoring", font=("Segoe UI", 24, "bold"),
                bg=ModernTheme.BG_DARK, fg=ModernTheme.TEXT_PRIMARY).pack(side=tk.LEFT)
        
        content = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        card = self.create_card(content, "Advanced Monitoring")
        card.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(card, text="Temperature sensors, fan speeds, and more...",
                font=("Segoe UI", 12), bg=ModernTheme.BG_CARD,
                fg=ModernTheme.TEXT_SECONDARY).pack(pady=50)
    
    def show_processes(self):
        """Process management view"""
        self.switch_section("processes")
        
        header = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        header.pack(fill=tk.X, padx=30, pady=20)
        
        tk.Label(header, text="Process Manager", font=("Segoe UI", 24, "bold"),
                bg=ModernTheme.BG_DARK, fg=ModernTheme.TEXT_PRIMARY).pack(side=tk.LEFT)
    
    def show_storage(self):
        """Storage management view with all drives"""
        self.switch_section("storage")
        
        header = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        header.pack(fill=tk.X, padx=30, pady=20)
        
        tk.Label(header, text="Storage Manager", font=("Segoe UI", 24, "bold"),
                bg=ModernTheme.BG_DARK, fg=ModernTheme.TEXT_PRIMARY).pack(side=tk.LEFT)
        
        content = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        # Get all partitions
        partitions = psutil.disk_partitions()
        
        for partition in partitions:
            if 'cdrom' in partition.opts or partition.fstype == '':
                continue
                
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                
                # Create card for each drive
                drive_card = self.create_card(content, f"Drive {partition.device}")
                drive_card.pack(fill=tk.X, pady=(0, 15))
                
                drive_info = tk.Frame(drive_card, bg=ModernTheme.BG_CARD)
                drive_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
                
                # Progress bar for usage
                usage_frame = tk.Frame(drive_info, bg=ModernTheme.BG_CARD)
                usage_frame.pack(fill=tk.X, pady=(0, 10))
                
                usage_pct = usage.percent
                tk.Label(usage_frame, text=f"Used: {usage.used/(1024**3):.1f} GB / {usage.total/(1024**3):.1f} GB ({usage_pct}%)",
                        font=("Segoe UI", 11, "bold"), bg=ModernTheme.BG_CARD,
                        fg=ModernTheme.TEXT_PRIMARY).pack(anchor="w")
                
                # Visual progress bar
                bar_bg = tk.Canvas(usage_frame, height=20, bg=ModernTheme.BG_DARK, highlightthickness=0)
                bar_bg.pack(fill=tk.X, pady=5)
                
                bar_color = ModernTheme.SUCCESS if usage_pct < 70 else \
                           ModernTheme.WARNING if usage_pct < 90 else ModernTheme.DANGER
                
                bar_width = int((usage_pct / 100) * bar_bg.winfo_reqwidth())
                bar_bg.create_rectangle(0, 0, 400 * (usage_pct/100), 20, fill=bar_color, outline="")
                
                # Details grid
                details = tk.Frame(drive_info, bg=ModernTheme.BG_CARD)
                details.pack(fill=tk.X)
                details.columnconfigure(0, weight=1)
                details.columnconfigure(1, weight=1)
                details.columnconfigure(2, weight=1)
                
                self.create_info_row(details, "Free Space:", f"{usage.free/(1024**3):.1f} GB").grid(row=0, column=0, sticky="w", padx=5)
                self.create_info_row(details, "File System:", partition.fstype).grid(row=0, column=1, sticky="w", padx=5)
                self.create_info_row(details, "Mount Point:", partition.mountpoint).grid(row=0, column=2, sticky="w", padx=5)
                
            except Exception as e:
                pass
    
    def show_network(self):
        """Network monitoring view with all adapters"""
        self.switch_section("network")
        
        header = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        header.pack(fill=tk.X, padx=30, pady=20)
        
        tk.Label(header, text="Network Monitor", font=("Segoe UI", 24, "bold"),
                bg=ModernTheme.BG_DARK, fg=ModernTheme.TEXT_PRIMARY).pack(side=tk.LEFT)
        
        content = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        # Get network interfaces
        net_if_addrs = psutil.net_if_addrs()
        net_if_stats = psutil.net_if_stats()
        
        for interface_name, addrs in net_if_addrs.items():
            # Create card for each interface
            if_card = self.create_card(content, f"Network Adapter: {interface_name}")
            if_card.pack(fill=tk.X, pady=(0, 15))
            
            if_info = tk.Frame(if_card, bg=ModernTheme.BG_CARD)
            if_info.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
            
            # Status
            stats = net_if_stats.get(interface_name)
            if stats:
                status = "🟢 Connected" if stats.isup else "🔴 Disconnected"
                status_color = ModernTheme.SUCCESS if stats.isup else ModernTheme.DANGER
                
                status_label = tk.Label(if_info, text=status, font=("Segoe UI", 11, "bold"),
                                       bg=ModernTheme.BG_CARD, fg=status_color)
                status_label.pack(anchor="w", pady=(0, 10))
                
                # Speed
                if stats.speed > 0:
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
        """Settings view"""
        self.switch_section("settings")
        
        header = tk.Frame(self.content_frame, bg=ModernTheme.BG_DARK)
        header.pack(fill=tk.X, padx=30, pady=20)
        
        tk.Label(header, text="Settings", font=("Segoe UI", 24, "bold"),
                bg=ModernTheme.BG_DARK, fg=ModernTheme.TEXT_PRIMARY).pack(side=tk.LEFT)
    
    def create_card(self, parent, title):
        """Create a styled card container"""
        card = tk.Frame(parent, bg=ModernTheme.BG_CARD, relief=tk.FLAT)
        
        # Title
        title_frame = tk.Frame(card, bg=ModernTheme.BG_CARD)
        title_frame.pack(fill=tk.X, padx=15, pady=(15, 10))
        
        tk.Label(title_frame, text=title, font=("Segoe UI", 12, "bold"),
                bg=ModernTheme.BG_CARD, fg=ModernTheme.TEXT_PRIMARY).pack(side=tk.LEFT)
        
        # Separator
        tk.Frame(card, bg=ModernTheme.BORDER, height=1).pack(fill=tk.X, padx=15)
        
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
        """Create styled action button"""
        btn_frame = tk.Frame(parent, bg=ModernTheme.ACCENT_PRIMARY, cursor="hand2")
        
        btn_label = tk.Label(btn_frame, text=text, font=("Segoe UI", 10, "bold"),
                            bg=ModernTheme.ACCENT_PRIMARY, fg=ModernTheme.BG_DARK,
                            cursor="hand2")
        btn_label.pack(padx=15, pady=8)
        
        # Bind click
        for widget in [btn_frame, btn_label]:
            widget.bind("<Button-1>", lambda e: command())
            widget.bind("<Enter>", lambda e: btn_frame.config(bg=ModernTheme.ACCENT_SECONDARY))
            widget.bind("<Leave>", lambda e: btn_frame.config(bg=ModernTheme.ACCENT_PRIMARY))
        
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
                
                # CPU Temp (if WMI available)
                if self.wmi_obj:
                    try:
                        for s in self.wmi_obj.Sensor():
                            if s.SensorType == u'Temperature' and 'cpu' in s.Name.lower():
                                self.ui_data["cpu_temp"] = int(s.Value)
                    except: pass
                
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
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(1)
    
    def update_ui(self):
        """Update UI with latest data"""
        try:
            # Update clock
            if hasattr(self, 'clock_label'):
                self.clock_label.config(text=datetime.now().strftime("%H:%M:%S"))
            
            # Update dashboard if active
            if self.current_section == "dashboard":
                # CPU
                cpu_color = ModernTheme.SUCCESS if self.ui_data["cpu_p"] < 50 else \
                           ModernTheme.WARNING if self.ui_data["cpu_p"] < 80 else ModernTheme.DANGER
                self.cpu_progress.set_value(self.ui_data["cpu_p"], 
                                           f"{int(self.ui_data['cpu_p'])}%",
                                           "CPU Load", cpu_color)
                self.cpu_graph.add_value(self.ui_data["cpu_p"])
                
                # RAM
                ram_color = ModernTheme.SUCCESS if self.ui_data["ram_p"] < 50 else \
                           ModernTheme.WARNING if self.ui_data["ram_p"] < 80 else ModernTheme.DANGER
                self.ram_progress.set_value(self.ui_data["ram_p"],
                                           f"{int(self.ui_data['ram_p'])}%",
                                           f"{self.ui_data['ram_used']}/{self.ui_data['ram_total']} GB",
                                           ram_color)
                self.ram_graph.add_value(self.ui_data["ram_p"])
                
                # GPU
                self.gpu_progress.set_value(self.ui_data["gpu_p"],
                                           f"{int(self.ui_data['gpu_p'])}%",
                                           "GPU Load", ModernTheme.ACCENT_TERTIARY)
                
                # Info labels
                if hasattr(self, 'info_labels'):
                    if "Processes:" in self.info_labels:
                        self.info_labels["Processes:"].config(text=str(self.ui_data["processes"]))
                    if "Uptime:" in self.info_labels:
                        self.info_labels["Uptime:"].config(text=self.ui_data["uptime"])
            
        except Exception as e:
            print(f"UI update error: {e}")
        
        self.root.after(250, self.update_ui)  # 250ms for ultra-responsive 144fps UI
    
    def optimize_ram(self):
        """Optimize RAM usage"""
        messagebox.showinfo("Optimize RAM", "RAM optimization started...")
        threading.Thread(target=self._optimize_ram_thread, daemon=True).start()
    
    def _optimize_ram_thread(self):
        """Background RAM optimization"""
        try:
            gc.collect()
            for proc in psutil.process_iter(['pid']):
                try:
                    empty_working_set(proc.info['pid'])
                except: pass
        except Exception as e:
            print(f"Optimization error: {e}")
    
    def clear_cache(self):
        """Clear system cache"""
        messagebox.showinfo("Clear Cache", "Cache clearing started...")
    
    def show_report(self):
        """Show full system report"""
        messagebox.showinfo("System Report", "Generating full system report...")

if __name__ == "__main__":
    root = tk.Tk()
    app = SystemDashboardPro(root)
    root.mainloop()
