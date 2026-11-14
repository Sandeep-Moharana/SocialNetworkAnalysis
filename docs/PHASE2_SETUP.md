# Phase 2 Setup: a friend's PC as a Spark worker

Goal: your laptop stays the **master** (HDFS, Spark master, driver, 1 worker), and
each friend's PC adds one **Spark worker**. The analytics code does not change.

```
  YOUR LAPTOP (master)                         FRIEND's PC
  ┌───────────────────────────────┐            ┌──────────────────┐
  │ spark-master    namenode      │◄── Wi-Fi ─►│ worker-alice     │
  │ spark-client    datanode      │            │ (2 cores, 2 GB)  │
  │ spark-worker-1                │            └──────────────────┘
  └───────────────────────────────┘
```

Do it with **one friend first**. Add the second friend only after the first one works.
In the examples, the friend is called `alice`, your IP is `172.30.10.84`, and
Alice's IP is `172.30.10.99`. Use your own values.

---

## 0. Before you start (your laptop)

- Both PCs must be on the **same Wi-Fi**, with VPNs off.
- Some campus and café networks block devices from talking to each other. Step 2 checks this
  in 2 minutes, before your friend installs anything big.
- Commit and push the latest code, so your friend can download it:
  ```powershell
  git add . ; git commit -m "feat: phase 2 cluster config" ; git push
  ```
  If the GitHub repo is private, add your friend as a collaborator, or send them the repo as a zip.

## 1. Swap IP addresses

On **both** PCs, run `ipconfig` and find **"IPv4 Address"** under **"Wireless LAN adapter Wi-Fi"**.
Send each other the number.

IP addresses can change when you reconnect to Wi-Fi. Check them again each time you meet.
If one changed, update `.env` and repeat steps 3 and 6.

## 2. Your laptop: start the master

Open PowerShell in the project folder.

```powershell
copy .env.master.example .env
notepad .env
```
Set `FRIEND_A=alice` and `FRIEND_A_IP=<Alice's IP>`. Leave `FRIEND_B` as it is for now. Save the file.

Open firewall ports for Alice. Use **PowerShell → "Run as administrator"**, then `cd` to the project folder:
```powershell
.\scripts\open_firewall.ps1 -Role master
```

Start the cluster in Phase 2 mode, in a normal PowerShell:
```powershell
.\scripts\cluster_up.ps1
```

**Quick network test (on Alice's PC, nothing installed yet):**
```powershell
Test-NetConnection 172.30.10.84 -Port 7077      # your IP
```
- `TcpTestSucceeded : True`: the network works. Continue.
- `False`: stop here and look at Troubleshooting. Installing Docker will not fix this.

## 3. Friend's PC: one-time install (about 30 min, mostly downloads)

**Needs:** Windows 10/11, at least 8 GB RAM, about 10 GB free disk, admin rights.

1. PowerShell → **"Run as administrator"**:
   ```powershell
   wsl --install
   winget install -e --id Docker.DockerDesktop
   winget install -e --id Git.Git
   ```
   **Restart the PC.**
2. Start **Docker Desktop** and accept the terms. Keep "Use WSL 2 based engine" on.
   Wait until it says *Engine running*.
3. Limit Docker's memory. Create the file `C:\Users\<name>\.wslconfig` with:
   ```ini
   [wsl2]
   memory=4GB
   processors=4
   ```
   Then run `wsl --shutdown` in PowerShell and restart Docker Desktop.
4. In a normal PowerShell, allow our scripts to run (one time):
   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   ```

## 4. Friend's PC: get the project and set it up

Normal PowerShell:
```powershell
cd $HOME
git clone https://github.com/<you>/SocialNetworkAnalysis.git
cd SocialNetworkAnalysis
copy .env.worker.example .env
notepad .env
```
Set:
```
NODE_NAME=alice              # must match FRIEND_A on your laptop
MASTER_IP=172.30.10.84       # YOUR laptop's IP
```
Leave `OTHER_FRIEND` as it is for now. Save the file.

Open the firewall. Use **PowerShell → "Run as administrator"**, then `cd $HOME\SocialNetworkAnalysis`:
```powershell
.\scripts\open_firewall.ps1 -Role worker
```

## 5. Friend's PC: start the worker

Normal PowerShell, in the project folder:
```powershell
.\scripts\worker_up.ps1
```
- It first checks that it can reach your master. If not, it stops with a hint.
- The **first** run builds the Spark image: about 1 GB download, 5–10 minutes.
- After that, starting takes seconds. The worker also restarts by itself after a reboot,
  as long as Docker Desktop is running.

## 6. Check that it is connected (your laptop)

**Check 1: does the master see the worker?** Open http://localhost:8080. Under *Workers* you should see:

| Worker | State |
|---|---|
| spark-worker-1 | ALIVE |
| worker-alice | ALIVE |

Or in PowerShell:
```powershell
(Invoke-RestMethod http://localhost:8080/json/).workers | Select-Object host, state, cores
```

**Check 2: does real work run there?** This is the real test. A worker can show ALIVE while
jobs still fail, if the connections the other way are blocked.
```powershell
.\scripts\submit.ps1 jobs\00_smoke_test.py
```
Success looks like this:
```
[1] Tasks ran on executors: ['spark-worker-1', 'worker-alice']
...
SMOKE TEST PASSED
```
`worker-alice` in that list means tasks ran on Alice's PC, read HDFS from your laptop,
and sent results back. **You now have a multi-PC cluster.**

## 7. Adding the second friend (Bob)

1. On your laptop's `.env`: set `FRIEND_B=bob` and `FRIEND_B_IP=<Bob's IP>`.
2. On Alice's `.env`: set `OTHER_FRIEND=bob` and `OTHER_FRIEND_IP=<Bob's IP>`.
3. On Bob's PC: steps 3–5, with `NODE_NAME=bob`, `OTHER_FRIEND=alice` and `OTHER_FRIEND_IP=<Alice's IP>`.
4. Everyone re-runs `open_firewall.ps1` (as admin) and their up script (`cluster_up.ps1` or `worker_up.ps1`).

## Daily use

| Who | Start | Stop |
|---|---|---|
| You | `.\scripts\cluster_up.ps1` | `docker compose stop` |
| Friend | `.\scripts\worker_up.ps1` | `docker compose -f docker-compose.worker.yml down` |

- **Back to one laptop** (Phase 1, 2 local workers): `docker compose up -d`. HDFS data is kept.
- **Run one job at a time.** The ports are fixed, so two jobs at once would clash.
- **When the project is done:** everyone runs `.\scripts\open_firewall.ps1 -Remove` as admin.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Test-NetConnection ... 7077` is `False` | (1) Is `cluster_up.ps1` running on your laptop? (2) Is it the right IP? Check `ipconfig` again. (3) Did you run `open_firewall.ps1 -Role master` after entering the friend's IP? (4) The Wi-Fi may block devices from reaching each other (common on campus): use a phone hotspot or a home router |
| `worker_up.ps1` says it cannot reach the master | Same as above |
| Worker never appears at :8080 | On the friend's PC: `docker compose -f docker-compose.worker.yml logs`. Usually a wrong `MASTER_IP` |
| Worker shows ALIVE, but the smoke test hangs at `Initial job has not accepted any resources` or executors keep exiting | Your laptop can't reach the friend's ports 7078/7079: run `open_firewall.ps1 -Role worker` on the friend's PC. Check that the friend's IP in your `.env` is current, then re-run `cluster_up.ps1` |
| `Cannot assign requested address` in the worker log | A PC's own name is in its own `extra_hosts`. Check that `OTHER_FRIEND` in `.env` is not this PC's name |
| `required variable ... is missing` | `.env` is missing or a value is empty: compare it with the `.example` file |
| Errors fetching shuffle data (job 02) with two friends | The two friends can't reach each other: check `OTHER_FRIEND_IP` and both firewalls |
| Works for hours, then breaks | Someone's IP changed (Wi-Fi reconnect) or a laptop went to sleep: see step 1 |
| Rare: your Wi-Fi IP starts with the same numbers as a Docker network | On the friend's PC, `docker network inspect sna-worker_default` shows the subnet. If it contains `MASTER_IP`, the worker's Docker network needs a fixed, different subnet in `docker-compose.worker.yml` |

## How it works (for the curious)

Docker on Windows hides each container behind its PC, so a container IP like `172.18.0.5`
means nothing to another PC. So:

- **Everyone introduces themselves by name** (`spark-master`, `spark-client`, `worker-alice`, …).
  Inside its own container, a name means "me". On other PCs, `extra_hosts` (filled from `.env`)
  maps it to that PC's Wi-Fi IP.
- **Every port is fixed and published with the same number on both sides**, because the port
  is part of the address each process announces:

| Port | Listens on | Who connects |
|---|---|---|
| 7077 | master (your laptop) | workers register |
| 7078 | each worker | the master starts executors |
| 7079 | each executor | other executors and the driver (shuffle data) |
| 7080, 7081 | driver (your laptop) | executors: tasks, our code, GraphFrames |
| 8020, 9866 | HDFS (your laptop) | executors read and write data |
| 8080, 8081, 9870, 4040 | web UIs | browsers |

The settings live in `docker-compose.yml`, `docker-compose.cluster.yml`,
`docker-compose.worker.yml`, `docker/spark-defaults.conf` and `.env`.
