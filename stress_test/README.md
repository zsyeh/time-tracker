# Capacity testing / 容量压测

This folder runs a repeatable production-capacity test from your PC. The VPS
only exposes a fixed, key-protected control/metrics endpoint. Real application
load still goes through Nginx, Gunicorn, Django authentication/CSRF/ownership,
the ORM, cache, and PostgreSQL.

本目录用于在 PC 上运行可重复的生产容量测试。VPS 只提供固定的密钥保护端点；真实负载仍经过 Nginx、Gunicorn、Django 认证/CSRF/数据权限、ORM、缓存和 PostgreSQL。

Read the code-derived and VPS-measured baseline first:
[架构审计](ARCHITECTURE_AUDIT.md).

## Safety model / 安全边界

- The load generator never runs on the VPS.
- No endpoint accepts shell commands, SQL, file paths, or arbitrary target URLs.
- The long-lived key is sent in `Authorization`, never in a URI or report.
- A signed short-lived run token enables timing only; it does not bypass normal
  application authentication or ownership checks.
- Real workload data belongs only to `loadtest_<run>_*` users. The default run
  deletes those users, their records, public test share, and auth sessions.
- Load-test users never create GitHub outbox entries or launch GitHub sync.
- Normal login availability is checked throughout the run.
- Sustained CPU, low memory, swap growth, database waits, configured network
  saturation, errors, p99, or queue growth stop further ramping.
- No storage benchmark is implemented. The probe reads virtual `/proc`/`/sys`
  counters; PostgreSQL statistics are sampled at a lower frequency.

压测器不在 VPS 上运行，不接受 shell/SQL/文件路径/任意 URL。测试数据只属于 `loadtest_*` 隔离账号，默认自动清理；不会提交到 GitHub。测试过程中会监测正常登录页并在系统失稳前停止。

## 1. Configure the VPS / 配置 VPS

Generate a 32-byte random key:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add this to the private server `.env` and restart Django. Real keys must never
be committed:

```dotenv
STRESS_TEST_ENABLED=true
STRESS_TEST_KEY=paste-the-generated-key

# Conservative per-Gunicorn-worker safety cap.
STRESS_TEST_MAX_RPS=20
STRESS_TEST_MAX_BODY_BYTES=4096

# Required for real authenticated workloads. Keep false outside planned tests.
STRESS_TEST_ALLOW_DATA_SETUP=true
STRESS_TEST_MAX_USERS=60
STRESS_TEST_MAX_HISTORY_ROWS=20000
STRESS_TEST_RUN_TTL_SECONDS=7200

# Set this to the provider contract when a virtual NIC reports no link speed.
STRESS_TEST_NETWORK_INTERFACE=ens18
STRESS_TEST_NETWORK_CAPACITY_MBPS=30
STRESS_TEST_GUNICORN_PORT=8000
```

Install the exact probe location and timing headers from
[`deploy/nginx/learning-os.conf.example`](../deploy/nginx/learning-os.conf.example),
then validate and reload Nginx. Probe access logging is disabled so the
high-frequency telemetry request cannot become a log-write benchmark.

服务端默认关闭。只在计划压测时打开隔离数据开关，并设置真实网络带宽上限；否则无法判断 30 Mbps 上行是否饱和。

Dedicated URI / 专用 URI:

```text
https://YOUR-DOMAIN/api/stress-test/probe/
```

## 2. Configure the PC / 配置 PC

```bash
git clone https://github.com/zsyeh/time-tracker.git
cd time-tracker/stress_test
cp stress-test.example.env stress-test.env
```

Windows PowerShell:

```powershell
Copy-Item stress-test.example.env stress-test.env
```

Only two PC values are required:

```dotenv
TARGET_URL=https://YOUR-DOMAIN
LOAD_TEST_KEY=the-same-server-key
```

`TARGET_URL` may also be the full dedicated probe URL. The client uses only the
Python 3 standard library. `stress-test.env`, credentials, run tokens, reports,
and result directories are excluded from Git and Docker build context.

PC 端只需填域名和同一密钥，无需安装第三方 Python 包。

## 3. Preflight / 压测前检查

```bash
python3 capacity.py --check
```

or:

```bash
bash run.sh --check
```

This validates TLS, URI, key, server limits, CPU/RAM/network/process counters,
PostgreSQL statistics support, and fixture policy. The printed run token is
redacted. It does not create users or start load.

## 4. Automatic mixed ramp / 自动混合 ramp

```bash
bash run.sh
```

The default is deliberately small: 60 isolated users, 30 seconds per stage,
and `1,5,10,20` offered QPS. Requests use deterministic aggregate Poisson
arrivals, representing independent users with think time instead of a
closed-loop client that hammers APIs with zero pause.

The mixed navigation workload is 90% reads and 10% deduplicated review writes
by operation, using weights derived from the current API/request amplification
audit. Because
the current site has `SESSION_SAVE_EVERY_REQUEST=True`, the measured SQL write
ratio can be much higher; that is an observed amplification, not a client bug.

To try a larger progression, first raise the server cap deliberately, then set:

```dotenv
RAMP_STEPS=1,5,10,20,50,100,200,500,1000
```

The runner stops adding stages after error rate, p99, CPU, RAM, swap, database,
network, queue, throughput-flattening, or normal-page guards trigger. Never use
the full list as the first production run.

Each virtual user has at most one in-flight request. If the PC exhausts all
available users, the missed offered arrival is recorded as
`client_vu_busy`—never silently omitted or misattributed to VPS capacity. Raise
PC `USER_COUNT`/`CONCURRENCY` and repeat before drawing a server conclusion.

## 5. Single endpoints / 单接口基准

```bash
python3 capacity.py --scenario endpoint --endpoint dashboard --label dashboard-baseline
python3 capacity.py --scenario endpoint --endpoint history --label history-baseline
python3 capacity.py --scenario endpoint --endpoint markdown --label markdown-large-body
python3 capacity.py --scenario endpoint --endpoint static_asset --label origin-static
python3 capacity.py --scenario endpoint --endpoint session_update --label write-update
```

Supported endpoint names:

```text
auth_bootstrap  dashboard      active_session  statistics
heatmap         session_start  history         session_detail
review_get      review_post    search          issues
markdown        share_status   share_create    public_share
session_update  static_asset
```

`active_session`, `statistics`, and `heatmap` intentionally map to the current
consolidated dashboard API. They are labels for business intent, not invented
extra endpoints. `session_start`, `review_post`, and `share_create` are
single-use writes per isolated user, so `USER_COUNT` must cover every planned
request. Use the finish-burst scenario for `session_finish`.

## 6. Cache hot/cold / 缓存热冷对比

```bash
python3 capacity.py --scenario cache-hot --label file-cache-hot
python3 capacity.py --scenario cache-cold --label file-cache-cold
python3 capacity.py --scenario cache-cold --endpoint history --label history-db-read
```

Hot mode supports the consolidated `dashboard`/`statistics`/`heatmap` labels
and warms each isolated overview key. Cold overview mode uses each isolated
user exactly once; if there are not enough fresh users, it truncates the ramp
instead of silently turning later requests into cache hits. Raise `USER_COUNT`
deliberately to measure more cold stages. Cold mode also supports `history` as
an uncached DB-read control, which can safely reuse users.
It never clears the shared cache because that would affect normal users.

For a Redis experiment, prepare a separate deployment/configuration, install
`requirements-loadtest-redis.txt`, and set `DJANGO_CACHE_BACKEND=redis` plus
`REDIS_CACHE_URL`. Keep the same seed/ramp/users and label the runs
`redis-hot`/`redis-cold`. The default requirements and configuration remain file
cache; the runner does not install a Redis server or assume it is faster.
Reported cache hit ratio, DB queries/request, CPU/request, QPS, and p99 provide
the evidence.

For the required no-application-cache control, use
`DJANGO_CACHE_BACKEND=dummy` in an otherwise identical temporary deployment.
The supported experiment matrix is therefore `dummy` (no application cache),
`file` (current default), and `redis`; do not compare runs that change more than
the cache backend.

## 7. 22:00 finish burst / 22:00 结算洪峰

```bash
python3 capacity.py --scenario finish-burst --label finish-burst
```

The configured model covers 40–60% of DAU finishing in 10 minutes, 2 minutes,
and 30 seconds. The default 60 users measure the first 100-DAU step at the
default 60% finish fraction. Every measured finish uses one eligible two-hour
running Session and one isolated authenticated user. Each event executes the
code-audited `POST finish → GET dashboard overview → GET auth/session` chain.
Events are distributed across the business window instead of jumping from zero
to all users at one instant.

If a configured DAU step needs more isolated users than the server allowed, it
is recorded as `derived-only`; it is never falsely called measured. Increase
`USER_COUNT` and the server-side maximum in a later deliberate run only after a
smaller stage is safe.

10/2-minute business windows take 10/2 real minutes. This is intentional for a
time-synchronized capacity model.

## 8. Results / 报告

```text
load-test-results/<timestamp>-<label>/
├── raw/
│   ├── requests.csv
│   ├── server-metrics.csv
│   └── db-metrics.csv
├── charts/
│   ├── qps-vs-p99-queue.svg
│   └── ...
├── report.md
├── report.json
└── summary.txt
```

Reports include successful QPS, error rate, p50/p90/p95/p99/p99.9/max,
Nginx/Gunicorn queue estimate, app wall, request user/system CPU, DB time and
queries/writes, cache result, host/per-process resources, origin Mbps,
PostgreSQL counters, automatic knee, evidence-based first bottleneck, safe QPS,
and normal/10-minute/2-minute/30-second DAU models.

Do not pretend that one workload proves both normal and synchronized capacity.
After one mixed ramp and one finish-burst run with the same seed/machine/cache,
combine their measured budgets:

```bash
python3 combine.py \
  load-test-results/<normal-ramp> \
  load-test-results/<finish-burst> \
  --output load-test-capacity-plan
```

The combined plan uses normal DAU from the mixed workload and 10-minute /
2-minute / 30-second DAU from the finish workload, then takes their minimum. It
refuses a finish report that contains only derived (unmeasured) stages.

Every metric is labeled as:

- **measured**: direct timing/counter;
- **estimated**: currently the Nginx handoff-to-Django queue approximation;
- **derived**: rates, knee, bottleneck, headroom, QPS, and DAU model.

## 9. Baseline → optimization rounds

Run the identical seed/workload after changing only one bottleneck:

```bash
python3 capacity.py --label baseline
python3 capacity.py --label optimization-round-1
python3 capacity.py --label optimization-round-2

python3 compare.py \
  load-test-results/<baseline> \
  load-test-results/<round-1> \
  load-test-results/<round-2> \
  --output load-test-comparison
```

The comparator rejects reports whose seed, scenario, ramp, duration, or
endpoint mix differs. Its before/after table covers QPS, p50/p95/p99/p99.9,
queue, CPU/request, DB queries/p99, cache, network, RAM, errors, DAU, and the new
first bottleneck.

## 10. Cleanup and disable / 清理与关闭

Automatic cleanup is the default. If the PC loses power, use the run ID printed
in the report/terminal:

```bash
python3 capacity.py --cleanup-run run-xxxxxxxx
```

This command can only delete users whose exact prefix belongs to that run. It
cannot target normal usernames. Recovery cleanup remains available after
`STRESS_TEST_ALLOW_DATA_SETUP=false` (while the protected probe/key itself is
still enabled), so disable data creation first, clean an interrupted run, then
disable the probe.

After testing, set:

```dotenv
STRESS_TEST_ENABLED=false
STRESS_TEST_ALLOW_DATA_SETUP=false
```

Restart Django and optionally rotate/remove `STRESS_TEST_KEY`.
