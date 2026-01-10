import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
import threading
import ctypes
import gc
import psutil
import time
import csv
import os
import subprocess
import platform
import urllib.request
from collections import deque
from datetime import datetime, timedelta

try:
    import wmi
    HAS_WMI = True
except ImportError:
    HAS_WMI = False

# Optional: Matplotlib for graphing
try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

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

class DEVMODE(ctypes.Structure):
    _fields_ = [
        ('dmDeviceName', ctypes.c_char * 32),
        ('dmSpecVersion', ctypes.c_short),
        ('dmDriverVersion', ctypes.c_short),
        ('dmSize', ctypes.c_short),
        ('dmDriverExtra', ctypes.c_short),
        ('dmFields', ctypes.c_int),
        ('dmOrientation', ctypes.c_short),
        ('dmPaperSize', ctypes.c_short),
        ('dmPaperLength', ctypes.c_short),
        ('dmPaperWidth', ctypes.c_short),
        ('dmScale', ctypes.c_short),
        ('dmCopies', ctypes.c_short),
        ('dmDefaultSource', ctypes.c_short),
        ('dmPrintQuality', ctypes.c_short),
        ('dmColor', ctypes.c_short),
        ('dmDuplex', ctypes.c_short),
        ('dmYResolution', ctypes.c_short),
        ('dmTTOption', ctypes.c_short),
        ('dmCollate', ctypes.c_short),
        ('dmFormName', ctypes.c_char * 32),
        ('dmLogPixels', ctypes.c_short),
        ('dmBitsPerPel', ctypes.c_int),
        ('dmPelsWidth', ctypes.c_int),
        ('dmPelsHeight', ctypes.c_int),
        ('dmDisplayFlags', ctypes.c_int),
        ('dmDisplayFrequency', ctypes.c_int),
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

class ModernDarkTheme:
    """Helper to configure a modern dark look for ttk widgets."""
    BG_COLOR = "#0f0f0f"
    FG_COLOR = "#f0f0f0"
    ACCENT_COLOR = "#00e5ff"
    CARD_BG = "#1a1a1a"
    SUCCESS_COLOR = "#00e676"
    WARNING_COLOR = "#ffea00"
    
    @staticmethod
    def apply_theme(root):
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure(".", background=ModernDarkTheme.BG_COLOR, foreground=ModernDarkTheme.FG_COLOR, font=("Segoe UI", 10))
        style.configure("TLabel", background=ModernDarkTheme.BG_COLOR, foreground=ModernDarkTheme.FG_COLOR)
        style.configure("TButton", background=ModernDarkTheme.ACCENT_COLOR, foreground="#000000", borderwidth=0, padding=10, font=("Segoe UI", 10, "bold"))
        style.map("TButton", background=[("active", "#00b8d4")])
        style.configure("Card.TFrame", background=ModernDarkTheme.CARD_BG, relief="flat")
        style.configure("Header.TLabel", font=("Segoe UI", 20, "bold"), background=ModernDarkTheme.BG_COLOR, foreground=ModernDarkTheme.ACCENT_COLOR)
        style.configure("CardHeader.TLabel", font=("Segoe UI", 12, "bold"), background=ModernDarkTheme.CARD_BG, foreground="#ffffff")
        style.configure("CardValue.TLabel", font=("Segoe UI", 14, "bold"), background=ModernDarkTheme.CARD_BG, foreground=ModernDarkTheme.ACCENT_COLOR)
        style.configure("CardSub.TLabel", font=("Segoe UI", 10), background=ModernDarkTheme.CARD_BG, foreground="#aaaaaa")
        root.configure(bg=ModernDarkTheme.BG_COLOR)
        return style

class RamCleanerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("System Dashboard Pro")
        self.root.geometry("1100x750")
        
        # Enable Windows Dark Title Bar
        try:
            # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
            get_parent = ctypes.windll.user32.GetParent
            hwnd = get_parent(self.root.winfo_id())
            value = ctypes.c_int(2)
            set_window_attribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value))
        except: pass
        
        self.style = ModernDarkTheme.apply_theme(self.root)

        # Config
        self.threshold_ram = 85
        self.threshold_cpu = 85
        self.last_opt_time = 0
        self.monitor_interval = 500 # 0.5s refresh for realtime UI
        self.csv_file = "system_performance_log.csv"
        
        self.wmi_obj = None
        if HAS_WMI:
            try:
                self.wmi_obj = wmi.WMI(namespace="root\\OpenHardwareMonitor")
            except Exception: 
                pass # Namespace not found or WMI error
        
        self.last_disk_io = psutil.disk_io_counters(perdisk=True)
        self.last_net_io = psutil.net_io_counters()
        self.last_net_io_dict = psutil.net_io_counters(pernic=True)
        self.last_check_time = time.time()
        self.net_load_active = False
        
        # Shared Data Container (Thread-safe enough for GUI polling)
        self.ui_data = {
            "ram_p": 0, "ram_u": 0, "ram_f": 0,
            "ram_comp": "--", "ram_avail": "--", "ram_comm": "--", "ram_cached": "--",
            "ram_paged": "--", "ram_nonpaged": "--",
            "cpu": 0, "res": "--", "fps": "--", "monitors": "--",
            "proc": 0, "thr": 0, "hnd": 0, "uptime": "--", "speed": "--",
            "cpu_temp": "--", "fan_speed": "--",
            "bat_st": "--", "bat_lv": "--", "bat_fl": "--", "bat_ds": "--",
            "gpu_list": [], # List of GPU dicts
            "disk_sp": "0.0 MB/s", 
            "net_send": "0 Kbps", "net_recv": "0 Kbps",
            "net_adapter": "--", "net_type": "--", "net_ipv4": "--", "net_ipv6": "--",
            "drives_storage": "--", "disk_io_str": "Idle"
        }
        
        # Static Info (Fetched once)
        self.total_ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)
        self.cpu_name = platform.processor()
        self.boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        
        # Advanced Static Info
        self.gpu_static_list = self.get_gpu_static_advanced()
        self.cached_batt_cap, self.cached_batt_design = self.get_static_batt_info()
        self.cpu_static = self.get_cpu_static_advanced()
        self.ram_static = self.get_ram_static_advanced()
        self.disk_static = self.get_disk_static_advanced()
        
        # Realtime history for analytics (last 60 points)
        self.history = deque(maxlen=60)

        self.init_csv()
        self.create_widgets()
        
        # Start Background Monitor Thread (Prevents UI lag from subprocess calls)
        threading.Thread(target=self.monitor_thread, daemon=True).start()
        
        # Start UI Update Loop
        self.update_ui()

    def get_disk_static_advanced(self):
        disks = {}
        try:
            # 1. Get Physical Disk Info (Model, Type, Size) via PowerShell
            # We use PowerShell for MediaType detection (SSD/HDD)
            cmd = ["powershell", "-Command", "Get-PhysicalDisk | Select-Object DeviceID, Model, MediaType, Size, FriendlyName | ConvertTo-Json"]
            res = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
            
            import json
            if res:
                data = json.loads(res)
                if isinstance(data, dict): data = [data]
                for d in data:
                    did = f"PhysicalDrive{d['DeviceID']}"
                    disks[did] = {
                        "model": d['Model'],
                        "type": d['MediaType'] if d['MediaType'] else "Fixed",
                        "size": f"{int(d['Size'])/(1024**3):.0f} GB",
                        "system": "No",
                        "pagefile": "No"
                    }

            # 2. Identify System Disk and Pagefile
            # Check partitions
            for part in psutil.disk_partitions():
                if 'fixed' in part.opts:
                    drive_letter = part.mountpoint.split(':')[0].upper() + ':'
                    # Is System?
                    if drive_letter == os.environ.get('SystemDrive', 'C:').upper():
                        # Find which physical drive this belongs to
                        # Mapping logical to physical is complex in WMI, let's assume PhysicalDrive0 for C: usually
                        # Or use wmic to be sure
                        cmd = ["wmic", "partition", "get", "DeviceID,DiskIndex"]
                        # Logic to map is tedious, let's just mark the first drive as System if C is found
                        if disks:
                            first_key = list(disks.keys())[0]
                            disks[first_key]["system"] = "Yes"
                    
            # Check Pagefile
            cmd = ["wmic", "pagefile", "get", "Caption"]
            res = subprocess.run(cmd, capture_output=True, text=True).stdout.lower()
            if "pagefile.sys" in res and disks:
                first_key = list(disks.keys())[0]
                disks[first_key]["pagefile"] = "Yes"

        except: pass
        return disks

    def get_gpu_static_advanced(self):
        gpus = []
        try:
            # PowerShell to get VideoController info including Driver info
            cmd = ["powershell", "-Command", "Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, DriverDate, AdapterRAM, PNPDeviceID | ConvertTo-Json"]
            res = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
            
            import json
            if res:
                data = json.loads(res)
                if isinstance(data, dict): data = [data]
                
                for d in data:
                    name = d.get('Name', 'Unknown GPU')
                    drv_ver = d.get('DriverVersion', 'Unknown')
                    
                    # Parse Date: 20240221... -> 21-02-2024
                    raw_date = d.get('DriverDate', '')
                    drv_date = "Unknown"
                    if raw_date and len(raw_date) >= 8:
                        # YYYYMMDD
                        try:
                            dt = datetime.strptime(raw_date[:8], "%Y%m%d")
                            drv_date = dt.strftime("%d-%m-%Y")
                        except: pass
                    
                    # Location (Simplification using PNPDeviceID)
                    pnp = d.get('PNPDeviceID', '')
                    loc = "Internal"
                    if "PCI" in pnp:
                        loc = "PCI Bus (Internal)"
                    
                    # Dedicated Mem
                    ram_bytes = d.get('AdapterRAM', 0)
                    ded_mem = f"{ram_bytes/(1024**3):.1f} GB" if ram_bytes and ram_bytes > 0 else "N/A"
                    
                    gpus.append({
                        "name": name,
                        "driver_ver": drv_ver,
                        "driver_date": drv_date,
                        "location": loc,
                        "dedicated_static": ded_mem
                    })
        except: pass
        
        # Fallback if empty
        if not gpus: gpus.append({"name": "Basic Display Adapter", "driver_ver": "--", "driver_date": "--", "location": "--", "dedicated_static": "--"})
        return gpus

    def get_ram_static_advanced(self):
        d = {"speed": "N/A", "slots": "N/A", "form": "N/A", "hw_res": "N/A"}
        try:
            # Memory Chips
            cmd = ["wmic", "memorychip", "get", "Speed,FormFactor,DeviceLocator,Capacity"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            lines = [l.strip() for l in res.stdout.split('\n') if l.strip()]
            
            if len(lines) > 1:
                chips = lines[1:]
                d["slots_used"] = len(chips)
                
                # Speed (MHz -> MT/s)
                speeds = [c.split()[-1] for c in chips if c.split()]
                if speeds: d["speed"] = f"{speeds[0]} MT/s"
                
                # Form Factor
                forms = {8: "DIMM", 12: "SODIMM"}
                f_val = chips[0].split()[1] # Naive index
                if f_val.isdigit(): d["form"] = forms.get(int(f_val), "Unknown")
            
            # Total Slots
            cmd = ["wmic", "memphysical", "get", "MemoryDevices"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            lines = [l.strip() for l in res.stdout.split('\n') if l.strip()]
            if len(lines) > 1:
                d["slots"] = f"{d.get('slots_used', 0)} of {lines[1]}"

            # Hardware Reserved
            # Total Installed - Available to OS
            cmd = ["powershell", "-Command", "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"]
            res = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
            if res.isdigit():
                total_installed = int(res)
                total_os = psutil.virtual_memory().total
                res_bytes = total_installed - total_os
                if res_bytes > 0:
                    d["hw_res"] = f"{res_bytes // (1024*1024)} MB"
        except: pass
        return d

    def get_cpu_static_advanced(self):
        # Default
        d = {
            "base_speed": "N/A", "sockets": "1", "cores": psutil.cpu_count(logical=False),
            "logical": psutil.cpu_count(logical=True), "virt": "Unknown",
            "l1": "--", "l2": "--", "l3": "--"
        }
        
        try:
            # Base Speed (Max Clock)
            freq = psutil.cpu_freq()
            if freq: d["base_speed"] = f"{freq.max/1000:.2f} GHz"
            
            # WMI for Caches and Virtualization
            # Cache Levels: 3 (L1), 4 (L2), 5 (L3) usually in CacheLevel col, but Size is simpler
            # Win32_CacheMemory: Level, MaxCacheSize
            # Or Win32_Processor: L2CacheSize, L3CacheSize, VirtualizationFirmwareEnabled
            
            cmd = ["wmic", "cpu", "get", "L2CacheSize,L3CacheSize,VirtualizationFirmwareEnabled"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            # Output:
            # L2CacheSize  L3CacheSize  VirtualizationFirmwareEnabled
            # 1280         12288        TRUE
            
            lines = [l.strip() for l in res.stdout.split('\n') if l.strip()]
            if len(lines) > 1:
                vals = lines[1].split() # Naive split might fail if spacing weird, but usually ok
                # Usually 3 values. If Virt is missing on old OS, fewer.
                # Let's parse strictly? Wmic is fixed width usually.
                # Regex or just split might work.
                
                # Let's try to map columns by header? Too complex.
                # Assume order: L2, L3, Virt (Alphabetical is default? No, explicit order)
                # wmic command arg order is respected.
                
                if len(vals) >= 2:
                    if vals[0].isdigit(): d["l2"] = f"{float(vals[0])/1024:.1f} MB"
                    if vals[1].isdigit(): d["l3"] = f"{float(vals[1])/1024:.1f} MB"
                if len(vals) >= 3:
                    d["virt"] = "Enabled" if vals[2] == "TRUE" else "Disabled"
                    
        except: pass
        return d

    def get_static_batt_info(self):
        full, des = "N/A", "N/A"
        
        # Method 1: PowerShell (Fast)
        try:
            cmd = ["powershell", "-Command", "Get-CimInstance -ClassName Win32_Battery | Select-Object -ExpandProperty DesignCapacity"]
            res_des = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
            
            cmd = ["powershell", "-Command", "Get-CimInstance -ClassName Win32_Battery | Select-Object -ExpandProperty FullChargeCapacity"]
            res_full = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
            
            if res_des and res_des.isdigit(): des = f"{res_des} mWh"
            if res_full and res_full.isdigit(): full = f"{res_full} mWh"
        except: pass

        # Method 2: Powercfg Report (Fallback, Slow but Robust)
        if des == "N/A" or full == "N/A":
            try:
                report_file = "battery_report.xml"
                # Generate report
                subprocess.run(['powercfg', '/batteryreport', '/output', report_file, '/xml'], capture_output=True, creationflags=0x08000000) # CREATE_NO_WINDOW
                
                if os.path.exists(report_file):
                    with open(report_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Simple string parsing to avoid XML lib dependency issues if any, though xml.etree is standard
                    # <DesignCapacity>48001</DesignCapacity>
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(content)
                    
                    # Namespace handling is annoying in ET, search by local name or strip NS
                    # The report has xmlns="http://schemas.microsoft.com/battery/2012"
                    ns = {'ns': 'http://schemas.microsoft.com/battery/2012'}
                    
                    batt = root.find('.//ns:Batteries/ns:Battery', ns)
                    if batt is not None:
                        d_cap = batt.find('ns:DesignCapacity', ns).text
                        f_cap = batt.find('ns:FullChargeCapacity', ns).text
                        
                        if d_cap: des = f"{d_cap} mWh"
                        if f_cap: full = f"{f_cap} mWh"
                    
                    try: os.remove(report_file)
                    except: pass
            except Exception as e:
                print(f"Battery Report Error: {e}")

        return full, des

    def get_ram_static_info(self):
        info = "Unknown"
        try:
            res = subprocess.run(['wmic', 'memorychip', 'get', 'Speed,Capacity'], capture_output=True, text=True)
            lines = [l.strip() for l in res.stdout.split('\n') if l.strip()]
            # lines[0] is header: Capacity Speed
            if len(lines) > 1:
                # Naive parse
                speeds = []
                for l in lines[1:]:
                    parts = l.split()
                    if parts: speeds.append(parts[-1]) # Speed is usually last if alphabetical, but let's check header
                # Header check is safer but wmic formatting is tricky. usually Speed is in MHz.
                # Let's just look for numbers > 100 in the line
                detected_speeds = [s for s in speeds if s.isdigit() and int(s) > 100]
                if detected_speeds:
                    info = f"{detected_speeds[0]} MHz ({len(lines)-1} sticks)"
        except: pass
        return info

    def init_csv(self):
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["Timestamp", "RAM%", "CPU%", "Battery%", "DiskSpeed(MB/s)", "NetSpeed(KB/s)", "Opt"])

    def log_csv(self, ram, cpu, batt, disk, net, opt=""):
        try:
            with open(self.csv_file, mode='a', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    ram, cpu, batt, f"{disk:.2f}", f"{net:.2f}", opt
                ])
        except Exception: pass

    def create_widgets(self):
        container = ttk.Frame(self.root, padding=20)
        container.pack(fill=tk.BOTH, expand=True)

        # Header
        header = ttk.Frame(container)
        header.pack(fill=tk.X, pady=(0, 20))
        ttk.Label(header, text="SYSTEM DASHBOARD PRO", style="Header.TLabel").pack(side=tk.LEFT)
        
        header_right = ttk.Frame(header)
        header_right.pack(side=tk.RIGHT)
        self.lbl_clock = ttk.Label(header_right, text="--:--:--", font=("Segoe UI", 18, "bold"), foreground=ModernDarkTheme.ACCENT_COLOR)
        self.lbl_clock.pack(anchor="e")
        ttk.Label(header_right, text=f"Booted: {self.boot_time} | {platform.system()} {platform.release()}", font=("Segoe UI", 9)).pack(anchor="e")
        
        self.update_clock()

        # Dashboard Grid
        grid = ttk.Frame(container)
        grid.pack(fill=tk.BOTH, expand=True)
        for i in range(6): grid.columnconfigure(i, weight=1)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)
        grid.rowconfigure(2, weight=1)

        # --- ROW 0 ---
        # RAM (Col 0-1)
        card_ram = self.create_card(grid, "MEMORY", 0, 0, colspan=2)
        
        # Main usage row
        r1 = ttk.Frame(card_ram, style="Card.TFrame"); r1.pack(fill=tk.X, pady=2)
        ttk.Label(r1, text="Utilization:", style="CardSub.TLabel").pack(side=tk.LEFT)
        self.lbl_ram_usage = ttk.Label(r1, text="--%", style="CardValue.TLabel"); self.lbl_ram_usage.pack(side=tk.RIGHT)

        # In use / Available row
        r2 = ttk.Frame(card_ram, style="Card.TFrame"); r2.pack(fill=tk.X, pady=5)
        r2.columnconfigure(0, weight=1); r2.columnconfigure(1, weight=1)
        
        self.lbl_ram_inuse = ttk.Label(r2, text="-- GB", style="CardValue.TLabel", font=("Segoe UI", 11, "bold"))
        self.lbl_ram_avail = ttk.Label(r2, text="-- GB", style="CardValue.TLabel", font=("Segoe UI", 11, "bold"))
        self.lbl_ram_inuse.grid(row=0, column=0); ttk.Label(r2, text="In use (Compressed)", style="CardSub.TLabel").grid(row=1, column=0)
        self.lbl_ram_avail.grid(row=0, column=1); ttk.Label(r2, text="Available", style="CardSub.TLabel").grid(row=1, column=1)

        # Committed / Cached row
        r3 = ttk.Frame(card_ram, style="Card.TFrame"); r3.pack(fill=tk.X, pady=5)
        r3.columnconfigure(0, weight=1); r3.columnconfigure(1, weight=1)
        
        self.lbl_ram_comm = ttk.Label(r3, text="--/-- GB", style="CardValue.TLabel", font=("Segoe UI", 10))
        self.lbl_ram_cached = ttk.Label(r3, text="-- GB", style="CardValue.TLabel", font=("Segoe UI", 10))
        self.lbl_ram_comm.grid(row=0, column=0); ttk.Label(r3, text="Committed", style="CardSub.TLabel").grid(row=1, column=0)
        self.lbl_ram_cached.grid(row=0, column=1); ttk.Label(r3, text="Cached", style="CardSub.TLabel").grid(row=1, column=1)

        # Paged / Non-paged row
        r4 = ttk.Frame(card_ram, style="Card.TFrame"); r4.pack(fill=tk.X, pady=5)
        r4.columnconfigure(0, weight=1); r4.columnconfigure(1, weight=1)
        
        self.lbl_ram_paged = ttk.Label(r4, text="-- MB", style="CardValue.TLabel", font=("Segoe UI", 10))
        self.lbl_ram_nonpaged = ttk.Label(r4, text="-- MB", style="CardValue.TLabel", font=("Segoe UI", 10))
        self.lbl_ram_paged.grid(row=0, column=0); ttk.Label(r4, text="Paged pool", style="CardSub.TLabel").grid(row=1, column=0)
        self.lbl_ram_nonpaged.grid(row=0, column=1); ttk.Label(r4, text="Non-paged pool", style="CardSub.TLabel").grid(row=1, column=1)

        ttk.Separator(card_ram, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Static Details Grid
        r5 = ttk.Frame(card_ram, style="Card.TFrame"); r5.pack(fill=tk.X)
        r5.columnconfigure(0, weight=1); r5.columnconfigure(1, weight=1)
        
        l = ttk.Frame(r5, style="Card.TFrame"); l.grid(row=0, column=0, sticky="nw")
        ttk.Label(l, text=f"Speed: {self.ram_static['speed']}", style="CardSub.TLabel").pack(anchor="w")
        ttk.Label(l, text=f"Slots used: {self.ram_static['slots']}", style="CardSub.TLabel").pack(anchor="w")
        
        r = ttk.Frame(r5, style="Card.TFrame"); r.grid(row=0, column=1, sticky="ne")
        ttk.Label(r, text=f"Form factor: {self.ram_static['form']}", style="CardSub.TLabel").pack(anchor="e")
        ttk.Label(r, text=f"Hardware reserved: {self.ram_static['hw_res']}", style="CardSub.TLabel").pack(anchor="e")

        # DISPLAY (Col 2-3) - Moved here, separated from CPU
        card_disp = self.create_card(grid, "DISPLAY", 0, 2, colspan=2)
        self.lbl_res = self.add_row(card_disp, "Primary Res:", "Detecting...")
        self.lbl_monitors = self.add_row(card_disp, "Monitors:", "--")
        self.lbl_monitors.config(justify="right")

        # BATTERY (Col 4-5)
        card_batt = self.create_card(grid, "BATTERY", 0, 4, colspan=2)
        self.lbl_batt_stat = self.add_row(card_batt, "Status:", "Detecting...")
        self.lbl_batt_lvl = self.add_row(card_batt, "Level:", "--%")
        self.lbl_batt_cap = self.add_row(card_batt, "Full Cap:", "Detecting...")
        self.lbl_batt_design = self.add_row(card_batt, "Design Cap:", "Detecting...")

        # --- ROW 1 ---
        # CPU (Col 0-2) - Detailed
        card_cpu = self.create_card(grid, "CPU", 1, 0, colspan=3)
        
        # Utilization Row
        r1 = ttk.Frame(card_cpu, style="Card.TFrame"); r1.pack(fill=tk.X, pady=2)
        ttk.Label(r1, text="Utilization:", style="CardSub.TLabel").pack(side=tk.LEFT)
        self.lbl_cpu_load = ttk.Label(r1, text="--%", style="CardValue.TLabel"); self.lbl_cpu_load.pack(side=tk.RIGHT)
        
        # Temp & Fan Row
        r_tf = ttk.Frame(card_cpu, style="Card.TFrame"); r_tf.pack(fill=tk.X, pady=2)
        self.lbl_cpu_temp = ttk.Label(r_tf, text="Temp: --", style="CardValue.TLabel", foreground="#ff5252")
        self.lbl_cpu_temp.pack(side=tk.LEFT)
        self.lbl_fan = ttk.Label(r_tf, text="Fan: --", style="CardSub.TLabel")
        self.lbl_fan.pack(side=tk.RIGHT)
        
        # Speed & Uptime
        r2 = ttk.Frame(card_cpu, style="Card.TFrame"); r2.pack(fill=tk.X, pady=2)
        self.lbl_speed = ttk.Label(r2, text="Speed: -- GHz", style="CardValue.TLabel"); self.lbl_speed.pack(side=tk.LEFT, padx=(0,10))
        self.lbl_uptime = ttk.Label(r2, text="Up: --:--:--", style="CardSub.TLabel"); self.lbl_uptime.pack(side=tk.RIGHT)

        # Processes Grid
        # Proc | Thr | Hnd
        r3 = ttk.Frame(card_cpu, style="Card.TFrame"); r3.pack(fill=tk.X, pady=5)
        for i in range(3): r3.columnconfigure(i, weight=1)
        
        self.lbl_proc = ttk.Label(r3, text="0", style="CardValue.TLabel", font=("Segoe UI", 12, "bold"))
        self.lbl_thr = ttk.Label(r3, text="0", style="CardValue.TLabel", font=("Segoe UI", 12, "bold"))
        self.lbl_hnd = ttk.Label(r3, text="0", style="CardValue.TLabel", font=("Segoe UI", 12, "bold"))
        
        self.lbl_proc.grid(row=0, column=0); ttk.Label(r3, text="Processes", style="CardSub.TLabel").grid(row=1, column=0)
        self.lbl_thr.grid(row=0, column=1); ttk.Label(r3, text="Threads", style="CardSub.TLabel").grid(row=1, column=1)
        self.lbl_hnd.grid(row=0, column=2); ttk.Label(r3, text="Handles", style="CardSub.TLabel").grid(row=1, column=2)

        # Static Details
        ttk.Separator(card_cpu, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # 2-Col Grid for Static
        r4 = ttk.Frame(card_cpu, style="Card.TFrame"); r4.pack(fill=tk.X)
        r4.columnconfigure(0, weight=1); r4.columnconfigure(1, weight=1)
        
        # Left Col
        l = ttk.Frame(r4, style="Card.TFrame"); l.grid(row=0, column=0, sticky="nw")
        ttk.Label(l, text=f"Base Speed: {self.cpu_static['base_speed']}", style="CardSub.TLabel").pack(anchor="w")
        ttk.Label(l, text=f"Sockets: {self.cpu_static['sockets']}", style="CardSub.TLabel").pack(anchor="w")
        ttk.Label(l, text=f"Cores: {self.cpu_static['cores']}", style="CardSub.TLabel").pack(anchor="w")
        ttk.Label(l, text=f"Logical: {self.cpu_static['logical']}", style="CardSub.TLabel").pack(anchor="w")
        
        # Right Col
        r = ttk.Frame(r4, style="Card.TFrame"); r.grid(row=0, column=1, sticky="ne")
        ttk.Label(r, text=f"Virtualization: {self.cpu_static['virt']}", style="CardSub.TLabel").pack(anchor="e")
        ttk.Label(r, text=f"L2 Cache: {self.cpu_static['l2']}", style="CardSub.TLabel").pack(anchor="e")
        ttk.Label(r, text=f"L3 Cache: {self.cpu_static['l3']}", style="CardSub.TLabel").pack(anchor="e")

        # GPU (Col 3-5)
        # We will use a container for dynamic GPU cards
        gpu_root = self.create_card(grid, "GPU", 1, 3, colspan=3)
        self.gpu_container = ttk.Frame(gpu_root, style="Card.TFrame")
        self.gpu_container.pack(fill=tk.BOTH, expand=True)
        self.gpu_widgets = {}
        
        # --- ROW 2 ---
        # STORAGE (Col 0-6)
        card_io = self.create_card(grid, "STORAGE & NETWORK", 2, 0, colspan=6)
        
        # We'll use a dynamic list for Disks. Create a container for them.
        self.disk_container = ttk.Frame(card_io, style="Card.TFrame")
        self.disk_container.pack(fill=tk.BOTH, expand=True)
        
        # We will create disk widgets dynamically in update_ui because the number of drives could change (USB)
        # But for now, we'll store references.
        self.disk_widgets = {}

        # Network section
        net_card = ttk.Frame(card_io, style="Card.TFrame", padding=5)
        net_card.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)
        
        ttk.Label(net_card, text="NETWORK", style="CardHeader.TLabel", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        
        # Throughput
        nt = ttk.Frame(net_card, style="Card.TFrame")
        nt.pack(fill=tk.X, pady=5)
        nt.columnconfigure(0, weight=1); nt.columnconfigure(1, weight=1)
        
        self.lbl_net_send = ttk.Label(nt, text="--", style="CardValue.TLabel", font=("Segoe UI", 11, "bold"))
        self.lbl_net_recv = ttk.Label(nt, text="--", style="CardValue.TLabel", font=("Segoe UI", 11, "bold"))
        self.lbl_net_send.grid(row=0, column=0); ttk.Label(nt, text="Send", style="CardSub.TLabel").grid(row=1, column=0)
        self.lbl_net_recv.grid(row=0, column=1); ttk.Label(nt, text="Receive", style="CardSub.TLabel").grid(row=1, column=1)
        
        ttk.Separator(net_card, orient='horizontal').pack(fill=tk.X, pady=5)
        
        # Adapter Info
        ni = ttk.Frame(net_card, style="Card.TFrame")
        ni.pack(fill=tk.X)
        self.lbl_net_adapter = ttk.Label(ni, text="Adapter: --", style="CardSub.TLabel"); self.lbl_net_adapter.pack(anchor="w")
        self.lbl_net_type = ttk.Label(ni, text="Type: --", style="CardSub.TLabel"); self.lbl_net_type.pack(anchor="w")
        self.lbl_net_ipv4 = ttk.Label(ni, text="IPv4: --", style="CardSub.TLabel"); self.lbl_net_ipv4.pack(anchor="w")
        self.lbl_net_ipv6 = ttk.Label(ni, text="IPv6: --", style="CardSub.TLabel"); self.lbl_net_ipv6.pack(anchor="w")

        # Controls
        controls = ttk.Frame(container)
        controls.pack(fill=tk.X, pady=20)
        ttk.Button(controls, text="⚡ OPTIMIZE RAM", command=lambda: self.start_opt("Manual")).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.btn_net = ttk.Button(controls, text="🌐 START NET LOAD (200KB/s)", command=self.toggle_net_load)
        self.btn_net.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(controls, text="📊 ANALYTICS", command=self.show_analytics).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Log
        log_frame = ttk.Frame(container, style="Card.TFrame", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', height=5, bg="#1e1e1e", fg="#aaa", font=("Consolas", 9), relief="flat")
        self.log_area.pack(fill=tk.BOTH, expand=True)

    def update_clock(self):
        self.lbl_clock.config(text=datetime.now().strftime("%I:%M:%S %p"))
        self.root.after(1000, self.update_clock)

    def create_card(self, parent, title, r, c, colspan=1):
        f = ttk.Frame(parent, style="Card.TFrame", padding=15)
        f.grid(row=r, column=c, padx=10, pady=10, sticky="nsew", columnspan=colspan)
        ttk.Label(f, text=title, style="CardHeader.TLabel").pack(anchor="w", pady=(0, 10))
        return f

    def add_row(self, parent, label, val):
        r = ttk.Frame(parent, style="Card.TFrame")
        r.pack(fill=tk.X, pady=3)
        ttk.Label(r, text=label, style="CardSub.TLabel").pack(side=tk.LEFT)
        v = ttk.Label(r, text=val, style="CardValue.TLabel")
        v.pack(side=tk.RIGHT)
        return v

    def get_display(self):
        displays = []
        try:
            # Enumerate through all display devices
            i = 0
            while True:
                # Get the device name (e.g., \\.\DISPLAY1)
                class DISPLAY_DEVICE(ctypes.Structure):
                    _fields_ = [
                        ('cb', ctypes.c_ulong),
                        ('DeviceName', ctypes.c_char * 32),
                        ('DeviceString', ctypes.c_char * 128),
                        ('StateFlags', ctypes.c_ulong),
                        ('DeviceID', ctypes.c_char * 128),
                        ('DeviceKey', ctypes.c_char * 128)
                    ]
                
                dd = DISPLAY_DEVICE()
                dd.cb = ctypes.sizeof(dd)
                
                if not user32.EnumDisplayDevicesA(None, i, ctypes.byref(dd), 0):
                    break
                
                # Check if it's an active monitor
                # 0x1 is DISPLAY_DEVICE_ATTACHED_TO_DESKTOP
                if dd.StateFlags & 0x1:
                    dm = DEVMODE()
                    dm.dmSize = ctypes.sizeof(DEVMODE)
                    if user32.EnumDisplaySettingsA(dd.DeviceName, -1, ctypes.byref(dm)):
                        res = f"{dm.dmPelsWidth}x{dm.dmPelsHeight}"
                        freq = f"{dm.dmDisplayFrequency} Hz"
                        displays.append(f"M{i}: {res} @ {freq}")
                i += 1
        except: pass
        
        if not displays: return "N/A", ""
        # Return first display's res as main, and the full list as second part
        return displays[0].split(": ")[1].split(" @ ")[0], "\n".join(displays)

    def get_batt(self):
        stat, lvl, rem = "N/A", "--%", "--"
        p = SYSTEM_POWER_STATUS()
        if kernel32.GetSystemPowerStatus(ctypes.byref(p)):
            stat = "Plugged In" if p.ACLineStatus == 1 else "On Battery"
            lvl = f"{p.BatteryLifePercent}%"
            if p.BatteryLifeTime != -1: rem = f"{p.BatteryLifeTime//60}m"
        
        return stat, lvl, self.cached_batt_cap, self.cached_batt_design

    def monitor_thread(self):
        """Background thread to fetch data without freezing UI."""
        while True:
            try:
                # 1. RAM
                mem = psutil.virtual_memory()
                ram_p = mem.percent
                ram_u = round(mem.used/(1024**3), 1)
                ram_f = round(mem.available/(1024**3), 1)
                
                # Detailed RAM
                pi = PERFORMANCE_INFORMATION()
                pi.cb = ctypes.sizeof(pi)
                psapi.GetPerformanceInfo(ctypes.byref(pi), pi.cb)
                
                pg_size = pi.PageSize
                comm_val = f"{round((pi.CommitTotal * pg_size)/(1024**3), 1)}/{round((pi.CommitLimit * pg_size)/(1024**3), 1)} GB"
                cache_val = f"{round((pi.SystemCache * pg_size)/(1024**3), 1)} GB"
                paged_val = f"{round((pi.KernelPaged * pg_size)/(1024**2), 0)} MB"
                nonpaged_val = f"{round((pi.KernelNonPaged * pg_size)/(1024**2), 0)} MB"
                
                # Compressed (Approx via PowerShell - Memory Compression process)
                # This is slow, maybe once every 5 iterations?
                comp_val = "0.0 GB"
                try:
                    cmd = ["powershell", "-Command", "Get-Process -Name 'Memory Compression' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty WorkingSet"]
                    res = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
                    if res and res.isdigit():
                        comp_val = f"{round(int(res)/(1024**3), 1)} GB"
                except: pass

                # 2. CPU & Display
                cpu = psutil.cpu_percent()
                res, monitors_str = self.get_display()
                
                # Advanced CPU (Processes, Threads, Handles, Uptime, Speed)
                pi = PERFORMANCE_INFORMATION()
                pi.cb = ctypes.sizeof(pi)
                psapi.GetPerformanceInfo(ctypes.byref(pi), pi.cb)
                
                uptime_sec = time.time() - psutil.boot_time()
                uptime_str = str(timedelta(seconds=int(uptime_sec)))
                
                freq = psutil.cpu_freq()
                curr_speed = f"{freq.current/1000:.2f} GHz" if freq else "--"
                
                # Sensors (Temp & Fan) via WMI (OHM)
                cpu_temp = "-- °C"
                fan_speed = "-- RPM"
                gpu_temps = {} # Mapping name -> temp
                
                if self.wmi_obj:
                    try:
                        # Re-connect if needed? No, WMI obj persists usually.
                        # Query OpenHardwareMonitor
                        sensors = self.wmi_obj.Sensor()
                        for s in sensors:
                            if s.SensorType == u'Temperature':
                                if 'cpu' in s.Name.lower():
                                    cpu_temp = f"{s.Value:.0f} °C"
                                elif 'gpu' in s.Name.lower():
                                    # Store by part of name or just assign to first found?
                                    # Ideally match Parent hardware.
                                    gpu_temps[s.Parent] = f"{s.Value:.0f} °C"
                            elif s.SensorType == u'Fan':
                                fan_speed = f"{s.Value:.0f} RPM"
                    except:
                        # Fallback for CPU Temp (Linux/some Win)
                        try:
                            t = psutil.sensors_temperatures()
                            if 'coretemp' in t:
                                cpu_temp = f"{t['coretemp'][0].current} °C"
                        except: pass

                # 3. Battery
                st, lv, fl, ds = self.get_batt()
                
                # GPU Monitoring (List)
                curr_gpus = []
                # Shared system memory (approx 50% of total RAM)
                shared_mem_gb = self.total_ram_gb / 2.0
                
                for i, g in enumerate(self.gpu_static_list):
                    # Default values
                    util = "--%"
                    mem_used = "0.0"
                    mem_tot = g['dedicated_static']
                    shared_used = "0.0" # Hard to get per-process without PerfCounters
                    
                    is_nvidia = "nvidia" in g['name'].lower()
                    
                    # Nvidia Realtime
                    if is_nvidia:
                        try:
                            # Index might match, but let's just query all and assume order or use ID?
                            # Using -i 0, -i 1 if we knew index. Assuming list order matches nvidia-smi indices if multiple?
                            # Safer: just query index 0 if one nvidia card.
                            # We'll just run a query for ALL nvidia cards and try to map?
                            # Simplification: Query nvidia-smi for the first NV card found.
                            proc_res = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total', '--format=csv,noheader,nounits'], capture_output=True, text=True)
                            if proc_res.returncode == 0:
                                # Lines for each GPU
                                nv_lines = [l for l in proc_res.stdout.strip().split('\n') if l]
                                # If we have multiple NV cards, we need to track which one in the static list matches.
                                # For this script, assume the first Nvidia card in static list matches first in smi.
                                nv_idx = 0 
                                # This logic is fragile for mixed multi-gpu but fine for most laptops.
                                p = nv_lines[nv_idx].split(', ')
                                util = f"{p[0]}%"
                                mem_used = f"{float(p[1])/1024:.1f}" # MB -> GB
                                mem_tot = f"{float(p[2])/1024:.1f} GB"
                        except: pass
                    else:
                        # Integrated (Intel/AMD)
                        # Utilization is hard. Win10 task manager uses Engine Utilization.
                        # We will leave Util as "--%" to be honest, or "0%" if inactive.
                        # For Memory, they use Shared.
                        mem_tot = "0.1 GB" if g['dedicated_static'] == "N/A" else g['dedicated_static']
                        pass

                    # GPU Temp matching (Heuristic)
                    g_temp = "-- °C"
                    if is_nvidia:
                        # Try nvidia-smi temp
                        try:
                            # We can re-use the smi call from earlier if we optimized, but for now:
                            proc_res = subprocess.run(['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader,nounits'], capture_output=True, text=True)
                            if proc_res.returncode == 0:
                                t_lines = [l for l in proc_res.stdout.strip().split('\n') if l]
                                if t_lines: g_temp = f"{t_lines[0]} °C"
                        except: pass
                    
                    curr_gpus.append({
                        "name": g['name'],
                        "util": util,
                        "mem_usage": f"{mem_used}/{mem_tot}", 
                        "shared_usage": f"{shared_used}/{shared_mem_gb:.1f} GB",
                        "driver": g['driver_ver'],
                        "date": g['driver_date'],
                        "loc": g['location'],
                        "temp": g_temp
                    })

                # 5. Disk/Net Calc
                now = time.time()
                dt = now - self.last_check_time
                if dt <= 0: dt = 0.5 # fallback
                
                dio = psutil.disk_io_counters(perdisk=True)
                nio = psutil.net_io_counters()
                
                # Total Speed & Per Disk String
                drive_lines = []
                total_r_mb = 0.0
                total_w_mb = 0.0
                
                for dname, cnt in dio.items():
                    if dname in self.last_disk_io:
                        prev = self.last_disk_io[dname]
                        r = (cnt.read_bytes - prev.read_bytes)/1024/1024/dt
                        w = (cnt.write_bytes - prev.write_bytes)/1024/1024/dt
                        total_r_mb += r
                        total_w_mb += w
                        
                        # Show all drives, even if idle
                        short = dname.replace("PhysicalDrive", "Drive ")
                        drive_lines.append(f"{short}: R:{r:.1f} W:{w:.1f} MB/s")
                
                disk_io_str = "\n".join(drive_lines) if drive_lines else "No Drives Found"
                
                # Disk Monitoring (Advanced)
                drive_details = []
                total_r_mb_sum = 0.0
                total_w_mb_sum = 0.0
                
                for dname, cnt in dio.items():
                    if dname in self.last_disk_io:
                        prev = self.last_disk_io[dname]
                        
                        # Throughput
                        r_mb = (cnt.read_bytes - prev.read_bytes)/1024/1024/dt
                        w_mb = (cnt.write_bytes - prev.write_bytes)/1024/1024/dt
                        total_r_mb_sum += r_mb
                        total_w_mb_sum += w_mb
                        
                        # Active Time % (busy_time is in ms)
                        if hasattr(cnt, 'busy_time'):
                            busy_ms = cnt.busy_time - prev.busy_time
                        else:
                            # Fallback for Windows: Sum of read/write times
                            # Note: This can exceed 100% if concurrent requests, so we cap it later
                            busy_ms = (cnt.read_time - prev.read_time) + (cnt.write_time - prev.write_time)
                            
                        active_p = (busy_ms / (dt * 1000)) * 100
                        active_p = min(100, max(0, active_p))
                        
                        # Avg Response Time (ms)
                        # (delta_time_ms) / (delta_count)
                        r_time = cnt.read_time - prev.read_time
                        w_time = cnt.write_time - prev.write_time
                        r_count = cnt.read_count - prev.read_count
                        w_count = cnt.write_count - prev.write_count
                        
                        total_ops = r_count + w_count
                        avg_resp = (r_time + w_time) / total_ops if total_ops > 0 else 0
                        
                        # Static info merge
                        static = self.disk_static.get(dname, {"model": "Unknown", "type": "Fixed", "size": "--", "system": "No", "pagefile": "No"})
                        
                        drive_details.append({
                            "name": dname.replace("PhysicalDrive", "Disk "),
                            "active": f"{active_p:.0f}%",
                            "read": f"{r_mb:.1f} MB/s" if r_mb > 0.1 else f"{r_mb*1024:.0f} KB/s",
                            "write": f"{w_mb:.1f} MB/s" if w_mb > 0.1 else f"{w_mb*1024:.0f} KB/s",
                            "latency": f"{avg_resp:.1f} ms",
                            **static
                        })

                # Network Monitoring (Advanced)
                nio_dict = psutil.net_io_counters(pernic=True)
                ifaces = psutil.net_if_addrs()
                istats = psutil.net_if_stats()
                
                # Find active adapter (one with non-zero traffic and an IP)
                active_iface = "--"
                net_send_str = "0 Kbps"
                net_recv_str = "0 Kbps"
                ipv4 = "--"
                ipv6 = "--"
                conn_type = "Unknown"
                
                # We'll look for the interface with the highest combined throughput
                max_traffic = -1
                best_iface = None
                
                for iface, nio in nio_dict.items():
                    if iface in self.last_net_io_dict:
                        prev = self.last_net_io_dict[iface]
                        traffic = (nio.bytes_sent - prev.bytes_sent) + (nio.bytes_recv - prev.bytes_recv)
                        # Check if it has an IPv4
                        has_ip = any(addr.family == 2 for addr in ifaces.get(iface, []))
                        if has_ip and traffic > max_traffic:
                            max_traffic = traffic
                            best_iface = iface
                
                if best_iface:
                    active_iface = best_iface
                    prev = self.last_net_io_dict[best_iface]
                    nio = nio_dict[best_iface]
                    
                    # Throughput Calc
                    s_bps = ((nio.bytes_sent - prev.bytes_sent) * 8) / dt
                    r_bps = ((nio.bytes_recv - prev.bytes_recv) * 8) / dt
                    
                    def fmt_bits(bits):
                        if bits > 1000000: return f"{bits/1000000:.1f} Mbps"
                        return f"{bits/1000:.1f} Kbps"
                    
                    net_send_str = fmt_bits(s_bps)
                    net_recv_str = fmt_bits(r_bps)
                    
                    # IPs
                    for addr in ifaces.get(best_iface, []):
                        if addr.family == 2: ipv4 = addr.address
                        elif addr.family == 23: ipv6 = addr.address.split('%')[0] # Remove scope id
                    
                    # Type
                    if "wi-fi" in best_iface.lower() or "wireless" in best_iface.lower(): conn_type = "Wi-Fi"
                    elif "ethernet" in best_iface.lower(): conn_type = "Ethernet"
                
                # Total Network Speed (KB/s) for Logs/UI
                # We need to calculate this from total counters to match previous logic
                # nio_total is not available as a variable, so fetch it or sum it?
                # Actually, self.last_net_io stores the *previous* total.
                # Let's fetch current total again or sum the dict. Fetching is safer.
                nio_total_curr = psutil.net_io_counters()
                nsp_dn = (nio_total_curr.bytes_recv - self.last_net_io.bytes_recv) / 1024 / dt
                nsp_up = (nio_total_curr.bytes_sent - self.last_net_io.bytes_sent) / 1024 / dt
                
                # Update total net io state
                self.last_net_io = nio_total_curr

                # Storage (All Drives) - RESTORED
                d_str = ""
                try: 
                    for part in psutil.disk_partitions(all=False):
                        if 'cdrom' in part.opts or part.fstype == '': continue
                        try:
                            u = psutil.disk_usage(part.mountpoint)
                            f_gb = int(u.free / (1024**3))
                            t_gb = int(u.total / (1024**3))
                            d_str += f"{part.device[:2]} {f_gb}/{t_gb} GB\n"
                        except: pass
                except: pass
                if not d_str: d_str = "No Drives Found"

                # Update State
                self.last_disk_io = dio
                self.last_net_io_dict = nio_dict
                self.last_check_time = now

                # Auto Optimize Trigger
                if (ram_p >= self.threshold_ram or cpu >= self.threshold_cpu) and (time.time() - self.last_opt_time > 60):
                     self.last_opt_time = time.time()
                     self.start_opt(f"Auto >{self.threshold_ram}%RAM or >{self.threshold_cpu}%CPU")

                # Push to Shared Dict
                self.ui_data = {
                    "ram_p": ram_p, "ram_u": ram_u, "ram_f": ram_f,
                    "ram_comp": comp_val, "ram_avail": f"{ram_f} GB", 
                    "ram_comm": comm_val, "ram_cached": cache_val,
                    "ram_paged": paged_val, "ram_nonpaged": nonpaged_val,
                    "cpu": cpu, "res": res, "monitors": monitors_str,
                    "proc": pi.ProcessCount, "thr": pi.ThreadCount, "hnd": pi.HandleCount,
                    "uptime": uptime_str, "speed": curr_speed,
                    "cpu_temp": cpu_temp, "fan_speed": fan_speed,
                    "bat_st": st, "bat_lv": lv, "bat_fl": fl, "bat_ds": ds,
                    "gpu_list": curr_gpus,
                    "disk_sp": "0.0", 
                    "net_send": net_send_str, "net_recv": net_recv_str,
                    "net_adapter": active_iface, "net_type": conn_type,
                    "net_ipv4": ipv4, "net_ipv6": ipv6,
                    "drives_storage": d_str.strip(),
                    "drive_details": drive_details,
                    "disk_io_str": disk_io_str
                }
                
                # Append to history for realtime graphs
                self.history.append({
                    "time": datetime.now(),
                    "ram": ram_p,
                    "cpu": cpu,
                    "disk": total_r_mb_sum + total_w_mb_sum,
                    "net": nsp_dn + nsp_up
                })
                
                # Log to CSV (Background)
                self.log_csv(ram_p, cpu, lv, total_r_mb_sum + total_w_mb_sum, nsp_dn + nsp_up)

            except Exception as e:
                print(f"Monitor Error: {e}")
            
            time.sleep(0.5) # 500ms polling

    def update_ui(self):
        """Main thread loop to update labels from shared data."""
        d = self.ui_data
        
        # RAM
        self.lbl_ram_usage.config(text=f"{d['ram_p']}%")
        self.lbl_ram_inuse.config(text=f"{d['ram_u']} GB ({d['ram_comp']})")
        self.lbl_ram_avail.config(text=d['ram_avail'])
        self.lbl_ram_comm.config(text=d['ram_comm'])
        self.lbl_ram_cached.config(text=d['ram_cached'])
        self.lbl_ram_paged.config(text=d['ram_paged'])
        self.lbl_ram_nonpaged.config(text=d['ram_nonpaged'])
        
        # Display
        self.lbl_res.config(text=d['res'])
        self.lbl_monitors.config(text=d['monitors'])
        
        # Battery
        self.lbl_batt_stat.config(text=d['bat_st'], foreground="#4caf50" if "Plugged" in d['bat_st'] else "#e0e0e0")
        self.lbl_batt_lvl.config(text=d['bat_lv'])
        self.lbl_batt_cap.config(text=d['bat_fl'])
        self.lbl_batt_design.config(text=d['bat_ds'])
        
        # CPU
        self.lbl_cpu_load.config(text=f"{d['cpu']}%")
        self.lbl_speed.config(text=f"Speed: {d['speed']}")
        self.lbl_uptime.config(text=f"Up: {d['uptime']}")
        self.lbl_proc.config(text=str(d['proc']))
        self.lbl_thr.config(text=str(d['thr']))
        self.lbl_hnd.config(text=str(d['hnd']))
        self.lbl_cpu_temp.config(text=d['cpu_temp'])
        self.lbl_fan.config(text=d['fan_speed'])
        
        # GPU (Dynamic)
        gpus = d.get('gpu_list', [])
        for i, g in enumerate(gpus):
            key = f"gpu_{i}"
            if key not in self.gpu_widgets:
                # Create Widget
                f = ttk.Frame(self.gpu_container, style="Card.TFrame", padding=5)
                f.pack(fill=tk.X, pady=5)
                
                # Header: Name + Util
                h = ttk.Frame(f, style="Card.TFrame"); h.pack(fill=tk.X)
                ttk.Label(h, text=g['name'], style="CardHeader.TLabel", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
                lbl_util = ttk.Label(h, text="--%", style="CardValue.TLabel", font=("Segoe UI", 11, "bold"))
                lbl_util.pack(side=tk.RIGHT)
                
                # Grid for details
                dg = ttk.Frame(f, style="Card.TFrame"); dg.pack(fill=tk.X, pady=2)
                dg.columnconfigure(0, weight=1); dg.columnconfigure(1, weight=1)
                
                def add_g_row(p, r, t, val_key=None):
                    ttk.Label(p, text=t, style="CardSub.TLabel").grid(row=r, column=0, sticky="w")
                    l = ttk.Label(p, text="--", style="CardValue.TLabel", font=("Segoe UI", 9))
                    l.grid(row=r, column=1, sticky="e")
                    return l

                l_mem = add_g_row(dg, 0, "GPU Memory")
                l_shar = add_g_row(dg, 1, "Shared Memory")
                l_temp = add_g_row(dg, 2, "Temperature")
                
                # Static grid
                ttk.Separator(f, orient='horizontal').pack(fill=tk.X, pady=5)
                sg = ttk.Frame(f, style="Card.TFrame"); sg.pack(fill=tk.X)
                sg.columnconfigure(0, weight=1); sg.columnconfigure(1, weight=1)
                
                ttk.Label(sg, text=f"Driver: {g['driver']}", style="CardSub.TLabel").grid(row=0, column=0, sticky="w")
                ttk.Label(sg, text=f"Date: {g['date']}", style="CardSub.TLabel").grid(row=0, column=1, sticky="e")
                ttk.Label(sg, text=f"Loc: {g['loc']}", style="CardSub.TLabel").grid(row=1, column=0, sticky="w")
                
                self.gpu_widgets[key] = {'util': lbl_util, 'mem': l_mem, 'shar': l_shar, 'temp': l_temp}
            
            # Update
            w = self.gpu_widgets[key]
            w['util'].config(text=g['util'])
            w['mem'].config(text=g['mem_usage'])
            w['shar'].config(text=g['shared_usage'])
            w['temp'].config(text=g['temp'])

        # I/O & Disks
        self.lbl_net_send.config(text=d['net_send'])
        self.lbl_net_recv.config(text=d['net_recv'])
        self.lbl_net_adapter.config(text=f"Adapter: {d['net_adapter']}")
        self.lbl_net_type.config(text=f"Type: {d['net_type']}")
        self.lbl_net_ipv4.config(text=f"IPv4: {d['net_ipv4']}")
        self.lbl_net_ipv6.config(text=f"IPv6: {d['net_ipv6']}")
        
        # Sync Disk Widgets
        curr_disks = d.get('drive_details', [])
        # Simple rebuild if mismatch, or just update labels if count same
        # To keep it simple and responsive, we'll update text if it exists, otherwise create
        for drive in curr_disks:
            name = drive['name']
            if name not in self.disk_widgets:
                # Create Card for Disk
                f = ttk.Frame(self.disk_container, style="Card.TFrame", padding=5)
                f.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
                
                ttk.Label(f, text=name, style="CardHeader.TLabel", font=("Segoe UI", 10, "bold")).pack(anchor="w")
                
                # Dynamic Grid
                dg = ttk.Frame(f, style="Card.TFrame")
                dg.pack(fill=tk.X, pady=5)
                dg.columnconfigure(0, weight=1); dg.columnconfigure(1, weight=1)
                
                # Rows
                lbls = {}
                def add_disk_row(parent, row, text):
                    ttk.Label(parent, text=text, style="CardSub.TLabel").grid(row=row, column=0, sticky="w")
                    v = ttk.Label(parent, text="--", style="CardValue.TLabel", font=("Segoe UI", 9, "bold"))
                    v.grid(row=row, column=1, sticky="e")
                    return v
                
                lbls['active'] = add_disk_row(dg, 0, "Active time")
                lbls['latency'] = add_disk_row(dg, 1, "Avg response")
                lbls['read'] = add_disk_row(dg, 2, "Read speed")
                lbls['write'] = add_disk_row(dg, 3, "Write speed")
                
                ttk.Separator(f, orient='horizontal').pack(fill=tk.X, pady=5)
                
                # Static info
                st = ttk.Frame(f, style="Card.TFrame")
                st.pack(fill=tk.X)
                ttk.Label(st, text=f"Capacity: {drive['size']}", style="CardSub.TLabel").pack(anchor="w")
                ttk.Label(st, text=f"Type: {drive['type']}", style="CardSub.TLabel").pack(anchor="w")
                ttk.Label(st, text=f"System disk: {drive['system']}", style="CardSub.TLabel").pack(anchor="w")
                ttk.Label(st, text=f"Page file: {drive['pagefile']}", style="CardSub.TLabel").pack(anchor="w")
                
                self.disk_widgets[name] = lbls
            
            # Update values
            w = self.disk_widgets[name]
            w['active'].config(text=drive['active'])
            w['latency'].config(text=drive['latency'])
            w['read'].config(text=drive['read'])
            w['write'].config(text=drive['write'])
        
        self.root.after(self.monitor_interval, self.update_ui)

    def log_msg(self, m):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {m}\n")
        self.log_area.see(tk.END); self.log_area.config(state='disabled')

    def start_opt(self, r):
        threading.Thread(target=self.opt, args=(r,), daemon=True).start()

    def toggle_net_load(self):
        if self.net_load_active:
            self.net_load_active = False
            self.btn_net.config(text="🌐 START NET LOAD (200KB/s)")
            self.log_msg("Network Load Stopped.")
        else:
            self.net_load_active = True
            self.btn_net.config(text="🛑 STOP NET LOAD")
            threading.Thread(target=self.net_load_loop, daemon=True).start()
            self.log_msg("Network Load Started (~200KB/s).")

    def net_load_loop(self):
        url = "http://speedtest.tele2.net/1MB.zip" # Public reliable test file
        while self.net_load_active:
            try:
                start_t = time.time()
                # Read 200KB chunk
                with urllib.request.urlopen(url) as response:
                    response.read(204800) # 200 KB
                
                # Ensure it takes exactly 1 second for the 200KB (200KB/s)
                elapsed = time.time() - start_t
                if elapsed < 1.0:
                    time.sleep(1.0 - elapsed)
            except Exception as e:
                # If error, wait a bit and retry
                time.sleep(1)

    def opt(self, r):
        self.root.after(0, lambda: self.log_msg(f"Optimizing ({r})..."))
        gc.collect()
        c = 0
        for p in psutil.process_iter(['pid']):
            if empty_working_set(p.info['pid']): c += 1
        self.root.after(0, lambda: self.log_msg(f"Done. Trimming {c} processes."))

    def show_analytics(self):
        """Opens a window to view Real-time Analytics with updating graphs."""
        win = tk.Toplevel(self.root)
        win.title("Real-Time System Analytics")
        win.geometry("1100x750")
        win.configure(bg=ModernDarkTheme.BG_COLOR)

        # Tabs
        tab_control = ttk.Notebook(win)
        tab_graph = ttk.Frame(tab_control)
        tab_table = ttk.Frame(tab_control)
        
        tab_control.add(tab_graph, text=' 📈 Live Graphs ')
        tab_control.add(tab_table, text=' 📋 Historical Log (CSV) ')
        tab_control.pack(expand=1, fill="both", padx=10, pady=10)

        # --- Tab 2: Logs Table (Static Load from CSV) ---
        cols = ("Time", "RAM%", "CPU%", "Batt%", "Disk(MB/s)", "Net(KB/s)", "Opt")
        tree = ttk.Treeview(tab_table, columns=cols, show="headings", height=20)
        
        sb = ttk.Scrollbar(tab_table, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True)

        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=100)

        if os.path.exists(self.csv_file):
            try:
                with open(self.csv_file, mode='r') as file:
                    reader = csv.reader(file)
                    next(reader) # header
                    data = list(reader)
                    for row in reversed(data[-100:]):
                        while len(row) < len(cols): row.append("")
                        tree.insert("", tk.END, values=row[:len(cols)])
            except Exception: pass

        # --- Tab 1: Live Graphs ---
        if not HAS_MATPLOTLIB:
            ttk.Label(tab_graph, text="Matplotlib not installed.", font=("Segoe UI", 14)).pack(expand=True)
            return

        import matplotlib.pyplot as plt
        plt.style.use('dark_background')
        
        fig = Figure(figsize=(10, 8), dpi=100, facecolor=ModernDarkTheme.BG_COLOR)
        ax1 = fig.add_subplot(111)
        
        canvas = FigureCanvasTkAgg(fig, master=tab_graph)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Add Toolbar for Zoom/Pan
        toolbar_frame = ttk.Frame(tab_graph)
        toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
        toolbar.update()

        def update_graphs():
            if not win.winfo_exists(): return
            
            # Fetch latest history
            data_points = list(self.history)
            if not data_points: 
                win.after(1000, update_graphs)
                return

            times = [d['time'] for d in data_points]
            ram_v = [d['ram'] for d in data_points]
            cpu_v = [d['cpu'] for d in data_points]

            # Clear Ax1
            ax1.clear()
            ax1.set_facecolor(ModernDarkTheme.CARD_BG)
            ax1.plot(times, ram_v, color="#00bcd4", label="RAM %", lw=1.5)
            ax1.fill_between(times, ram_v, color="#00bcd4", alpha=0.1)
            ax1.plot(times, cpu_v, color="#ff4081", label="CPU %", lw=1.5)
            ax1.set_title("Live System Load (Last 60s)", color="white")
            ax1.legend(loc='upper left', facecolor=ModernDarkTheme.CARD_BG, edgecolor='#444', labelcolor='white')
            ax1.grid(color='#333', linestyle='--')
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

            fig.tight_layout()
            canvas.draw()
            
            # Schedule next update
            win.after(1000, update_graphs)

        # Start loop
        update_graphs()

if __name__ == "__main__":
    root = tk.Tk()
    RamCleanerGUI(root)
    root.mainloop()
