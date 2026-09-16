using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;

namespace SystemAutoBooster
{
    static class Program
    {
        // --- Win32 Native APIs ---
        [DllImport("psapi.dll")]
        static extern int EmptyWorkingSet(IntPtr hProcess);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        static extern bool GlobalMemoryStatusEx(ref MEMORYSTATUSEX lpBuffer);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool GetSystemTimes(out long lpIdleTime, out long lpKernelTime, out long lpUserTime);

        [DllImport("user32.dll")]
        static extern IntPtr GetForegroundWindow();

        [DllImport("user32.dll")]
        static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

        [DllImport("dnsapi.dll", EntryPoint = "DnsFlushResolverCache")]
        static extern int DnsFlushResolverCache();

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
        struct MEMORYSTATUSEX
        {
            public uint dwLength;
            public uint dwMemoryLoad;
            public ulong ullTotalPhys;
            public ulong ullAvailPhys;
            public ulong ullTotalPageFile;
            public ulong ullAvailPageFile;
            public ulong ullTotalVirtual;
            public ulong ullAvailVirtual;
            public ulong ullAvailExtendedVirtual;
        }

        // --- Exact Thresholds Configured ---
        const int RAM_THRESHOLD_PERCENT = 85;   // Auto-boost trigger at 85% RAM
        const int CPU_THRESHOLD_PERCENT = 90;   // Auto-boost trigger at 90% CPU
        const int MONITOR_INTERVAL_MS = 5000;   // Monitor every 5 seconds
        const int COOLDOWN_SECONDS = 30;        // 30s cooldown between consecutive boosts to prevent thrashing

        static readonly string[] ProtectedProcesses = new string[]
        {
            "system", "idle", "dwm", "csrss", "smss", "winlogon", 
            "services", "lsass", "taskmgr", "explorer", "audiodg"
        };

        // CPU Tracking state
        static long _prevIdleTime = 0;
        static long _prevKernelTime = 0;
        static long _prevUserTime = 0;

        [STAThread]
        static void Main()
        {
            // Ensure only 1 instance runs silently in the background
            bool createdNew;
            using (Mutex mutex = new Mutex(true, "Global\\WindowsAutoBoostService_Silent", out createdNew))
            {
                if (!createdNew)
                {
                    return; // Another instance is already running
                }

                // Initialize baseline CPU timing
                GetSystemTimes(out _prevIdleTime, out _prevKernelTime, out _prevUserTime);
                DateTime lastBoostTime = DateTime.MinValue;

                while (true)
                {
                    try
                    {
                        Thread.Sleep(MONITOR_INTERVAL_MS);

                        uint ramUsage = GetRamUsagePercent();
                        double cpuUsage = GetCpuUsagePercent();

                        bool ramTriggered = (ramUsage >= RAM_THRESHOLD_PERCENT);
                        bool cpuTriggered = (cpuUsage >= CPU_THRESHOLD_PERCENT);

                        // If either RAM >= 85% or CPU >= 90% is reached
                        if (ramTriggered || cpuTriggered)
                        {
                            if ((DateTime.Now - lastBoostTime).TotalSeconds >= COOLDOWN_SECONDS)
                            {
                                if (ramTriggered)
                                {
                                    TrimMemoryWorkingSets();
                                    FlushDns();
                                }

                                if (cpuTriggered)
                                {
                                    TameBackgroundCpuHogs();
                                }

                                lastBoostTime = DateTime.Now;
                            }
                        }
                    }
                    catch
                    {
                        // Silent fail-safe: never crash or show popups
                    }
                }
            }
        }

        static uint GetRamUsagePercent()
        {
            MEMORYSTATUSEX memStatus = new MEMORYSTATUSEX();
            memStatus.dwLength = (uint)Marshal.SizeOf(typeof(MEMORYSTATUSEX));
            if (GlobalMemoryStatusEx(ref memStatus))
            {
                return memStatus.dwMemoryLoad;
            }
            return 0;
        }

        static double GetCpuUsagePercent()
        {
            long idleTime, kernelTime, userTime;
            if (!GetSystemTimes(out idleTime, out kernelTime, out userTime))
                return 0;

            long deltaIdle = idleTime - _prevIdleTime;
            long deltaKernel = kernelTime - _prevKernelTime;
            long deltaUser = userTime - _prevUserTime;

            _prevIdleTime = idleTime;
            _prevKernelTime = kernelTime;
            _prevUserTime = userTime;

            long totalSystemTime = deltaKernel + deltaUser;
            if (totalSystemTime <= 0)
                return 0;

            double cpuPercent = (1.0 - ((double)deltaIdle / (double)totalSystemTime)) * 100.0;
            if (cpuPercent < 0) cpuPercent = 0;
            if (cpuPercent > 100) cpuPercent = 100;

            return cpuPercent;
        }

        static uint GetForegroundProcessId()
        {
            IntPtr hwnd = GetForegroundWindow();
            if (hwnd != IntPtr.Zero)
            {
                uint pid;
                GetWindowThreadProcessId(hwnd, out pid);
                return pid;
            }
            return 0;
        }

        static bool IsProtected(string procName)
        {
            string lower = procName.ToLowerInvariant();
            for (int i = 0; i < ProtectedProcesses.Length; i++)
            {
                if (lower == ProtectedProcesses[i])
                    return true;
            }
            return false;
        }

        static void TrimMemoryWorkingSets()
        {
            int currentPid = Process.GetCurrentProcess().Id;
            Process[] processes = Process.GetProcesses();

            for (int i = 0; i < processes.Length; i++)
            {
                Process proc = processes[i];
                try
                {
                    if (proc.Id == 0 || proc.Id == 4 || proc.Id == currentPid)
                        continue;

                    // Release unused working set pages back to Windows memory manager
                    EmptyWorkingSet(proc.Handle);
                }
                catch
                {
                    // Ignore inaccessible processes
                }
                finally
                {
                    try { proc.Dispose(); } catch { }
                }
            }

            // Flush own process memory
            GC.Collect();
            GC.WaitForPendingFinalizers();
        }

        static void TameBackgroundCpuHogs()
        {
            uint fgPid = GetForegroundProcessId();
            int currentPid = Process.GetCurrentProcess().Id;

            Process[] processes = Process.GetProcesses();
            for (int i = 0; i < processes.Length; i++)
            {
                Process proc = processes[i];
                try
                {
                    // Do NOT throttle the current process or the foreground window (active game / active app)
                    if (proc.Id == 0 || proc.Id == 4 || proc.Id == currentPid || proc.Id == fgPid)
                        continue;

                    if (IsProtected(proc.ProcessName))
                        continue;

                    // Lower priority of background processes so foreground active app never stutters
                    if (proc.PriorityClass == ProcessPriorityClass.Normal ||
                        proc.PriorityClass == ProcessPriorityClass.AboveNormal)
                    {
                        proc.PriorityClass = ProcessPriorityClass.BelowNormal;
                    }
                }
                catch
                {
                    // Ignore processes where priority cannot be modified
                }
                finally
                {
                    try { proc.Dispose(); } catch { }
                }
            }
        }

        static void FlushDns()
        {
            try
            {
                DnsFlushResolverCache();
            }
            catch { }
        }
    }
}
