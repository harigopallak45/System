import ctypes
import gc
import psutil
import time
from datetime import datetime

# --- Windows API setup for RAM cleaning ---
psapi = ctypes.WinDLL('psapi.dll')
kernel32 = ctypes.WinDLL('kernel32.dll')

def empty_working_set(pid):
    """Trim memory usage of a process without closing it."""
    hProcess = kernel32.OpenProcess(0x001F0FFF, False, pid)
    if hProcess:
        psapi.EmptyWorkingSet(hProcess)
        kernel32.CloseHandle(hProcess)

def optimize_ram():
    """Run garbage collection and trim all processes."""
    gc.collect()
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            empty_working_set(proc.info['pid'])
        except Exception:
            pass
    print("✅ RAM optimized")

def optimize_cpu():
    """Lower priority of high-CPU processes (instead of killing)."""
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            if proc.info['cpu_percent'] > 20:  # processes using >20% CPU
                p = psutil.Process(proc.info['pid'])
                p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)  # lower priority
                print(f"🔧 Lowered priority: {proc.info['name']} (PID {proc.info['pid']})")
        except Exception:
            pass

def monitor_system(threshold=85, interval=10, time_interval=300):
    """
    Monitor CPU and RAM every 'interval' seconds.
    Optimize if usage ≥ threshold.
    Show system time every 'time_interval' seconds (default 5 minutes).
    """
    last_time_display = time.time()
    
    while True:
        # RAM usage
        mem = psutil.virtual_memory()
        ram_usage = mem.percent
        print(f"\n📊 RAM usage: {ram_usage:.1f}%")

        # CPU usage
        cpu_usage = psutil.cpu_percent(interval=1)
        print(f"⚙️ CPU usage: {cpu_usage:.1f}%")

        # Optimize if threshold exceeded
        if ram_usage >= threshold:
            print("⚠️ High RAM detected! Cleaning RAM...")
            optimize_ram()
        if cpu_usage >= threshold:
            print("⚠️ High CPU detected! Adjusting priorities...")
            optimize_cpu()

        # Show current time every 5 minutes
        if time.time() - last_time_display >= time_interval:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"🕒 Current Time: {current_time}")
            last_time_display = time.time()

        time.sleep(interval)

if __name__ == "__main__":
    monitor_system(threshold=85, interval=10, time_interval=300)
