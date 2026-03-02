# SortIQ REST API

SortIQ ships a full REST API built on **FastAPI**. It gives you every capability of the GUI in a scriptable, automatable form — perfect for NAS setups, home media servers, CI pipelines, and unattended batch renaming.

**Swagger UI (interactive):** `http://localhost:8060/docs`
**ReDoc (readable):** `http://localhost:8060/redoc`
**OpenAPI JSON:** `http://localhost:8060/openapi.json`

---

## Quick start

```bash
# Start the container (GUI + API)
docker run -p 6080:6080 -p 8060:8060 \
  -e TMDB_API_KEY=your_key \
  -v ~/Media:/media \
  ghcr.io/loukaniko/sortiq

# Check health
curl http://localhost:8060/api/v1/health

# Set keys at runtime (no restart required)
curl -X PATCH http://localhost:8060/api/v1/settings \
  -H "Content-Type: application/json" \
  -d '{"tmdb_api_key": "your_key"}'
```

---

## Endpoints

All endpoints are prefixed with `/api/v1`.

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check — API key status, mediainfo availability |
| GET | `/naming-tokens` | Reference for all `{token}` placeholders |

### Media operations

| Method | Path | Description |
|--------|------|-------------|
| POST | `/media/scan` | Scan a directory for media files |
| POST | `/media/parse` | Parse a filename into structured metadata (no API calls) |
| POST | `/media/search` | Search TMDB for movies or TV shows |
| POST | `/media/match` | Match files against TMDB/TVDB — returns proposed names |
| POST | `/media/rename` | Match **and** rename files in one synchronous call |
| POST | `/media/auto-rename` | Scan directory + match + rename in one call |
| POST | `/media/stats` | Library statistics: file count, size, breakdown by extension and resolution |
| POST | `/media/checksum` | Compute MD5/SHA1/SHA256 checksums with optional sidecar files |

### Batch jobs (async)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/jobs` | Submit a batch rename job (returns immediately with `job_id`) |
| GET | `/jobs` | List all jobs |
| GET | `/jobs/{job_id}` | Get job detail, progress, per-file results, and log |
| POST | `/jobs/{job_id}/cancel` | Cancel a running job |
| DELETE | `/jobs/{job_id}` | Remove a job record |

### Watch folders

| Method | Path | Description |
|--------|------|-------------|
| POST | `/watchers` | Create a watch folder (auto-rename new media files) |
| GET | `/watchers` | List all configured watch folders |
| GET | `/watchers/{watcher_id}` | Get watch folder status and statistics |
| POST | `/watchers/{watcher_id}/start` | Start or resume a paused/stopped watcher |
| POST | `/watchers/{watcher_id}/pause` | Pause a watcher (keeps seen-file history) |
| POST | `/watchers/{watcher_id}/stop` | Stop a watcher |
| DELETE | `/watchers/{watcher_id}` | Stop and remove a watch folder |

### Presets

| Method | Path | Description |
|--------|------|-------------|
| GET | `/presets` | List all naming scheme presets (built-in + user) |
| POST | `/presets` | Create or update a preset |
| DELETE | `/presets/{name}` | Delete a user preset (built-in presets cannot be deleted) |

### History

| Method | Path | Description |
|--------|------|-------------|
| GET | `/history` | Get rename history with undo/redo availability |
| POST | `/history/undo` | Undo the most recent rename |
| POST | `/history/redo` | Redo a previously undone rename |
| DELETE | `/history` | Clear all rename history |

### Settings

| Method | Path | Description |
|--------|------|-------------|
| GET | `/settings` | Read current settings (key values never returned — only set/not-set status) |
| PATCH | `/settings` | Update settings — partial update, only provided fields changed |
| POST | `/settings/keys` | Convenience alias for `PATCH /settings` |

---

## Naming scheme tokens

| Token | Description | Example output |
|-------|-------------|----------------|
| `{n}` | Title (movie or show name) | `Breaking Bad` |
| `{y}` | Year | `2008` |
| `{t}` | Episode title (multi-episode: joined with ` + `) | `Pilot + Cat's in the Bag` |
| `{s}` | Season number | `S01` |
| `{e}` | Episode number or range | `E01` or `E01-E03` |
| `{s00e00}` | Season + episode combined | `S01E01` or `S01E01-E03` |
| `{vf}` | Video resolution | `1080p`, `720p`, `4K` |
| `{vc}` | Video codec | `x264`, `x265`, `HEVC` |
| `{af}` | Audio codec | `AAC`, `AC3`, `DTS` |
| `{ac}` | Audio channels | `5.1`, `2.0` |

### Built-in preset schemes

| Preset | Scheme |
|--------|--------|
| Plex - Movie | `{n} ({y})` |
| Plex - Movie (folder) | `{n} ({y})/{n} ({y})` |
| Plex - TV | `{n}/Season {s}/{n} - {s00e00} - {t}` |
| Kodi - Movie | `{n} ({y})/{n} ({y})` |
| Kodi - TV | `{n}/Season {s}/{n} S{s00e00}` |
| Jellyfin - Movie | `{n} ({y})` |
| Jellyfin - TV | `{n}/Season {s}/{s00e00} - {t}` |
| FileBot Style | `{n}.{y}.{vf}.{vc}.{af}` |
| Anime - Simple | `[{n}] {s00e00} - {t}` |

---

## Workflow examples

### 1 — Preview renames before committing

```bash
curl -s -X POST http://localhost:8060/api/v1/media/rename \
  -H "Content-Type: application/json" \
  -d '{
    "files": ["/media/Downloads/Inception.2010.BluRay.1080p.mkv"],
    "naming_scheme": "{n} ({y})",
    "dry_run": true
  }' | python3 -m json.tool
```

### 2 — Batch rename a whole folder (synchronous)

```bash
curl -s -X POST http://localhost:8060/api/v1/media/rename \
  -H "Content-Type: application/json" \
  -d '{
    "files": ["/media/Downloads/Movies/"],
    "naming_scheme": "{n} ({y})",
    "output_dir": "/media/Movies",
    "operation": "move",
    "download_artwork": true,
    "write_metadata": true
  }'
```

### 3 — Auto-rename a directory in one call

```bash
curl -s -X POST http://localhost:8060/api/v1/media/auto-rename \
  -H "Content-Type: application/json" \
  -d '{
    "directory": "/media/Downloads/TV",
    "naming_scheme": "{n}/Season {s}/{n} - {s00e00} - {t}",
    "output_dir": "/media/TV",
    "operation": "move",
    "dry_run": true
  }' | python3 -m json.tool
```

### 4 — Submit async batch job and poll for progress

```bash
# Submit
JOB=$(curl -s -X POST http://localhost:8060/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "files": ["/media/Downloads/TV/"],
    "naming_scheme": "{n}/Season {s}/{n} - {s00e00} - {t}",
    "output_dir": "/media/TV",
    "operation": "move",
    "data_source": "TheMovieDB"
  }')

JOB_ID=$(echo $JOB | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
echo "Job ID: $JOB_ID"

# Poll
while true; do
  STATUS=$(curl -s "http://localhost:8060/api/v1/jobs/$JOB_ID" | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'], d['progress']['percent'],'%')")
  echo $STATUS
  echo "$STATUS" | grep -qE "completed|failed|cancelled" && break
  sleep 2
done
```

### 5 — Submit job with webhook callback

```bash
curl -X POST http://localhost:8060/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "files": ["/media/Downloads/"],
    "naming_scheme": "{n} ({y})",
    "output_dir": "/media/Movies",
    "webhook_url": "https://your-server.com/hooks/sortiq"
  }'
```

The webhook receives a `POST` with the full job summary JSON on completion (or failure).

### 6 — Create a watch folder

```bash
curl -X POST http://localhost:8060/api/v1/watchers \
  -H "Content-Type: application/json" \
  -d '{
    "directory": "/media/Downloads",
    "naming_scheme": "{n} ({y})",
    "output_dir": "/media/Movies",
    "operation": "move",
    "poll_interval_secs": 60,
    "auto_start": true
  }'
```

The watcher scans every `poll_interval_secs` seconds, skipping files still being downloaded (`.part`, `.crdownload`, etc.). New files are matched and renamed automatically; results appear in `GET /jobs`.

### 7 — Generate checksums for verification

```bash
curl -X POST http://localhost:8060/api/v1/media/checksum \
  -H "Content-Type: application/json" \
  -d '{
    "files": ["/media/Movies/Inception (2010)/Inception (2010).mkv"],
    "algorithm": "sha256",
    "save_sfv": true
  }'
```

### 8 — Library statistics

```bash
curl -X POST http://localhost:8060/api/v1/media/stats \
  -H "Content-Type: application/json" \
  -d '{"directory": "/media/Movies", "recursive": true}'
```

Returns total file count, total size in MB, and breakdowns by extension and resolution.

### 9 — Search for a title manually

```bash
curl -X POST http://localhost:8060/api/v1/media/search \
  -H "Content-Type: application/json" \
  -d '{"query": "The Dark Knight", "year": 2008, "type": "movie"}'
```

### 10 — Undo the last rename

```bash
curl -X POST http://localhost:8060/api/v1/history/undo
```

### 11 — Update settings at runtime

```bash
curl -X PATCH http://localhost:8060/api/v1/settings \
  -H "Content-Type: application/json" \
  -d '{
    "tmdb_api_key": "your_tmdb_key",
    "sonarr_url": "http://localhost:8989",
    "sonarr_key": "your_sonarr_key",
    "default_naming_scheme": "{n} ({y})"
  }'
```

Keys are persisted to `~/.sortiq/settings.json` and injected into the running process immediately — no restart required.

---

## Automation examples

### cron job — rename new downloads nightly

```bash
# /etc/cron.d/sortiq
0 2 * * * curl -s -X POST http://localhost:8060/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{"files":["/media/Downloads/"],"naming_scheme":"{n} ({y})","output_dir":"/media/Movies","operation":"move"}' \
  >> /var/log/sortiq.log 2>&1
```

### Python client

```python
import requests

BASE = "http://localhost:8060/api/v1"

def rename_folder(path: str, scheme: str = "{n} ({y})", dry_run: bool = True):
    r = requests.post(f"{BASE}/media/rename", json={
        "files": [path],
        "naming_scheme": scheme,
        "dry_run": dry_run,
    })
    r.raise_for_status()
    data = r.json()
    for result in data["results"]:
        status = "✓" if result["success"] else "✗"
        print(f"{status} {result['original']} → {result.get('destination','(no match)')}")
    print(f"\nRenamed: {data['renamed_count']}/{data['total']}")

rename_folder("/media/Downloads/Movies/", dry_run=True)
```

### Node.js client

```javascript
const BASE = "http://localhost:8060/api/v1";

async function submitJob(filesOrDir, scheme = "{n} ({y})", outputDir = null) {
  const res = await fetch(`${BASE}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      files: [filesOrDir],
      naming_scheme: scheme,
      output_dir: outputDir,
      operation: "move",
    }),
  });
  const job = await res.json();
  console.log(`Job submitted: ${job.job_id}`);
  return job.job_id;
}
```

---

## API-only Docker deployment

For headless server use without a GUI:

```bash
docker run -d \
  --name sortiq-api \
  -p 8060:8060 \
  -e TMDB_API_KEY=your_key \
  -v ~/.sortiq:/root/.sortiq \
  -v /mnt/media:/media \
  ghcr.io/loukaniko/sortiq api
```

Or with compose — uncomment the `sortiq-api` service in `docker-compose.yml`.

---

## Error responses

All errors follow the standard FastAPI format:

```json
{"detail": "Human-readable error message"}
```

Common HTTP status codes:
- `201` — Resource created (new job, new watcher, new preset)
- `204` — Success, no content (delete operations)
- `400` — Bad request (e.g., tried to delete a built-in preset)
- `404` — File, directory, job, or watcher not found
- `422` — Validation error (check your request body against the schema)
- `500` — Internal error (usually a bad API key or network issue — check `/health`)
