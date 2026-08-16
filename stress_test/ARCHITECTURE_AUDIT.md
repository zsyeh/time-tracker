# Production architecture audit (2026-08-15)

This audit was taken from the running VPS, systemd/Nginx process state, Django
settings, Vue source, ORM code, and PostgreSQL statistics. It is not inferred
from the README. Secrets, capability paths, user content, and database
credentials are intentionally omitted.

## Request path

```text
PC / browser
  ↓ Internet + TLS + Cloudflare proxy
Nginx (2 workers, HTTP/2 on the public site)
  ↓ local TCP 127.0.0.1:8000; listener backlog currently 2048
Gunicorn master
  ↓ accept/backlog + scheduling
2 synchronous Gunicorn workers
  ↓
LoadTestTimingMiddleware (inert for normal traffic)
  ↓ Security / WhiteNoise / DB Session / CSRF / Auth middleware
Django REST Framework view
  ↓ serializer + service + signals
PostgreSQL 15 over a local Unix/default connection
  ↓ response construction
Gunicorn → Nginx → Cloudflare → client
```

The MCP server is a separate Python process on port 8001 and is not part of the
browser/API request path. A systemd timer retries pending GitHub note sync every
minute.

## Measured host and process baseline

| Item | Observed value |
|---|---|
| Virtualization | KVM, Debian/Linux, x86-64 |
| CPU | 2 vCPU, Intel Xeon E5-2680 v4 class |
| RAM | 1,967 MiB total; about 897 MiB available at audit time |
| Swap | 0 MiB |
| Root filesystem | 30 GiB ext4, about 16 GiB available |
| Block device | QEMU virtual block device; rotational flag exposed as `1` |
| Gunicorn | 2 sync workers; about 79 MiB RSS each at audit time |
| MCP process | about 95 MiB RSS at audit time |
| PostgreSQL | 15.18, local, about 10 MiB logical database size |
| PostgreSQL connections | 3 total / 1 active during audit |
| PostgreSQL max connections | 20 |
| PostgreSQL extensions | `pg_stat_statements`, `plpgsql` |
| Cache | Django file-based cache under `/tmp`, 60-second dashboard entries |
| Django session | database backend; `SESSION_SAVE_EVERY_REQUEST=True` |
| Nginx status | `stub_status` is not configured |

PostgreSQL's current conservative memory settings are 128 MiB
`shared_buffers`, 2 MiB `work_mem`, and 768 MiB `effective_cache_size`. The
capacity system observes them but does not modify PostgreSQL configuration.

The virtual NIC does not expose the provider bandwidth contract through sysfs.
Set `STRESS_TEST_NETWORK_CAPACITY_MBPS` to the real VPS egress limit (for
example, 30) before using the network saturation guard.

## Static and dynamic traffic

- Nginx currently proxies `/static/` to Django/WhiteNoise instead of reading a
  filesystem directly. Assets have a one-year immutable browser cache header.
- Cloudflare fronts the public origin. A spot check returned Cloudflare as the
  server, but the tested static object was not confirmed as an edge cache hit.
  Therefore an origin capacity run must not assume static traffic is eliminated.
- Dynamic API, representative large Markdown detail, and a static asset can be
  benchmarked separately with the endpoint scenario.

## Real Vue request amplification

The SPA fetches dashboard overview and auth/bootstrap together when the private
shell loads. Today and Trends reuse the same in-memory overview. Dashboard,
statistics, subject totals, streaks, and heatmap are one origin response, not
six separate APIs.

Important real chains:

```text
Start action
  POST /api/sessions/
  GET  /api/dashboard/overview/
  GET  /api/auth/session/

Finish action
  GET  /api/completion-options/       once per mounted component when needed
  POST /api/sessions/<id>/finish/
  GET  /api/dashboard/overview/
  GET  /api/auth/session/

Session article/review
  GET  /api/sessions/<uuid>/
  GET  /api/sessions/<uuid>/share/
  POST /api/sessions/<uuid>/reviews/  automatic deduplicated review event

Public share open
  GET /share/<token>                  SPA shell
  GET /api/public/shares/<token>/     minimal anonymous article payload
```

Depending on how often a user reloads instead of navigating within the SPA,
the supplied heavy-user profile maps to approximately 107–131 origin requests
per DAU/day in the current code. The report keeps a range instead of pretending
the ambiguous logical-operation list has one exact amplification value.
The high-side 131-request model is stored as an endpoint-level breakdown in
`capacity_analysis.py`; its dashboard component falls from 55 to 31 at the
low side because Today/Trends/heatmap statistics can reuse one SPA payload.

Because database sessions are saved on every request, nearly every
authenticated origin request can also cause a `django_session` UPDATE. This
must be measured as the current baseline. A future controlled optimization
round can test `SESSION_SAVE_EVERY_REQUEST=False`, but the load-test feature
does not silently change it.

## Session finish critical path

The current finish request performs:

1. owner-scoped TimeLog lookup;
2. payload validation and optional owned-tag lookup;
3. transaction plus `SELECT ... FOR UPDATE`;
4. TimeLog update (or delete outside the 25-minute/12-hour bounds);
5. tag relation update when supplied;
6. dashboard-version invalidation in the file cache;
7. daily-stat refresh queries;
8. durable GitHub outbox creation for normal users;
9. response serialization;
10. a detached management-command spawn for GitHub sync.

The Git/GitHub network work occurs outside the request, and the minute timer is
the retry path. Process spawning remains a small synchronous part of the normal
finish response and is visible in app/CPU timing. Isolated `loadtest_*` users
skip both outbox creation and dispatch so a capacity test can never push test
Markdown to GitHub.

The synchronized finish-burst workload therefore measures the safe local
three-request browser chain (`finish → dashboard + auth refresh`) but explicitly
does not claim to benchmark GitHub subprocess/network throughput. The optional
completion-options request happens before the user writes/confirms the finish
form and is not placed inside the synchronized POST shock.

## Observability map

| Stage | Measurement | Classification / limitation |
|---|---|---|
| PC ↔ origin | total latency, bytes, status | measured; includes Internet, TLS, Cloudflare, Nginx, queue, app, and response transfer |
| Nginx upstream | connect/header/response headers | measured when the supplied Nginx snippet is installed |
| Nginx → Django | proxy-handoff timestamp to middleware entry | estimated queue/scheduling time; millisecond timestamp and clock error apply |
| Django | middleware-entry through rendered response | measured app wall time |
| DRF JSON rendering | final JSON byte encoding | measured separately; serializer model-to-Python work remains within app wall |
| Request CPU | Linux request-thread user/system CPU | measured; not mislabeled wall time |
| ORM/DB within request | SQL count, write count, cumulative SQL wall time | measured with Django `execute_wrapper`; includes auth/session SQL because instrumentation is outermost |
| Dashboard cache | hit/miss response header | measured for overview requests |
| Host | aggregate/per-core counters, user/system/iowait/steal, load, context switches, memory/swap, network, TCP | measured cumulative Linux counters; rates are derived client-side |
| Processes | Gunicorn/Nginx/PostgreSQL CPU counters and RSS | measured cumulative process groups; CPU rate is derived |
| Gunicorn workers/backlog | worker-role process count, local connections, listener receive queue | measured/approximated from procfs; exact in-handler busy percentage is not exposed |
| Nginx reading/writing/waiting | unavailable | `stub_status` is not configured; public established sockets are only an approximation |
| PostgreSQL | transactions, statements, rows, cache, connections/waits/locks, WAL, checkpoints, temp/dead tuples | measured from statistics views every few seconds; sampling has small stated overhead |
| Knee/bottleneck/safe QPS/DAU | analysis of the measured stages | derived and explicitly labeled |

## Safety boundary

- The VPS never runs the load generator and never accepts shell text.
- Only fixed probe actions exist: begin, metrics, provision isolated fixtures,
  prepare an eligible finish burst, and clean up the same run prefix.
- Real APIs keep their normal session authentication, CSRF, ownership, and
  serializer validation. The short-lived signed run token enables measurement,
  not authorization.
- Default server and PC limits are conservative. Larger ramps require an
  explicit server-side limit change.
- Normal login availability, sustained CPU, available RAM, swap growth,
  PostgreSQL waits, network contract, errors, p99, and queue growth are stop
  conditions.
- No storage benchmark exists. `/proc` and `/sys` reads are virtual counter
  reads. Nginx access logging is disabled for the high-frequency protected
  probe. Real business requests retain normal security logging.
