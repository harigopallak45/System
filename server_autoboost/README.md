# ⚡ AutoBoost for Linux Servers

A lightweight, zero-dependency background daemon and management suite for Linux, adapted from the Windows `AutoBoost.cs` architecture.

### 🌐 Configured & Running On:
1. **EC2 Instance**: `ubuntu@client.truewilly.com` (Ubuntu 24.04, 4GB RAM, 3GB Swap)
2. **VPS Instance**: `root@185.27.135.36` (Ubuntu 24.04 LTS, 2GB RAM, Virtuozzo Container)

---

## 🚀 Key Features

1. **Lightweight Monitoring**: Consumes `< 2.5 MB RAM` and `0.0% CPU` in the background, checking metrics every 5 seconds.
2. **Smart RAM Pressure Relief (Default >= 85%)**:
   - Flushes filesystem buffers (`sync`).
   - Safely releases unused page cache, directory entries, and inode tables (`/proc/sys/vm/drop_caches`).
   - Defragments physical memory pages (`/proc/sys/vm/compact_memory`).
   - Cleans the local DNS resolver cache (`resolvectl flush-caches`).
   - Vacuums oversized systemd journal logs if they exceed threshold.
3. **Background CPU Hog Tamer (Default >= 90%)**:
   - Detects runaway background processes consuming abnormal CPU.
   - Demotes rogue processes with `renice +10` and `ionice -c 3` (idle I/O), preventing the server and SSH from locking up.
   - **Protected Processes**: `mariadbd`, `nginx`, `sshd`, `dockerd`, `containerd`, `n8n`, `node`, `python`, `pm2`, and core system units are strictly protected and never throttled.
4. **Thrashing Prevention**: 30-second cooldown window between boosts.
5. **Full CLI & Interactive Dashboard**: Run `autoboost` anytime on the server or use the Windows `.bat` launcher.

---

## 🛠️ CLI Commands (On Server)

```bash
# Open interactive menu dashboard
autoboost

# View live CPU, RAM, and Swap gauges + service status
autoboost status

# Manually trigger an instant boost
autoboost boost

# View recent boost history and freed memory logs
autoboost logs
autoboost logs -f       # Live follow/tail logs

# Manage the background systemd service
autoboost start
autoboost stop
autoboost restart
autoboost enable        # Enable auto-start on server boot
autoboost disable
```

---

## ⚙️ Configuration (`/etc/autoboost/autoboost.conf`)

You can edit thresholds and protected applications:
```ini
[autoboost]
ram_threshold_percent = 85
cpu_threshold_percent = 90
check_interval_seconds = 5
cooldown_seconds = 30

drop_caches = true
compact_memory = true
flush_dns = true
vacuum_journal = true
max_journal_size = 100M
renice_cpu_hogs = true
cpu_hog_threshold = 30.0

protected_processes = systemd,kthreadd,sshd,mariadbd,mysqld,nginx,httpd,dockerd,containerd,docker-proxy,amazon-ssm-agent,systemd-journald,systemd-resolved,systemd-udevd,dbus-broker,n8n,node,python,python3,pm2,autoboost
```

---

## 💻 Local Windows Control (From this PC)

In `d:\Project\Personal Tools & Labs (hari)\Desktop & System\System\server_autoboost\`:
- **`manage_remote.bat`**: Double-click to immediately SSH into the server and launch the interactive AutoBoost manager.
- **`deploy_to_ec2.bat`**: Re-syncs and re-deploys any configuration changes to the server automatically.
