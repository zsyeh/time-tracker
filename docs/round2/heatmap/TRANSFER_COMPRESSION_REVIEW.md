# BUG-04 production transfer repair — independent review

Scope: root's minimal per-view `@method_decorator(gzip_page, name='dispatch')` on `DrillHeatmapView`, plus `drill/test_heatmap_transfer.py`. This review changes no backend/UI source and does not reopen query optimization.

## Why this is a separate repair

The earlier actual-PG comparison proved unchanged query count/data and no API query regression. It did **not** measure production network transfer. Subsequent production evidence supplied by root/search reviewer reports about307KB uncompressed selected-grid JSON and46–673ms body transfer, while API-response-to-DOM is23–31ms. The gzip change addresses that measured network cost; the earlier JSON/API equivalence evidence remains relevant to decoded data, not proof that the production cold-first-screen gate was already met. Final transfer bytes/latency and cold-first-screen remeasurement belong to root's production smoke evidence.

## Framework implementation checked

The installed test/release base uses Django4.2.30. Read actual installed source for `GZipMiddleware.process_response`, `make_middleware_decorator`, and `compress_string`:

- The decorator installs a post-render callback on DRF's Response; JSON is rendered before gzip accesses its bytes. It does not prematurely evaluate an unrendered response.
- Requests whose Accept-Encoding does not contain gzip retain the original body; responses below200bytes or already having Content-Encoding are skipped. Compression is retained only when it makes the body smaller.
- Content-Length is recomputed; Vary merges Accept-Encoding with existing Cookie variation. Existing authentication/session middleware and account-affinity checks remain in place. There is no new response cache or proxy cache configuration.
- Django4.2's default compressor adds random padding (up to100bytes) for HTB mitigation. This is the installed standard behavior, not a handwritten compression/security mechanism. [Official Django4.2 GZip documentation](https://docs.djangoproject.com/en/4.2/ref/middleware/#gzip-middleware).

## Permissions, state and compression sensitivity

The decorator only wraps response transfer; the same APIView authentication/permissions, workspace/collection validation and progress aggregation execute. The JSON grid contains public question identity/labels and account-specific progress, but excludes prompt/answer contents, Notes, environment defaults, session/CSRF/share tokens. Arbitrary search text is not reflected by this endpoint. Root's4 tests verify that decoding returns the **exact original JSON bytes**, which includes all statistics/status fields.

One accuracy qualification was sent to root: the endpoint still permits DRF BrowsableAPIRenderer for explicit Accept:text/html requests, whose standard template can include a masked CSRF token. Root corrected that initial source comment to describe transport-level grid compression without claiming every representation is token-free. Standard Django random padding and CSRF masking still apply; this is not a reason to change renderer/API functionality or introduce a custom compressor. Do not expand this targeted repair into blanket compression of private Notes or token-bearing pages.

## Independently executed tests

`python manage.py test drill.test_heatmap_transfer --noinput` in an isolated ephemeral SQLite test DB passed **4/4** (0.392s); log `/home/eh/round2-independent-gzip-tests.log`.

Coverage inspected and executed:

1. Drill and EI: negotiated gzip, decompressed bytes equal plain bytes, smaller payload, exact Content-Length, Vary includes Accept-Encoding and Cookie, valid question count, private prompt absent.
2. No Accept-Encoding negotiation: original uncompressed body and attempted statistic remain available.
3. Other account sees its own zero progress; illegal EI selected collection still404; wrong expected account still409.
4. Anonymous gzip request still401/403.

No P1 found in this minimal transfer repair. The tests intentionally do not claim a final production timing, physical Safari result, all HTTP negotiation edge cases, or cache behavior beyond the checked Vary/length headers. Root must retain actual post-deployment compressed response bytes and complete heatmap cold-screen measurements before closing BUG-04.
