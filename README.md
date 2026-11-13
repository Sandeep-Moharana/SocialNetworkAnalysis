# Social Network Analysis with HDFS, Spark and GraphFrames

Distributed graph analytics on real social-network data:
**influencer detection, community detection, network statistics, and friend recommendation**,
stored in HDFS, processed with Apache Spark, and analyzed with GraphFrames.

## Status

| Phase | Description | Status |
|---|---|---|
| 0 | Plan, architecture, repo | ✅ |
| 1 | MVP on one machine (Dockerized HDFS + Spark cluster, ego-Facebook dataset) | 🚧 in progress |
| 2 | Real cluster on multiple laptops | ⏳ |
| 3 | Bigger datasets, more algorithms, evaluation, visualization | ⏳ |

Phase 1 progress:
- [x] 1.1 Docker cluster (HDFS + Spark standalone)
- [x] 1.2 Smoke test (GraphFrames PageRank + HDFS round trip)
- [x] 1.3 Dataset download + load into HDFS
- [ ] 1.4 Core pipeline (config, session, loader)
- [ ] 1.5 Network statistics
- [ ] 1.6 Influencer detection
- [ ] 1.7 Community detection
- [ ] 1.8 Friend recommendation
- [ ] 1.9 Tests + results

## Architecture (Phase 1)

```
 laptop ──► spark-client (driver) ──► spark-master ──► spark-worker-1, spark-worker-2
                    │                                        │
                    └──────────────► HDFS: namenode ◄── datanode (blocks)
```
Details: [docs/PLAN.md](docs/PLAN.md)

## Quickstart

Prerequisites: Docker Desktop (WSL2), Git. Full guide: [docs/SETUP.md](docs/SETUP.md).

```powershell
docker compose up -d --build                  # build our Spark image, start HDFS + Spark
.\scripts\submit.ps1 jobs\00_smoke_test.py    # verify the stack
.\scripts\download_dataset.ps1                # get ego-Facebook
.\scripts\load_to_hdfs.ps1                    # put it in HDFS
```

## Tech stack

Hadoop HDFS 3.3.6 · Apache Spark 3.5.3 (PySpark) · GraphFrames 0.8.4 · Docker Compose

## Repository layout

```
docker-compose.yml   the cluster
docker/              Hadoop + Spark config
scripts/             download, load to HDFS, submit jobs
jobs/                Spark jobs (entry points)
src/sna/             reusable library (coming in step 1.4)
docs/                plan and setup guide
data/                local downloads (not committed)
```

## Dataset

[SNAP ego-Facebook](https://snap.stanford.edu/data/ego-Facebook.html): 4,039 users, 88,234 friendships.
J. McAuley and J. Leskovec, *Learning to Discover Social Circles in Ego Networks*, NIPS 2012.
