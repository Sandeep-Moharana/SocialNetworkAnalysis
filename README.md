# Social Network Analysis on a Distributed Cluster using HDFS, Spark and GraphFrames

**Lab Report**

| | |
|---|---|
| Course | *<course code and name>* |
| Team | *<name (roll no.)>*, *<name (roll no.)>*, *<name (roll no.)>* |
| Instructor | *<instructor name>* |
| Date | *<submission date>* |
| Repository | *<GitHub URL>* |

---

## Abstract

We built a distributed system that analyzes a real social network (SNAP ego-Facebook: 4,039 users,
88,234 friendships). The data is stored in **HDFS**, processed with **Apache Spark** and analyzed with
**GraphFrames**. The system computes network statistics, detects influencers (PageRank), finds
communities (Label Propagation) and recommends friends (mutual friends + Adamic-Adar). We first ran it
as a containerized cluster on one laptop, then on several students' laptops connected over Wi-Fi.
All results match published reference values and hand-calculated tests (35 unit tests). The whole
pipeline takes 121 s on one laptop, 362 s on two and 443 s on three, because the Wi-Fi link is about
400× slower than the network inside one machine. On three laptops, a job survived a worker leaving
mid-run, and distributed HDFS (2 copies per block) kept every file readable after losing a storage
node, then restored its 2 copies automatically.

## 1. Introduction

Social networks are graphs: people are **vertices** and friendships are **edges**. Large graphs
do not fit on one machine, so they need distributed storage and processing.

**Objectives**
1. Store a social graph in a distributed file system (HDFS).
2. Implement four analyses with Spark and GraphFrames: **network statistics, influencer detection,
   community detection, friend recommendation**.
3. Run the same code on a single machine and on a multi-PC cluster, with no code changes.
4. Validate correctness and measure performance and fault tolerance.

## 2. Background

| Tool | Role in this project |
|---|---|
| **HDFS** (Hadoop 3.3.6) | Distributed storage. The *NameNode* keeps metadata and *DataNodes* store data blocks, replicated on several machines |
| **Apache Spark** (3.5.3, PySpark) | Distributed processing. A *driver* splits work into *tasks* that run on *executors* on *worker* machines |
| **GraphFrames** (0.8.4) | Graph algorithms on Spark DataFrames: PageRank, Label Propagation, connected components, triangle count |
| **Docker Compose** | Runs every node as a container, so each PC has the same setup |

| Algorithm | Idea |
|---|---|
| Degree centrality | number of friends ÷ (n − 1) |
| PageRank | a user is important if important users are connected to them |
| Label Propagation (LPA) | each user repeatedly adopts the most common label among friends; groups emerge |
| Modularity Q | how much denser communities are inside than chance (> 0.3 = clear structure) |
| Clustering coefficient | fraction of a user's friend pairs who are also friends |
| Adamic-Adar | mutual friends weighted by 1 / log(their degree): a shared friend with few friends counts more |

## 3. System Design

### 3.1 Architecture

**Phase 1: one laptop.** Six containers form a real (small) cluster:

```
 spark-client (driver) ──► spark-master ──► spark-worker-1, spark-worker-2
        │                                         │
        └────────────────► HDFS: namenode ◄── datanode
```

**Phase 2: several laptops on the same Wi-Fi.**

```
  Laptop 1 (master)                 Laptop 2                Laptop 3
  ┌───────────────────────────┐     ┌────────────────┐      ┌────────────────┐
  │ spark-master   namenode   │◄───►│ worker-alice   │◄────►│ worker-bob     │
  │ spark-client   datanode   │     │ datanode-alice │      │ datanode-bob   │
  │ spark-worker-1            │     └────────────────┘      └────────────────┘
  └───────────────────────────┘
```

### 3.2 Data flow

Every analysis is a separate Spark job with the same four steps:

```
HDFS raw edge list ─► load + clean ─► GraphFrame (vertices, edges) ─► algorithm ─► results as Parquet in HDFS
```
Cleaning removes self-loops and duplicates. Because friendship is mutual, each edge is stored in
both directions (88,234 friendships → 176,468 directed edges).

### 3.3 Key design decisions

| Decision | Reason |
|---|---|
| Docker instead of a native install | Hadoop on Windows is fragile; containers give each PC the same setup |
| Settings outside the code (`config/sna.ini`, `docker/spark-defaults.conf`, `.env`) | Moving from 1 to N machines changed **only configuration**, never analytics code |
| Analysis functions do no I/O (they take a graph and return tables) | They can be unit-tested on tiny graphs without a cluster |
| Our Python package is zipped and shipped with each job | Executors on other PCs need no copy of the code |
| **Names + fixed ports** for every service | Docker on Windows hides containers behind NAT; each service announces a name (e.g. `worker-alice`), which every PC maps to the right Wi-Fi IP |
| One HDFS data port per PC | The NameNode sees all remote DataNodes from the same NAT address and tells them apart by port |
| Automatic IP discovery (a small registry on the master) | Phone hotspots give new IPs every session. Each laptop detects its own IP, finds the master by scanning the hotspot (~2 s) and learns everyone's current IP. The firewall allows the local subnet, so no manual changes are needed |
| HDFS replication 2 + persistent volumes | Data survives a laptop leaving and container restarts |

## 4. Implementation

**Dataset.** SNAP ego-Facebook [1]: friend lists of 10 "ego" users and their friends, anonymized.

| Job | Feature | Method | Output (HDFS) |
|---|---|---|---|
| `01_build_graph.py` | Graph building | parse, clean, symmetrize, cache as Parquet | `processed/` |
| `02_network_stats.py` | Network statistics | degrees, connected components, triangle count, clustering | `stats/` |
| `03_influencers.py` | Influencer detection | degree centrality, PageRank (until converged, tol 1e-4) | `influencers/` |
| `04_communities.py` | Community detection | Label Propagation (10 rounds), modularity | `communities/` |
| `05_recommend.py` | Friend recommendation | friends-of-friends ranked by mutual friends, ties broken by Adamic-Adar | `recommendations/` |

Code layout: reusable library in `src/sna/` (config, loaders, `features/`), entry points in
`jobs/`, tests in `tests/`, cluster files in `docker/` and `docker-compose*.yml`.

## 5. Experimental Setup

| | Phase 1 | Phase 2 |
|---|---|---|
| Machines | 1 laptop (Windows 11, Docker Desktop) | 3 laptops on a phone hotspot |
| Spark | 2 workers × 2 cores × 2 GB | 1 worker per laptop × 2 cores × 2 GB |
| HDFS | 1 DataNode | 1 DataNode per laptop, replication 2 |
| Measurement | `scripts/run_all.ps1` (all 5 jobs, wall-clock time per job) | same |

**Validation.** Results were compared against (a) SNAP's published statistics, (b) hand-calculated
answers on tiny graphs (35 unit tests), and (c) an independent plain-Python brute force for recommendations.

## 6. Results

### 6.1 Network statistics

| Statistic | Our result | SNAP reference [1] |
|---|---|---|
| Users / friendships | 4,039 / 88,234 | 4,039 / 88,234 ✅ |
| Connected components | 1 | largest = 4,039 ✅ |
| Triangles | 1,612,010 | 1,612,010 ✅ |
| Avg. clustering coefficient | 0.6055 | 0.6055 ✅ |
| Density / transitivity | 0.0108 / 0.5192 | |
| Degree median / mean / max | 25 / 43.7 / 1,045 | |

The degree distribution is **heavy-tailed**: most users have 16–63 friends, and a few hubs have hundreds.

### 6.2 Influencers

| Rank | By degree (friends) | By PageRank (1.0 = average) |
|---|---|---|
| 1 | 107 (1,045) | 3437 (30.6) |
| 2 | 1684 (792) | 107 (27.8) |
| 3 | 1912 (755) | 1684 (25.5) |
| 4 | 3437 (547) | 0 (25.1) |
| 5 | 0 (347) | 1912 (15.4) |

- **PageRank found the dataset's ego users:** 9 of its top 10 are among the 10 users the data was
  collected from. Each one connects their friend circle to the rest of the network.
- Degree and PageRank overlap in only 5 of the top 10 (correlation 0.68). User 3980 has only 59
  friends but ranks 8th by PageRank: few links, but to important users.

### 6.3 Communities

| Communities | Largest | Edges inside communities | Modularity Q |
|---|---|---|---|
| 70 | 476 users (11.8%) | 92.2% | **0.808** |

Q = 0.808 indicates very strong community structure. 6 of the 10 largest communities are led by an
ego user from 6.2. User 2543 has many friends but low PageRank: their community is 59% dense, a closed
circle with few links outside.

### 6.4 Friend recommendations

```
User 460 (66 friends)
 rank  suggest  mutual  adamic-adar  same community
    1      483      41        9.968  yes
    2      561      41        9.851  yes
    3      513      39        9.183  yes
```
- Identical to the brute-force check for all tested users.
- **85% of suggestions fall in the user's own community** (50 random users), so features 6.3 and 6.4
  agree without using each other's results.

### 6.5 Performance: one, two and three laptops

| Job | 1 laptop | 2 laptops (hotspot) | 3 laptops (hotspot) |
|---|---|---|---|
| 01 build graph | 12 s | 10 s | 39 s |
| 02 network stats | 39 s | 92 s | 192 s |
| 03 influencers | 26 s | 62 s | 75 s |
| 04 communities | 29 s | 95 s | 114 s |
| 05 recommend | 15 s | 84 s | 23 s |
| **Total** | **121 s** | **362 s** | **443 s** |

The results were identical on all setups, and in every 3-laptop job each laptop ran an executor.
Over the hotspot the same job varies a lot between runs: an earlier 3-laptop run took 425 s, and
job 02 took between 121 s and 192 s. Only the trend is meaningful: **more laptops = slower** for this
small graph. To explain the slowdown, we measured:

| | Inside one laptop | Between laptops (hotspot) |
|---|---|---|
| Transfer 20 MB | 0.03 s | 27 s (~400× slower) |
| Round-trip latency | < 1 ms | ~10 ms |
| Same CPU work | 0.06 s | 0.12 s (second laptop's CPU) |

### 6.6 Distributed HDFS and fault tolerance

Tested on the 3 real laptops (3 Spark workers, 3 DataNodes):

| Test | How | Result |
|---|---|---|
| Replication | `hdfs fsck` | every block stored as 2 copies on 2 different laptops |
| Worker leaves mid-job | stop one Spark worker 50 s into job 02 | Spark re-ran the lost tasks on the other laptops; job finished in **124 s** (normal: 121 s), same results |
| DataNode leaves | stop the master's DataNode | all **68 files still readable** from the copies on the friends' laptops |
| Self-healing | wait | node declared dead after **~2.5 min**; 2 copies of every block restored on the remaining laptops **within 80 s** |
| Container restart | `docker compose down` / `up` | data kept (persistent volumes) |

The first worker-leaves test **failed**: GraphFrames' connected components saves a checkpoint every 2
rounds and deletes older ones, and Spark needed a deleted file to recompute the lost work. We switched
that step to the GraphX implementation, which recovers from lineage (same results; all tests pass).
Earlier simulations on one laptop gave the same picture (re-replication in 26 s).

## 7. Discussion

**Correctness.** Every analysis matches an external reference or an independent calculation, and the
results are identical on 1, 2 and 3 machines.

**Why the cluster was slower.** Graph algorithms exchange data between machines (a *shuffle*) at
almost every step. Over a phone hotspot this costs far more than the computation it saves, and one
slow task delays its whole stage. With a 1 MB dataset, adding machines only adds network cost.
A cluster pays off when the data is large and the network is fast (wired LAN or home router).

**Challenges and solutions**

| Problem | Solution |
|---|---|
| GraphFrames needs numpy, which is missing from the Spark image | Custom Docker image with pinned numpy 1.26.4 |
| PageRank ranking flipped between runs on a 2-node cycle | Run until convergence (tolerance) instead of a fixed number of iterations |
| Equal recommendation scores ranked differently between runs | Floating-point sums depend on order; scores rounded to 9 decimals |
| Containers on different PCs could not reach each other (NAT) | Services announce names; fixed ports published on every PC |
| Two remote DataNodes kept replacing each other in HDFS | One data port per PC (the NameNode identifies nodes by address + port) |
| One PC with outdated settings slowed every job | IPs are now discovered automatically at every start (registry) |
| Hotspot IPs (and even the subnet) change every session | Registry + subnet scan + firewall rule for the local subnet |
| A laptop registered under a friend's name (copied example `.env`), so two names pointed to one IP | The registry now allows one name per IP: the newest registration wins |
| `sudo` fails inside the Hadoop image on a newer Docker version (PAM error), so a DataNode kept restarting | Start scripts use sudo only when the storage folder is not yet writable; one-time `chown` as root otherwise |
| A job failed when a worker left mid-job (GraphFrames deleted a checkpoint it still needed) | Connected components via GraphX, which recomputes lost data from lineage |
| A firewall silently dropped all connections to one laptop | Fixed on that laptop (rule + blocked Docker rules); diagnosed remotely: "timed out" = firewall, "refused" = service not running |

**Limitations.** Small dataset; LPA results depend on the number of rounds; no data locality between
Spark and HDFS containers; a phone hotspot is a slow, shared network.

## 8. Testing

| Level | What | Result |
|---|---|---|
| Unit tests | 35 tests on tiny hand-drawn graphs (stats, PageRank, modularity, recommendations vs. brute force) | all pass, ~40 s |
| Smoke test | cluster, GraphFrames and HDFS read/write | pass |
| End-to-end | all 5 jobs on real data, 1, 2 and 3 laptops | pass, identical results |
| Fault tolerance | stop a Spark worker mid-job; stop a DataNode, check reads and re-replication | pass, on 3 real laptops |

## 9. Conclusion and Future Work

We built a working distributed social-network analysis system on HDFS, Spark and GraphFrames. It
gives correct results, runs unchanged from one laptop to several, and tolerates the loss of a storage
node. The main lesson: **distribution only helps when the computation per byte sent is large**. On small
data and slow Wi-Fi, the network dominates.

Future work: a faster network (router or wired LAN); larger datasets (Epinions,
LiveJournal); data locality between Spark and HDFS; Louvain communities; recommendation evaluation
(precision@K); visualization.

## References

1. J. McAuley and J. Leskovec. *Learning to Discover Social Circles in Ego Networks.* NIPS 2012.
   Dataset: https://snap.stanford.edu/data/ego-Facebook.html
2. Apache Hadoop HDFS documentation: https://hadoop.apache.org/docs/r3.3.6/
3. Apache Spark documentation: https://spark.apache.org/docs/3.5.3/
4. GraphFrames user guide: https://graphframes.github.io/graphframes/docs/_site/user-guide.html
5. L. Page, S. Brin, R. Motwani, T. Winograd. *The PageRank Citation Ranking.* Stanford, 1999.
6. U. N. Raghavan, R. Albert, S. Kumara. *Near linear time algorithm to detect community structures
   in large-scale networks.* Physical Review E, 2007.
7. L. Adamic and E. Adar. *Friends and neighbors on the Web.* Social Networks, 2003.

---

## Appendix A: How to Run

Prerequisites: Windows 10/11, Docker Desktop (WSL2), Git. Full guides: [docs/SETUP.md](docs/SETUP.md)
(one laptop), [docs/PHASE2_SETUP.md](docs/PHASE2_SETUP.md) (several laptops), [docs/DEMO.md](docs/DEMO.md)
(demo checklist). Design: [docs/PLAN.md](docs/PLAN.md).

Several laptops on one hotspot (after the one-time setup in PHASE2_SETUP.md):
```powershell
.\scripts\cluster_up.ps1        # master laptop: finds the friends, starts the cluster
.\scripts\worker_up.ps1         # each friend's laptop: finds the master, joins
.\scripts\cluster_status.ps1    # master: who is connected
```

One laptop:

```powershell
docker compose up -d --build                  # start HDFS + Spark
.\scripts\submit.ps1 jobs\00_smoke_test.py    # check the cluster
.\scripts\download_dataset.ps1                # download ego-Facebook
.\scripts\load_to_hdfs.ps1                    # copy it into HDFS
.\scripts\run_all.ps1                         # run jobs 01-05 with a timing table
.\scripts\test.ps1                            # run the 35 unit tests
.\scripts\submit.ps1 jobs\05_recommend.py --users 460   # recommendations for one user
```

## Appendix B: Repository Layout

```
docker-compose.yml          cluster (one laptop; also the master in Phase 2)
docker-compose.cluster.yml  Phase 2 add-on for the master laptop
docker-compose.worker.yml   Phase 2: a friend's laptop (Spark worker + DataNode)
docker/                     Spark image, Spark and HDFS settings, HDFS start scripts
config/sna.ini              HDFS paths and dataset formats
src/sna/                    library: config, loading, features/ (stats, influencers, communities, recommend)
jobs/                       Spark jobs 00-05
tests/                      unit tests
scripts/                    setup, run, status and firewall scripts
docs/                       plan and setup guides
```
