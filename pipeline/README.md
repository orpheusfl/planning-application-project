# ETL Pipeline — OpenPlan

Automated data pipeline that scrapes, enriches, and stores planning applications from the Tower Hamlets council portal. Runs as a scheduled ECS Fargate task.

---

## What It Does

1. **Extract** — Scrapes two sources in parallel:
   - *Current applications* list (rolling, all active applications)
   - *Weekly decided* list (recently determined applications with decision data)
   - Deduplicates across both sources, preferring weekly-decided entries where they overlap
2. **Transform** — For each new application:
   - Geocodes the address to lat/long via postcode extraction
   - Downloads planning documents (PDFs) from the council portal using a Selenium-driven browser
   - Extracts text from PDFs using PyMuPDF
   - Calls the OpenAI LLM (GPT-5-nano) in parallel (up to 5 concurrent calls) to produce:
     - A plain-English **AI summary** for residents
     - A **public interest score** (1–10)
     - Four **sub-scores**: disturbance, scale, housing impact, environment (each 1–5)
3. **Load** — Inserts new applications or updates existing ones (status, decision) in RDS PostgreSQL
4. **Store** — Saves downloaded PDFs to S3 at `<council>/<application_number>/<document_name>.pdf`

---

## Database Schema

Star schema with the following tables:

| Table | Type | Description |
|---|---|---|
| `application` | Fact | One row per planning application with all fields and scores |
| `document` | Fact | One row per planning document linked to an application |
| `council` | Dimension | Council lookup |
| `status_type` | Dimension | Application status lookup |
| `application_type` | Dimension | Application type lookup |
| `decision_type` | Dimension | Decision lookup |
| `subscriber` | Reference | Email alert subscriptions with postcode, radius, and score threshold |

---

## Key Files

| File | Description |
|---|---|
| `pipeline.py` | Orchestration entry point |
| `utilities/extract.py` | Web scraping (requests + BeautifulSoup + Selenium) |
| `utilities/transform.py` | `Application` class, geocoding, PDF extraction, LLM calls |
| `utilities/load.py` | RDS insert and update functions |
| `utilities/config.py` | LLM model name, parallelism limits, and scoring rubrics |
| `rds-init.sql` | Schema DDL — run once to initialise the database |
| `seed-reference-data.sql` | Inserts dimension table seed data |

---

## Running Locally

```bash
cd pipeline
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in values below
python pipeline.py
```

---

## Deploying to AWS

```bash
bash build_and_push_container.sh
```

Builds and pushes the container to ECR. The ECS scheduled task runs pipeline.py on a cron schedule defined in Terraform.

### Initialise the database (first run only)

```bash
bash run_init_db.sh
```

---

## Environment Variables

**RDS connection:**

```
RDS_HOST=
RDS_PORT=5432
RDS_USER=
RDS_PASSWORD=
RDS_DB_NAME=
```

**Table names (match `rds-init.sql` defaults):**

```
APPLICATION_FACT_TABLE=application
DOCUMENT_FACT_TABLE=document
COUNCIL_DIM_TABLE=council
STATUS_DIM_TABLE=status_type
APPLICATION_TYPE_DIM_TABLE=application_type
DOCUMENT_TYPE_DIM_TABLE=document_type
```

**LLM:**

```
OPENAI_API_KEY=
```



