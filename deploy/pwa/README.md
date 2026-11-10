# One iPad Home Screen app for Timer, Drill and EI

Install from **https://47.95.10.128/**. The shared HTTPS origin already routes:

| Service | Path | Upstream |
| --- | --- | --- |
| Timer | `/` and `/today` | Django/Gunicorn `127.0.0.1:18000`, with Timer Host |
| Drill | `/drill/practice` | Same upstream, `/drill` stripped, Drill Host |
| EI | `/ei/practice` | Same upstream, `/ei` stripped, EI Host |

Both frontends use Vue 3 + Vite; Drill and EI share a build with a runtime path prefix. The three public subdomains remain separate origins. The existing sidebar links already point to the common IP origin in the same window. Service links in the standalone menu also point there. Share links retain their public domains; external links and the existing domain Passkey handoff can leave the PWA scope. No global link interception or authentication rewrite is introduced.

`/` is the existing Timer landing page; unauthenticated visits follow the existing login flow. No new entry page is needed. All paths under the IP origin share manifest id `/` and scope `/`. Do not install three domain shortcuts to get the unified app.

## Deployment

1. Back up the web service drop-in and retain the current image. Build both `npm run build` and `npm run build:drill`; run frontend tests. Package the application image normally. Django changes are HTML includes only; no migration or API change.
2. Copy `deploy/pwa` and `deploy/ha/{install-pwa.sh,nginx-pwa.conf}` to the origin, keeping their directory layout. Run `sudo bash deploy/ha/install-pwa.sh`. The script backs up the **actual** live Nginx config, snippet and any previous assets, adds only a shared include, runs `nginx -t`, and reloads with rollback on failure. It does not install the repository proxy template over the live config. Use a fresh `PWA_BACKUP_DIR` if specifying one.
3. Deploy the application image, checking health and retaining normal rollback. No database migration, extra port, firewall or RainYun configuration change. Domain requests for PWA static assets continue through RainYun's existing proxy to 47.
4. Check the manifest, image dimensions/MIME, three authenticated HTML pages, same session before/after, static asset hashes, business GET APIs, and `nginx -t`.

The manifest and navigation script use HTTP revalidation (`no-cache`), with no Service Worker or offline cache. No notes, questions, cookies or API responses enter a new cache. The 180px icon reuses the existing Timer artwork; 192/512px variants derive from that asset. Manifest theme/background are white; existing application themes are unchanged. The navigation menu reads existing theme variables and English/Chinese language selection.

The public PWA static locations are also provided on existing domain vhosts so the shared HTML head has no broken references. An installation made on a domain is still a different origin; install from the IP for a single shared app.

## iPad manual acceptance

1. Close the old Home Screen shortcut. Long press its icon and choose Remove/Delete Bookmark (wording varies). This does not delete server learning data; deleting an installed app may remove its local browser storage, so save any unsaved draft first.
2. In Safari open `https://47.95.10.128/`, verify there is no certificate warning, sign in normally, then Share → Add to Home Screen. If shown, enable **Open as Web App**. Name it `eh` or `Study` and Add.
3. Launch the **new icon**, not a Safari bookmark. Verify Safari address/tool bars are hidden. Use the bottom-left small menu to refresh, go back/home, and switch Timer → Drill → EI → Timer. Confirm the URL stays on the IP origin and the app stays standalone. Normal Safari should not show this menu.
4. Check portrait/landscape scrolling, touch/zoom, keyboard/drafts, existing in-page question reader, refreshing a deep question URL, and login/Passkey flow. Native iPadOS controls and external/domain authentication may still show OS browser UI; this cannot be guaranteed by desktop tests.

Automated Chromium display-mode/iOS-standalone emulation verifies our DOM and navigation, not the actual iPadOS Home Screen installation or Safari window behavior. Certificate trust and expiry must be checked at deployment time; the existing certificate renewal mechanism is unchanged.

## Repeatable navigation check

After building both frontends, run `python3 deploy/pwa/test_navigation.py` in a Python environment with Playwright and Chromium installed. Set `PWA_TEST_OUTPUT` to retain results/screenshots in a chosen directory and `PWA_TEST_PORT` to override the local fixture port. The test intercepts every request to the IP origin with local static fixtures and does not access or write production learning data. Standalone detection is simulated; this does not replace the iPad manual checks above.
