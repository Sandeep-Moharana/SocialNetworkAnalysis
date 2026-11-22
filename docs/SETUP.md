# Setup Guide (Phase 1: single machine, Windows)

Goal: a 6-container cluster (HDFS NameNode + DataNode, Spark master + 2 workers + client)
running on your laptop, verified by a smoke test.

Requirements: Windows 10/11, 16 GB RAM recommended (8 GB minimum, then use 1 worker), about 15 GB free disk.

---

## 1. Install the tools (one time)

Open **PowerShell as Administrator**:

```powershell
wsl --install                      # WSL2: the Linux kernel Docker runs on. REBOOT afterwards.
winget install -e --id Docker.DockerDesktop
winget install -e --id Git.Git
```

After the reboot:
1. Start **Docker Desktop**, accept the terms, and keep the default *"Use WSL 2 based engine"*.
2. Limit how much RAM Docker may use. Create `C:\Users\<you>\.wslconfig`:
   ```ini
   [wsl2]
   memory=8GB
   processors=6
   ```
   Then run `wsl --shutdown` and restart Docker Desktop.
3. Check the install (in a **new** terminal):
   ```powershell
   docker --version; docker compose version; git --version
   ```
4. Let PowerShell run our scripts (one time, normal terminal):
   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   ```

> **Optional:** install Python 3.10+ and run `pip install pyspark==3.5.3` so VS Code can autocomplete PySpark.
> Jobs never run with this local Python; they run inside the containers.

## 2. Git + GitHub (Step 0)

```powershell
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"

cd C:\Users\<you>\Codes\SocialNetworkAnalysis
git init -b main
git add .
git commit -m "chore: project plan, docker cluster, setup scripts"
```
On GitHub, create an **empty** repo (no README), then:
```powershell
git remote add origin https://github.com/<you>/SocialNetworkAnalysis.git
git push -u origin main
git tag v0.0; git push --tags
```

## 3. Start the cluster

```powershell
docker compose up -d --build   # first time: downloads about 2 GB of images and builds our Spark image
docker compose ps              # all 6 services should be "running"
```

> **Why `--build`?** The Spark containers use our own image, `sna-spark` ([docker/spark/Dockerfile](../docker/spark/Dockerfile)).
> It is the official Spark image plus the Python packages in
> [docker/spark/requirements.txt](../docker/spark/requirements.txt) (for example, numpy, which GraphFrames needs).
> Use `--build` the first time and every time you change those two files. A plain `docker compose up -d` is enough otherwise.

Open these in a browser:

| UI | URL | What to check |
|---|---|---|
| HDFS NameNode | http://localhost:9870 | *Datanodes* tab → 1 live node |
| Spark master | http://localhost:8080 | *Workers* → 2 ALIVE, 4 cores total |
| Running job | http://localhost:4040 | only while a job is running |

## 4. Smoke test

```powershell
.\scripts\submit.ps1 jobs\00_smoke_test.py
```
The first run takes about 1 minute longer because it downloads GraphFrames. Expected output ends with:
```
[1] Tasks ran on executors: ['spark-worker-1', 'spark-worker-2']
...
[4] Wrote and read back 4 rows at hdfs://namenode:8020/sna/tmp/smoke_test

SMOKE TEST PASSED
```
✅ **Step 1.1 + 1.2 done.** Commit and push.

## 5. Dataset into HDFS

```powershell
.\scripts\download_dataset.ps1       # -> data\raw\facebook\facebook_combined.txt (88,234 lines)
.\scripts\load_to_hdfs.ps1           # -> hdfs:///sna/raw/facebook/
```
Check it at http://localhost:9870 → *Utilities* → *Browse the file system* → `/sna/raw/facebook`.

✅ **Step 1.3 done.**

## 6. Daily use

| Task | Command |
|---|---|
| Start | `docker compose up -d` |
| Run a job | `.\scripts\submit.ps1 jobs\01_build_graph.py --dataset facebook` |
| Run all jobs + timing table | `.\scripts\run_all.ps1` |
| Run the unit tests | `.\scripts\test.ps1` (exit code 0 = all passed) |
| Re-parse a dataset after changing `config/sna.ini` or the loader | add `--rebuild` to `01_build_graph.py` |
| Add a Python package for jobs | add it to `docker/spark/requirements.txt`, then `docker compose up -d --build` |
| Pause (keeps HDFS data) | `docker compose stop` |
| Remove the containers (HDFS data is kept on volumes) | `docker compose down` |
| Remove everything, **including HDFS data** (then re-run `load_to_hdfs.ps1`) | `docker compose down -v` |
| Phase 2: who is in the cluster | `.\scripts\cluster_status.ps1` |
| Logs of one service | `docker compose logs -f spark-worker-1` |
| HDFS shell | `docker compose exec namenode hdfs dfs -ls -R /sna` |
| PySpark shell on the cluster | `docker compose exec spark-client /opt/spark/bin/pyspark` |

**Phase 2 (friends' PCs as workers):** see [PHASE2_SETUP.md](PHASE2_SETUP.md).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `port is already allocated` | Another program uses 8080/9870/4040. Stop it or change the left-hand port in `docker-compose.yml` |
| Spark UI shows 0 workers | `docker compose logs spark-worker-1`; usually the master was not ready yet. Run `docker compose restart spark-worker-1 spark-worker-2` |
| Job hangs on *"Initial job has not accepted any resources"* | Workers are missing or have too little memory. Check the :8080 UI |
| `Name node is in safe mode` | Wait 30 s after start-up, or `docker compose exec namenode hdfs dfsadmin -safemode leave` |
| `ModuleNotFoundError: No module named 'numpy'` (or another package) | Spark containers run the plain image. Run `docker compose up -d --build`; check with `docker compose exec spark-client python3 -c "import numpy"` |
| GraphFrames download fails | Container needs internet. Retry; check proxy/VPN |
| Laptop runs out of RAM | Remove `spark-worker-2` from `docker-compose.yml` and lower `memory` in `.wslconfig` |
| `scripts cannot be loaded ... running scripts is disabled` | Run step 1.4 (`Set-ExecutionPolicy`) |
