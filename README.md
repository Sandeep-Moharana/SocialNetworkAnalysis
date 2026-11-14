# Social Network Analysis with HDFS, Spark and GraphFrames

Distributed graph analytics on real social-network data:
**influencer detection, community detection, network statistics, and friend recommendation**,
stored in HDFS, processed with Apache Spark, and analyzed with GraphFrames.

## Status

| Phase | Description | Status |
|---|---|---|
| 0 | Plan, architecture, repo | ✅ |
| 1 | MVP on one machine (Dockerized HDFS + Spark cluster, ego-Facebook dataset) | ✅ `v0.1` |
| 2 | Real cluster on multiple laptops | 🚧 in progress |
| 3 | Bigger datasets, more algorithms, evaluation, visualization | ⏳ |

Phase 1 progress:
- [x] 1.1 Docker cluster (HDFS + Spark standalone)
- [x] 1.2 Smoke test (GraphFrames PageRank + HDFS round trip)
- [x] 1.3 Dataset download + load into HDFS
- [x] 1.4 Core pipeline (config, session, loader): `jobs/01_build_graph.py`
- [x] 1.5 Network statistics: `jobs/02_network_stats.py`
- [x] 1.6 Influencer detection: `jobs/03_influencers.py`
- [x] 1.7 Community detection: `jobs/04_communities.py`
- [x] 1.8 Friend recommendation: `jobs/05_recommend.py`
- [x] 1.9 Tests + results: 35 unit tests (`scripts\test.ps1`), full pipeline (`scripts\run_all.ps1`)

Phase 2 progress ([guide](docs/PHASE2_SETUP.md)):
- [x] 2.1 Cluster config: fixed names + ports, master/worker compose files, setup scripts (tested with a simulated friend PC)
- [ ] 2.2 First friend's PC joins as a Spark worker
- [ ] 2.3 Second friend, timing vs Phase 1, fault-tolerance demo
- [ ] 2.4 HDFS across PCs (DataNode per friend, replication 2)
- [ ] 2.5 Results, tag `v0.2`

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
.\scripts\submit.ps1 jobs\01_build_graph.py   # build the graph: 4,039 vertices, 88,234 connections
.\scripts\submit.ps1 jobs\02_network_stats.py # degrees, components, triangles, clustering
.\scripts\submit.ps1 jobs\03_influencers.py   # top-10 by degree centrality and PageRank
.\scripts\submit.ps1 jobs\04_communities.py   # Label Propagation communities + modularity
.\scripts\submit.ps1 jobs\05_recommend.py --users 460 2627   # "people you may know"

.\scripts\test.ps1                            # unit tests (tiny graphs, known answers)
.\scripts\run_all.ps1                         # jobs 01-05 in order, with a timing table
```

## Testing

| Check | Command | What it proves |
|---|---|---|
| Unit tests (35) | `.\scripts\test.ps1` | Every analysis function gives the hand-calculated answer on tiny graphs. Runs in Spark local mode: no workers or HDFS needed, about 40 s |
| Smoke test | `.\scripts\submit.ps1 jobs\00_smoke_test.py` | The cluster works: both workers, GraphFrames, HDFS |
| Full pipeline | `.\scripts\run_all.ps1` | All jobs run end to end on real data |

Each test file in [tests/](tests/) draws its tiny graph in the docstring and explains
the expected numbers. Recommendations are also compared with an independent
plain-Python brute force on random graphs.

## Results so far (ego-Facebook)

| Statistic | Value | SNAP reference |
|---|---|---|
| Vertices / connections | 4,039 / 88,234 | 4,039 / 88,234 ✅ |
| Density | 0.0108 | |
| Degree median / avg / max | 25 / 43.69 / 1,045 | |
| Connected components | 1 (100% of vertices) | largest WCC = 4,039 ✅ |
| Triangles | 1,612,010 | 1,612,010 ✅ |
| Avg clustering coefficient | 0.6055 | 0.6055 ✅ |
| Transitivity | 0.5192 | |

Most users have 16–63 friends, while a few hubs have hundreds (user 107 has 1,045):
a heavy-tailed degree distribution, typical of social networks.

### Influencers

| Rank | By degree (friends) | By PageRank (score, 1.0 = average user) |
|---|---|---|
| 1 | 107 (1,045) | 3437 (30.6) |
| 2 | 1684 (792) | 107 (27.8) |
| 3 | 1912 (755) | 1684 (25.5) |
| 4 | 3437 (547) | 0 (25.1) |
| 5 | 0 (347) | 1912 (15.4) |
| 6–10 | 2543, 2347, 1888, 1800, 1663 | 348, 686, 3980, 414, 483 |

- The two rankings agree on the top 5, but only 5 of the top 10 overlap (correlation over all users: 0.68).
- **PageRank finds the "ego" users.** This dataset was collected from the friend lists of 10 users
  (0, 107, 348, 414, 686, 698, 1684, 1912, 3437, 3980), and 9 of them are in PageRank's top 10.
  Each one is the hub that connects their own circle of friends to everyone else.
- User **3980 has only 59 friends but ranks 8th** by PageRank: few connections, but to the right people.
  Users 2543, 2347, … have more friends, but inside one dense circle, so they rank lower.

### Communities (Label Propagation, 10 rounds)

| Metric | Value |
|---|---|
| Communities | 70 (median size 15, largest 476 = 11.8% of users) |
| Connections inside a community | 92.2% |
| Modularity Q | **0.808** (> 0.3 = clear structure; 5 rounds: 0.789, 20 rounds: 0.813) |

| Largest communities | Size | Density inside | Leader (friends) |
|---|---|---|---|
| 1205 | 476 | 0.15 | 107 (1,045) |
| 3277 | 450 | 0.08 | 1684 (792) |
| 559 | 327 | 0.10 | 483 (231) |
| 2344 | 295 | 0.23 | 1912 (755) |
| 2353 | 237 | **0.59** | 2543 (294) |
| 200 | 228 | 0.08 | 0 (347) |

- **The ego users lead communities:** 6 of the 10 largest communities are led by one of the
  ego users that PageRank found in step 1.6 (107, 1684, 1912, 0, 686, 3437).
- **This explains step 1.6:** user 2543 has many friends but low PageRank. Their community
  is extremely dense (59% of all possible pairs are friends): a closed circle where everyone
  knows everyone, with few links to the outside.

### Friend recommendations (mutual friends, Adamic-Adar as tie-breaker)

```
--- User 460 (66 friends) ---
  rank  suggest  mutual  adamic-adar  same comm.  because you both know
     1      483      41        9.968  yes         348, 353, 366, 370, 373, ...
     2      561      41        9.851  yes         348, 353, 360, 370, 373, ...
     3      513      39        9.183  yes         348, 353, 360, 366, 373, ...
```

- Checked against a plain-Python brute force for 8 users: identical candidates, scores and order.
- **85% of suggestions fall in the user's own community** (50 random non-ego users, top 10 each).
  The two features agree without using each other's results.
- Ego users (0, 107, …) are the exception: they already know their whole circle, so every
  suggestion comes from another circle (0% same community). Correct behavior, not a bug.
- Ties are common (user 460: ranks 1 and 2 both have 41 mutual friends). Adamic-Adar breaks them by
  counting mutual friends who are *not* hubs as stronger evidence.

### Performance baseline (Phase 1: 1 laptop, 2 workers × 2 cores × 2 GB)

| Job | Seconds |
|---|---|
| 01 build graph | 12 |
| 02 network stats | 39 |
| 03 influencers | 26 |
| 04 communities | 29 |
| 05 recommend | 15 |
| **Total** | **121** |

Every job is under the 2-minute target from [docs/PLAN.md](docs/PLAN.md). About 10 s of each is
Spark start-up. Phase 2 will run `scripts\run_all.ps1` on the multi-PC cluster and compare.

## Configuration

| File | Holds | Change it when |
|---|---|---|
| [config/sna.ini](config/sna.ini) | HDFS folder layout, dataset formats | adding a dataset |
| [docker/spark-defaults.conf](docker/spark-defaults.conf) | Spark master URL, HDFS NameNode, memory | moving to another cluster |
| [docker/hadoop.env](docker/hadoop.env) | HDFS settings (replication, …) | moving to another cluster |
| `.env` (from [.env.master.example](.env.master.example) / [.env.worker.example](.env.worker.example)) | Phase 2: names and Wi-Fi IPs of the PCs | an IP changes |

The analytics code (`src/sna`, `jobs/`) contains no hosts or paths, so it runs unchanged on any cluster.

## Tech stack

Hadoop HDFS 3.3.6 · Apache Spark 3.5.3 (PySpark) · GraphFrames 0.8.4 · Docker Compose

## Repository layout

```
docker-compose.yml   the cluster (Phase 1; also the master laptop in Phase 2)
docker-compose.cluster.yml   Phase 2 add-on for the master: friends' names -> IPs
docker-compose.worker.yml    Phase 2: a friend's PC (one Spark worker)
docker/              Hadoop + Spark config, our Spark image
config/sna.ini       app settings: HDFS paths, datasets
scripts/             download, load to HDFS, submit jobs
jobs/                Spark jobs (entry points): load -> build graph -> analyze -> write
src/sna/             reusable library: config, session, loaders, storage, cli
src/sna/features/    analysis: stats, influencers, communities, recommend
tests/               unit tests on tiny graphs (stdlib unittest, no extra packages)
docs/                plan and setup guide
data/                local downloads (not committed)
```

## Dataset

[SNAP ego-Facebook](https://snap.stanford.edu/data/ego-Facebook.html): 4,039 users, 88,234 friendships.
J. McAuley and J. Leskovec, *Learning to Discover Social Circles in Ego Networks*, NIPS 2012.
