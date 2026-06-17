# Leadsgen

FastAPI service for enriching newly observed `.nl` domains into structured Aresis B2B lead profiles.

## Run

```bash
pip install -e ".[test]"
uvicorn app.main:app --reload --port 8000
```

## API

Swagger UI is available at:

- `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

```bash
curl -X POST http://127.0.0.1:8000/enrich-domain \
  -H 'content-type: application/json' \
  -d '{"domain":"example.nl","first_seen_at":"2026-06-17T12:00:00Z","source":"feed"}'
```

## KvK

Set `KVK_API_KEY` to enable live KvK enrichment. Without it, the API still returns valid JSON and records KvK enrichment as skipped.

Optional environment variables:

- `KVK_API_BASE_URL`
- `HTTP_TIMEOUT_SECONDS`
- `USER_AGENT`
- `MAX_PAGES_PER_DOMAIN`

## Registered Domain TXT

### Domains Monitor API

Put your API token in `.env`:

```env
DOMAINS_MONITOR_API_TOKEN=your-token-here
```

Then download yesterday's newly registered `.nl` domains:

```bash
python scripts/download_domains_monitor_nl_domains.py
```

Or download a specific date:

```bash
python scripts/download_domains_monitor_nl_domains.py \
  --date 2026-06-16 \
  --output data/domains_registered_2026-06-16.txt
```

The script uses Domains Monitor's historical daily endpoint for the requested date. It filters the returned feed down to `.nl` domains and writes one domain per line. Use `--allow-current-fallback` only for diagnostics; the current global daily feed is not a reliable substitute for a specific date.

With a Standard account, the reliable `.nl` path is full snapshot diffing:

```bash
python scripts/snapshot_domains_monitor_nl.py
```

This writes `data/snapshots/nl_domains_<date>.txt`. On the next run, it compares against the previous snapshot and writes new domains to `data/domains_registered_<date>.txt`.

For deployment, use SQLite-backed snapshots instead of full text baselines:

```bash
python scripts/run_domains_monitor_snapshot.py
```

This stores snapshots in `SNAPSHOT_DATABASE_PATH` and exports daily additions into `SNAPSHOT_OUTPUT_DIR`.

## Docker

```bash
docker compose up --build
```

The API listens on port `8000`. The scheduled snapshot job should run:

```bash
python scripts/run_domains_monitor_snapshot.py
```

### Generic Feed Import

SIDN does not expose a public complete same-day `.nl` registration list in this project. Use an authorized registrar/provider/internal feed export as input:

```bash
python scripts/build_registered_domains_txt.py \
  --input path/to/feed.csv \
  --date 2026-06-17 \
  --source registrar-feed \
  --output data/domains_registered_2026-06-17.txt
```

The input can be newline text or CSV. The script extracts `.nl` domains, strips protocols and `www.`, dedupes, sorts, and writes one domain per line.

For a public but incomplete fallback, collect `.nl` domains newly observed in Certificate Transparency:

```bash
python scripts/fetch_ct_observed_nl_domains.py \
  --date 2026-06-17 \
  --output data/ct_observed_nl_domains_2026-06-17.txt
```

Certificate Transparency output is not equivalent to all newly registered domains. It only includes domains for which certificates were logged.

### DomainMetaData

DomainMetaData publishes `.nl` ZIP downloads, but access is gated behind signup/login. After logging in, pass the authenticated cookie to download the daily file:

```bash
DOMAINMETADATA_COOKIE='your-session-cookie' \
python scripts/download_domainmetadata_nl_domains.py \
  --date 2026-06-17 \
  --output data/domains_registered_2026-06-17.txt
```

The default URL is `https://domainmetadata.com/download/nl/nl-domains-<date>.zip`.

For scheduled runs, omit `--date`; the downloader defaults to yesterday's daily new-domain file:

```bash
DOMAINMETADATA_COOKIE='your-session-cookie' \
python scripts/download_domainmetadata_nl_domains.py
```

DomainMetaData's FAQ says they do not currently offer API access; they offer SFTP for automated data syncing.
