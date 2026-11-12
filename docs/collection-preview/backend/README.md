# Collection preview: backend and long-link review evidence

## URL budget

[url-budget.mjs](url-budget.mjs) uses the installed Vue Router serializer and Python/Django-equivalent authentication quoting. It has no network access and no authentication secrets. Its synthetic 120-character Chinese query matches `drill/search/query.py`'s limit. Numeric document/topic IDs test encoding size, not nonempty search results.

**Correction:** the review initially demonstrated a 180-character query failing Gunicorn's former 4094-byte request-line limit. A 180-character query exceeds the actual search API limit and is not a valid user search. That example is superseded by the valid 120-character calculations below; it is not an acceptance test.

Run from repository root with the existing local dependency mount:

```sh
docker run --rm --network none \
  -v "$PWD:/work" \
  -v /home/eh/ui-rebuild-node-modules:/work/frontend/node_modules \
  -w /work node:22 \
  node docs/collection-preview/backend/url-budget.mjs \
  > docs/collection-preview/backend/url-budget.json
```

[Recorded output](url-budget.json):

| Case | IP preview URL | Auth start | Accounts login | Longest HTTP/1.1 request line | 8190-byte remainder |
|---|---:|---:|---:|---:|---:|
| 120 Chinese characters | 3128 | 4684 | 6242 | 6255 | 1935 |
| Current UI filters + 120 characters | 3732 | 5480 | 7230 | 7243 | 947 |
| Additional recognized scope keys, size stress only | 4162 | 6054 | 7948 | 7961 | 229 |

The scope stress case does not claim all those controls coexist in a single collection. The main UI-filter case uses valid control values (`short_answer`, `overconfident`, etc.). Earlier provisional arithmetic used different sample labels, hence the small numerical difference; this script/JSON is the reproducible final calculation.

The URI includes the original list URL in `returnTo`. `drill_spa_view` encodes the resulting path into `/drill-auth/start?next=...&site=drill`; `login_required` encodes that into `/accounts/login/?next=...`. For IP Passkey login, `/ip-auth/start?next=/drill/preview...` similarly nests inside accounts login. The IP prefix and HTTP method/version bytes are counted. The authentication origin is `timer.ehzsy.site`; the IP callback returns to `47.95.10.128`. Nginx prefixes and host rewrites do not eliminate these encoded query lengths.

These cases fit the new finite `gunicorn.conf.py` / production CMD limit of **8190 bytes**. This is not a proof that every arbitrary 8192-character context JSON or 16384-character Handoff model value is transportable. The Handoff database field limit is separate from the HTTP budget. End-to-end production redirects remain a separate owner-run acceptance check.

## Effective Nginx configuration: independent read-only audit

[Sanitized observation](nginx-readonly-audit.json) records the inspected filenames, SHA256 values and defaults. Full `nginx -T` dumps were deliberately not copied into Git: they include unrelated services and potentially sensitive configuration.

Both hosts passed `nginx -T`; both have a 4096-byte memory page. Neither effective dump had an explicit `proxy_buffer_size`, `proxy_buffers`, `proxy_busy_buffers_size`, `large_client_header_buffers`, or `client_header_buffer_size` override for the learning application.

Nginx's upstream response-header buffer defaults to one memory page, thus **4KB here**; response headers exceeding that buffer are invalid. A first authentication `Location` alone reaches 5504 bytes in the UI-filter case, before other headers. [Nginx proxy buffer documentation](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_buffer_size).

The default large request-header buffers are `4 8k`, with a request line required to fit one buffer. This already accommodates the measured 8190-byte Gunicorn budget; increasing it is unnecessary for these cases. [Nginx request buffer documentation](https://nginx.org/en/docs/http/ngx_http_core_module.html#large_client_header_buffers).

### Exact owner-applied changes recommended

```nginx
proxy_buffer_size 16k;
proxy_buffers 8 16k;
proxy_busy_buffers_size 32k;
```

Apply these as a bounded response-buffer set, not unlimited headers or bodies. Keep request/body/timeouts, TLS verification, cookies, authentication and cache policy unchanged. This sets at most 16KB initial plus eight 16KB response buffers per active proxied connection, allocated as needed; it is a modest but explicit increase from defaults.

| Host | Actual file / scope | Repository mapping |
|---|---|---|
| 47 | `/etc/nginx/time-tracker-ha/proxy-promoted-common.conf`, included by the learning proxy locations in `/etc/nginx/conf.d/time-tracker-ha.conf` | `deploy/ha/proxy-promoted-common.conf` |
| 98 | `/etc/nginx/conf.d/ehzsy.site.conf`, **only** the `timer.ehzsy.site`, `drill.ehzsy.site`, `ei.ehzsy.site` server blocks | `deploy/ha/nginx-rainyun-edge.conf` contains the related application template; it is **not** a complete safe replacement of the multi-site live file |

Do not overwrite the whole 98 multi-site file using the narrower repository template. Do not modify the FRP endpoint or other applications. Existing Nginx share-cache/tunnel and IP Passkey callback rules stay intact.

### Owner acceptance and rollback gates

1. Save exact live config files and hashes before editing, including 98's full multi-site file and 47's shared include. Save new-file presence/absence if using a separate snippet.
2. Apply only these scopes; run `nginx -t` on each host. On validation failure restore the saved files before any reload.
3. Verify the new immutable application reports `limit_request_line=8190`; include the config or explicit CLI option in the actual production command, not just a developer-only invocation.
4. Reload only after validation. Check ordinary `/accounts/login/`, Drill, EI, public share/static routes and existing IP callback behavior.
5. With the synthetic 120-character query, verify authenticated preview refresh and anonymous preview → auth start → accounts login → authenticated return. Record each status, response Location length and final preserved context; do not store session cookies, capabilities or passkey material in evidence.
6. Cover both IP prefixes and 98-backed domains. Confirm no `upstream sent too big header`, 400 request-line or 414 failures. A numeric calculation alone is not this test.
7. On regression, restore saved Nginx config, `nginx -t`, reload, and roll back the application image/queue/PWA using the owner's release runbook. Retain migration0040's compatible widened column; do not reverse-shrink it or restore old learning data.

The reviewer performed **no server configuration modification, reload, login, deployment or database mutation** during this audit.
