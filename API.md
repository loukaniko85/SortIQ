# SortIQ REST API

SortIQ ships a full REST API built on **FastAPI**. It gives you every capability of the GUI in a scriptable, automatable form — perfect for NAS setups, home media servers, CI pipelines, and unattended batch renaming.

**Swagger UI (interactive):** `http://localhost:8060/docs`  
**ReDoc (readable):** `http://localhost:8060/redoc`  
**OpenAPI JSON:** `http://localhost:8060/openapi.json`

---

## Quick start

```bash
# Start the container (API + GUI)
docker run -p 6080:6080 -p 8060:8060 \
  -e TMDB_API_KEY=your_key \
  -v ~/Media:/media \
  sortiq

# Set your key via the API (alternative to env var)
curl -X POST "http://localhost:8060/api/v1/settings/keys?tmdb=YOUR_KEY"

# Check health
curl http://localhost:8060/api/v1/health
```

---

## Endpoints

All endpoints are under the prefix `/api/v1`.

### Info

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check — key status, mediainfo availability |
| GET | `/naming-tokens` | Reference for all `{token}` placeholders |

### Media operations

| Method | Path | Description |
|--------|------|-------------|
| POST | `/media/scan` | Scan a directory for media files |
| POST | `/media/parse` | Parse a filename into structured metadata (no API calls) |
| POST | `/media/search` | Search TMDB for movies or TV shows |
| POST | `/media/match` | Match files against TMDB/TVDB — returns proposed names |
| POST | `/media/rename` | Match **and** rename files in one synchronous call |
| POST | `/media/checksum` | Compute MD5/SHA1/SHA256 checksums with optional sidecar files |

### Batch jobs (async)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/jobs` | Submit a batch rename job (returns immediately with `job_id`) |
| GET | `/jobs` | List all jobs |
| GET | `/jobs/{job_id}` | Get job detail, progress, per-file results, and log |
| POST | `/jobs/{job_id}/cancel` | Cancel a running job |
| DELETE | `/jobs/{job_id}` | Remove a job record |

### Presets

| Method | Path | Description |
|--------|------|-------------|
| GET | `/presets` | List all naming scheme presets |
| POST | `/presets` | Create or update a preset |
| DELETE | `/presets/{name}` | Delete a preset |

### History

| Method | Path | Description |
|--------|------|-------------|
| GET | `/history` | Get rename history (supports undo from the GUI) |

### Settings

| Method | Path | Description |
|--------|------|-------------|
| POST | `/settings/keys` | Update API keys at runtime — no restart required |

---

## Naming scheme tokens

| Token | Description |
|-------|-------------|
| `{n}` | Title (movie or show name) |
| `{y}` | Year |
| `{t}` | Episode title |
| `{s}` | Season number (S01) |
| `{e}` | Episode number (E01) |
| `{s00e00}` | Season+episode combined (S01E01) |
| `{vf}` | Video resolution (1080p, 720p…) |
| `{vc}` | Video codec (x264, x265, HEVC…) |
| `{af}` | Audio codec (AAC, AC3, DTS…) |
| `{ac}` | Audio channels (5.1, 2.0…) |

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

### 2 — Batch rename a whole folder

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

### 3 — Submit async batch job and poll for progress

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
  STATUS=$(curl -s "http://localhost:8060/api/v1/jobs/$JOB_ID" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'], d['progress']['percent'],'%')")
  echo $STATUS
  echo "$STATUS" | grep -qE "completed|failed|cancelled" && break
  sleep 2
done
```

### 4 — Submit job with webhook callback

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

The webhook receives a `POST` with the job summary JSON on completion.

### 5 — Generate checksums for verification

```bash
curl -X POST http://localhost:8060/api/v1/media/checksum \
  -H "Content-Type: application/json" \
  -d '{
    "files": ["/media/Movies/Inception (2010)/Inception (2010).mkv"],
    "algorithm": "sha256",
    "save_sfv": true
  }'
```

### 6 — Search for a title manually

```bash
curl -X POST http://localhost:8060/api/v1/media/search \
  -H "Content-Type: application/json" \
  -d '{"query": "The Dark Knight", "year": 2008, "type": "movie"}'
```

### 7 — Headless API-only mode (no GUI)

```bash
docker run -p 8060:8060 \
  -e TMDB_API_KEY=your_key \
  -v ~/Media:/media \
  sortiq api
```

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
  sortiq api
```

Or with compose — uncomment the `sortiq-api` service in `docker-compose.yml`.

---

## Error responses

All errors follow the standard FastAPI format:

```json
{"detail": "Human-readable error message"}
```

Common errors:
- `404` — File or job not found
- `422` — Validation error (check your request body)
- `500` — Internal error (usually a bad API key or network issue — check `/health`)
