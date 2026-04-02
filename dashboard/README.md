# Dashboard — OpenPlan

Interactive map-based UI for browsing AI-enriched planning applications. Built with Streamlit and deployed as an ECS Fargate service behind an Application Load Balancer.

---

## What It Does

- Plots all planning applications as colour-coded map markers, clustered by postcode
- Sidebar filters: date range, application status, public interest score, and four AI sub-scores
- Postcode + radius filter using vectorised haversine distance
- Full-text search across application descriptions and addresses
- Per-application detail panel: AI summary, impact scores, links to council documents
- Council boundary polygon overlay (Tower Hamlets, Lewisham)
- Subscriber management: sign up for email alerts with custom postcode, radius, and minimum score threshold

---

## Key Files

| File | Description |
|---|---|
| `app.py` | Streamlit entry point and page routing |
| `utils/queries.py` | Database queries; loads applications and boundary data |
| `utils/filters.py` | Pure DataFrame filtering functions (date, status, score, radius, council) |
| `utils/components.py` | All Streamlit UI components (map, sidebar, detail view, search) |
| `utils/subscribers.py` | Subscriber CRUD against the `subscriber` table |
| `utils/config.py` | CSS and shared config constants |
| `boundaries/` | GeoJSON boundary files for council overlays |

---

## Running Locally

### Docker (recommended)

```bash
# From the project root
docker build -t openplan-dashboard:latest dashboard/
docker run -p 8501:8501 \
  -e RDS_HOST=... \
  -e RDS_PORT=5432 \
  -e RDS_USER=... \
  -e RDS_PASSWORD=... \
  -e RDS_DB_NAME=... \
  openplan-dashboard:latest
```

### Directly

```bash
cd dashboard
pip install -r requirements.txt
streamlit run app.py
```

---

## Deploying to AWS

```bash
bash build_and_push_container.sh
```

The script builds the image, authenticates with ECR, and pushes it. ECS picks up the new image on the next service deployment.

---

## Environment Variables

| Variable | Description |
|---|---|
| `RDS_HOST` | PostgreSQL host |
| `RDS_PORT` | PostgreSQL port (default `5432`) |
| `RDS_USER` | Database username |
| `RDS_PASSWORD` | Database password |
| `RDS_DB_NAME` | Database name |

In production these are injected by the ECS task definition via AWS Secrets Manager.
