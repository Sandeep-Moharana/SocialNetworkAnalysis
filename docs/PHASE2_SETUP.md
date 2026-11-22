# Phase 2 Setup: friends' PCs as Spark workers + HDFS DataNodes

Your laptop is the **master**. Each friend's PC adds **computing** (Spark worker) and
**storage** (HDFS DataNode, every block kept on 2 PCs). The analytics code does not change.

```
  YOUR LAPTOP (master)                FRIEND A's PC          FRIEND B's PC
  ┌─────────────────────────────┐     ┌────────────────┐     ┌────────────────┐
  │ spark-master   namenode     │◄───►│ worker-alice   │◄───►│ worker-bob     │
  │ spark-client   datanode     │     │ datanode-alice │     │ datanode-bob   │
  │ spark-worker-1  registry    │     └────────────────┘     └────────────────┘
  └─────────────────────────────┘           all on the same hotspot / Wi-Fi
```

**Nobody types IP addresses.** Phone hotspots give every laptop a new IP each time.
So the master runs a small **registry** (port 8099). Each friend's script finds the master on
the hotspot by itself (about 2 s), says "I'm alice at 10.67.29.112", and gets everyone's
current IP. The firewall rule allows the whole local network, so it never needs updating.

In the examples, the friends are `alice` and `bob`. Use your own names.

---

## Part A: one-time setup

### A1. Master laptop (yours)

```powershell
copy .env.master.example .env
notepad .env                 # FRIEND_A=alice   FRIEND_B=bob   (just the names)
```
PowerShell **as administrator**, in the project folder:
```powershell
.\scripts\open_firewall.ps1 -Role master
```

### A2. Each friend's PC

**Needs:** Windows 10/11, 8 GB RAM or more, about 10 GB free disk, admin rights.

1. PowerShell **as administrator**:
   `wsl --install` · `winget install -e --id Docker.DockerDesktop` · `winget install -e --id Git.Git` → **restart**.
2. Open **Docker Desktop**, accept, wait for *Engine running*.
3. Create `C:\Users\<name>\.wslconfig` with these lines, then run `wsl --shutdown` and reopen Docker Desktop:
   ```ini
   [wsl2]
   memory=4GB
   processors=4
   ```
4. Normal PowerShell:
   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   cd $HOME
   git clone https://github.com/<you>/SocialNetworkAnalysis.git
   cd SocialNetworkAnalysis
   copy .env.worker.example .env
   notepad .env
   ```
   | Setting | Alice | Bob |
   |---|---|---|
   | `NODE_NAME` | `alice` | `bob` |
   | `DATANODE_PORT` | `9876` | `9886` (**must differ**) |
5. PowerShell **as administrator**, in the project folder:
   ```powershell
   .\scripts\open_firewall.ps1 -Role worker
   ```
6. Download the images **now, at home** (about 1.5 GB, 5–10 min), so the first start is quick:
   ```powershell
   docker build -t sna-spark:3.5.3 docker/spark
   docker pull apache/hadoop:3.3.6
   ```

## Part B: every session (3 commands)

1. **Everyone joins the same hotspot.** Docker Desktop must be running on every laptop.
2. **Master:**
   ```powershell
   .\scripts\cluster_up.ps1
   ```
   It shows your IP, starts the registry, and **waits** (up to 3 min) until the friends join.
3. **Each friend** (while the master waits):
   ```powershell
   .\scripts\worker_up.ps1
   ```
   It finds the master, registers, waits for the other friend, writes the IPs and starts.
4. **Master, about 30 s later:**
   ```powershell
   .\scripts\cluster_status.ps1
   ```
   You want every PC listed under the registry, Spark workers (ALIVE) and HDFS DataNodes (Live):
   ```
   === Registry ===           === Spark workers ===      === HDFS DataNodes ===
   master 10.67.29.84         spark-worker-1 ALIVE       datanode       Live
   alice  10.67.29.112        worker-alice   ALIVE       datanode-alice Live
   bob    10.67.29.66         worker-bob     ALIVE       datanode-bob   Live
   ```
5. Run the pipeline: `.\scripts\run_all.ps1`. Then `cluster_status.ps1` should show
   *Under-replicated blocks: 0*, meaning every block is on 2 PCs.

**Someone joined late, or a laptop reconnected and got a new IP?** Everyone who is already running
runs their script again (`cluster_up.ps1` / `worker_up.ps1`). It refreshes the IPs, and HDFS data is kept.

**Storage causing trouble?** A friend can join with computing only: `.\scripts\worker_up.ps1 -NoStorage`.

## Updating a friend's PC (e.g. Alice from the old version)

```powershell
cd $HOME\SocialNetworkAnalysis
git pull
notepad .env                               # keep NODE_NAME=alice, add DATANODE_PORT=9876
.\scripts\open_firewall.ps1 -Role worker   # as administrator: the new rule works on any hotspot
docker pull apache/hadoop:3.3.6            # image for the new DataNode
```
Then continue with Part B. Code in `src/` and `jobs/` never needs updating on friends' PCs:
every job sends it to the executors.

## Experiments (for the report and the demo)

| Experiment | How | What should happen |
|---|---|---|
| Scaling | `run_all.ps1` with 1, 2, 3 PCs | Compare the timing tables (1 laptop: 121 s) |
| Worker leaves mid-job | During job 02, a friend runs `docker compose -f docker-compose.worker.yml stop spark-worker` | The job still finishes: Spark re-runs the lost tasks |
| DataNode leaves | A friend runs `docker compose -f docker-compose.worker.yml --profile storage stop datanode` | Data still readable. After about 2.5 min it shows Dead, and HDFS re-copies its blocks |
| Slow-task fix | `.\scripts\run_all.ps1 -Conf spark.speculation=true` | Spark starts backup copies of slow tasks |

## Daily use

| Who | Start | Stop |
|---|---|---|
| Master | `.\scripts\cluster_up.ps1` (`-NoWait`: don't wait for friends) | `docker compose -f docker-compose.yml -f docker-compose.cluster.yml stop` |
| Friend | `.\scripts\worker_up.ps1` (`-NoStorage`: computing only) | `docker compose -f docker-compose.worker.yml --profile storage stop` |

- **Back to one laptop (Phase 1):** `docker compose up -d --remove-orphans`. HDFS data is kept.
- **Run one job at a time** (fixed ports).
- **Project finished:** everyone runs `.\scripts\open_firewall.ps1 -Remove` as administrator.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `worker_up.ps1`: *Master laptop not found* | Is `cluster_up.ps1` running on the master? Same hotspot? Did the master run `open_firewall.ps1 -Role master` (once, as admin)? Some phones isolate devices from each other: try another phone. Or give the IP: `worker_up.ps1 -MasterIP <IP shown by cluster_up>` |
| `cluster_up.ps1` keeps waiting for a friend | That friend hasn't run `worker_up.ps1`, or their `NODE_NAME` doesn't match `FRIEND_A`/`FRIEND_B` (their script prints a warning) |
| Worker not ALIVE in `cluster_status.ps1` | Friend: `docker compose -f docker-compose.worker.yml logs spark-worker`. Usually their firewall: re-run `open_firewall.ps1 -Role worker` as admin |
| DataNode missing | Friend: `docker compose -f docker-compose.worker.yml --profile storage logs datanode`. *Retrying connect to server: namenode* = can't reach the master's port 8020 (master firewall) |
| Only one friend's DataNode shows; they replace each other | Both use the same `DATANODE_PORT`. Use 9876 and 9886 |
| Jobs suddenly take minutes, retries / `FetchFailed` | A laptop's IP changed or someone joined late: everyone re-runs their up script |
| `required variable ... is missing` | `.env` incomplete: compare with the `.example` file |
| Registry shows a friend at another friend's IP | Someone's `.env` still says `NODE_NAME=alice` (copied from the example). Fix the name, re-run `worker_up.ps1`, then the master re-runs `cluster_up.ps1` |
| DataNode keeps restarting; log: `sudo: PAM account management error` | Newer Docker versions break sudo in the Hadoop image. Once: `docker compose -f docker-compose.worker.yml --profile storage run --rm --no-deps --user root --entrypoint chown datanode hadoop:users /hdfs`, then `... --profile storage up -d datanode` |
| Master can ping a friend but every port times out | The friend's firewall drops everything: re-run `open_firewall.ps1 -Role worker` as admin; remove blocking Docker rules (`Get-NetFirewallRule -Direction Inbound -Action Block -Enabled True \| Where-Object DisplayName -match "docker\|vpnkit\|wsl" \| Remove-NetFirewallRule`); check third-party antivirus firewalls. ("Refused" instead of "timed out" = the container isn't running) |

## How it works (for the curious)

Docker on Windows hides containers behind NAT, so a container IP like `172.18.0.5` means nothing to
another PC. So:

- **Names, not IPs.** Every service introduces itself by name (`spark-master`, `worker-alice`,
  `datanode-alice`, …). On its own PC the name means "me"; on other PCs, `extra_hosts` maps it to that
  PC's current IP. The scripts write those IPs into `.env` from the registry.
- **Fixed ports, the same number on both sides**, because the port is part of each address.
- **One HDFS data port per PC.** The NameNode sees every friend's DataNode arriving from the same NAT
  address (`172.18.0.1`) and tells them apart by address + data port.

| Port | Where | Who connects |
|---|---|---|
| 8099 | registry (master) | friends' scripts: "who is where?" |
| 7077 | Spark master | workers register |
| 7078 | each worker | master starts executors |
| 7079 | each executor | other executors + driver (shuffle data) |
| 7080, 7081 | driver (master) | executors: tasks, our code, GraphFrames |
| 8020 | NameNode (master) | DataNodes (heartbeats), clients |
| 9866 / 9876 / 9886 | DataNode: master / Alice / Bob | clients and other DataNodes (block data) |
| 9867 | DataNodes (IPC) | other DataNodes (block recovery) |
| 8080, 8081, 9870, 4040 | web UIs | browsers |
