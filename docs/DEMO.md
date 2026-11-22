# Demo Checklist (final presentation)

## The evening before

- [ ] All 3 laptops: `git pull`. Images ready (`docker images` shows `sna-spark` and `apache/hadoop`).
- [ ] Full rehearsal on the hotspot you will use tomorrow: Part B of [PHASE2_SETUP.md](PHASE2_SETUP.md),
      then `.\scripts\run_all.ps1`. Write down the timing table.
- [ ] Master: HDFS already holds the dataset and results (they survive restarts), so the demo
      doesn't depend on downloading anything.
- [ ] Chargers, phone hotspot charged, laptops set to never sleep while plugged in.

## At the venue (10 min before)

1. Everyone joins **your** phone hotspot (not the campus Wi-Fi). Start Docker Desktop on every laptop.
2. Master: `.\scripts\cluster_up.ps1`. Friends: `.\scripts\worker_up.ps1`.
3. Master: `.\scripts\cluster_status.ps1`: 3 workers ALIVE, 3 DataNodes Live.
4. Open the browser tabs: http://localhost:8080 (Spark), http://localhost:9870 (HDFS → *Datanodes*),
   and the dashboard `ui\index.html` (already exported; works offline, even if the cluster fails).

## Demo script (about 10 minutes)

| # | Show | Command / where | Say |
|---|---|---|---|
| 1 | The cluster | `cluster_status.ps1`, Spark UI :8080 | "3 laptops, found each other by themselves through the registry" |
| 2 | The data in HDFS | HDFS UI :9870 → *Utilities → Browse* `/sna` | "Stored in HDFS, each block on 2 laptops" |
| 3 | Run the analysis | `.\scripts\run_all.ps1` (or one job: `.\scripts\submit.ps1 jobs\03_influencers.py`) | Point at :4040 → *Executors*: tasks on all 3 laptops |
| 4 | Results | **Dashboard** `ui\index.html`: Overview → Network graph (zoom, click user 107) → Influencers → Communities (click 1205) → Recommendations (user 460, click the first suggestion) | Same numbers as SNAP's reference (README, section 6); "everything here was computed by Spark" |
| 5 | Fault tolerance (Spark) | while job 02 runs, Bob: `docker compose -f docker-compose.worker.yml stop spark-worker` | "Job still finishes: Spark re-runs the lost tasks" |
| 6 | Fault tolerance (HDFS) | Bob: `docker compose -f docker-compose.worker.yml --profile storage stop datanode`, then `docker compose exec namenode hdfs fsck /sna/output -files -blocks -locations` | "Every block still has a copy elsewhere; after ~2.5 min HDFS re-copies it" |
| 7 | Lesson | README 6.5 | "On a hotspot the network is ~400× slower than inside one laptop: distribution pays off only for big data" |

After step 5/6, Bob restarts with `.\scripts\worker_up.ps1`.

## If something goes wrong

| Problem | Plan B |
|---|---|
| A friend can't find the master | `.\scripts\worker_up.ps1 -MasterIP <IP printed by cluster_up>` |
| A friend's DataNode misbehaves | That friend: `docker compose -f docker-compose.worker.yml --profile storage stop datanode`, then `.\scripts\worker_up.ps1 -NoStorage` |
| A friend's laptop fails completely | Master: `.\scripts\cluster_up.ps1 -NoWait`. The demo runs with the others |
| The hotspot fails / nothing connects | Master alone, Phase 1: `docker compose up -d --remove-orphans`, then `run_all.ps1`. Same results on one laptop (2 workers) |
