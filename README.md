# OpenPlan — Planning Intelligence Platform

> Automated monitoring and AI-powered analysis of UK planning applications, delivered through an interactive map-based dashboard.

OpenPlan gives communities, residents associations, and local newsletters instant visibility into nearby planning activity — without trawling council websites. The platform scrapes live data, enriches each application with AI-generated summaries and impact scores, and surfaces everything through a clean, filterable map interface with email alerts.

---

## Key Features

| Feature | Description |
|---|---|
| **Live Data Pipeline** | Automated scraping of current and weekly-decided applications from the council portal |
| **AI Enrichment** | GPT-powered plain-english summaries and four impact sub-scores per application |
| **Interactive Dashboard** | Map-based Streamlit UI with postcode search, filters, and per-application detail views |
| **Email Alerts** | Subscribers receive notifications for new applications matching their postcode, radius, and interest threshold |
| **RAG Chatbot** | AWS Lambda function enabling natural-language Q&A over the actual planning documents (PDFs) |
| **Fully Cloud-Native** | Containerised, serverless, and infrastructure-as-code on AWS — zero manual ops |

---

## Architecture

```
Council Planning Portal
        │
        ▼
┌───────────────────┐     ┌─────────────┐     ┌─────────────────┐
│  ETL Pipeline     │────▶│  OpenAI LLM │────▶│   RDS (Postgres)│
│  (ECS Fargate)    │     │  (GPT-5)    │     │                 │
└───────────────────┘     └─────────────┘     └────────┬────────┘
                                                        │
                          ┌─────────────────────────────┤
                          │                             │
                    ┌─────▼──────┐             ┌───────▼────────┐
                    │  Dashboard │             │  Notifications │
                    │ (Streamlit/│             │  Lambda (SES)  │
                    │  ECS/ALB)  │             └────────────────┘
                    └─────┬──────┘
                          │
                    ┌─────▼──────┐
                    │ RAG Lambda │
                    │ (PDF Q&A)  │
                    └────────────┘
```

**AWS Services:** ECS Fargate · RDS PostgreSQL · S3 · Lambda · SES · ALB · ECR · CloudWatch · Secrets Manager  
**Region:** eu-west-2

---

## AI Scoring

Every new application is automatically scored by the LLM across four resident-relevant dimensions (1–5 scale):

- **Disturbance** — noise, dust, and disruption during construction
- **Scale** — physical size and duration of works
- **Housing Impact** — effect on local property supply and prices
- **Environment** — impact on green space, biodiversity, and community feel

A composite **public interest score** (1–10) combines these for quick filtering.

---

## Deliverables

| Component | Description | Folder |
|---|---|---|
| ETL Pipeline | Scraper, LLM transform, and DB loader | [`pipeline/`](pipeline/README.md) |
| Dashboard | Streamlit map UI | [`dashboard/`](dashboard/README.md) |
| RAG Chatbot | Document Q&A Lambda | [`RAG-lambda/`](RAG-lambda/README.md) |
| Infrastructure | Terraform for all AWS resources | [`terraform/`](terraform/README.md) |

---

## Deploying to AWS

### 1. Provision infrastructure

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars  # fill in secrets
terraform init
terraform apply
```

### 2. Build and push containers

Run the build script in each sub-folder. Each script authenticates with ECR, builds the Docker image, and pushes it.

```bash
# Pipeline
cd pipeline && bash build_and_push_container.sh

# Dashboard
cd dashboard && bash build_and_push_container.sh

# RAG Lambda
cd RAG-lambda && bash build_and_push_container.sh

# Notifications Lambda (from root)
bash build-notifications.sh
```

### 3. Initialise the database

```bash
cd pipeline && bash run_init_db.sh
```

ECS tasks pick up the new images automatically on the next deployment cycle.

---

## Running Locally

### Pipeline

```bash
cd pipeline
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in RDS credentials and OpenAI key
python pipeline.py
```

### Dashboard

```bash
# Using Docker (recommended)
docker build -t openplan-dashboard:latest dashboard/
docker run -p 8501:8501 -v ~/.aws:/root/.aws openplan-dashboard:latest

# Or directly
cd dashboard
pip install -r requirements.txt
streamlit run app.py
```

---

## Environment Variables

| Variable | Used By | Description |
|---|---|---|
| `RDS_HOST` | Pipeline, Dashboard | PostgreSQL host |
| `RDS_PORT` | Pipeline, Dashboard | PostgreSQL port (default `5432`) |
| `RDS_USER` | Pipeline, Dashboard | Database username |
| `RDS_PASSWORD` | Pipeline, Dashboard | Database password |
| `RDS_DB_NAME` | Pipeline, Dashboard | Database name |
| `OPENAI_API_KEY` | Pipeline | OpenAI API key for LLM enrichment |

In production, secrets are managed via AWS Secrets Manager and injected into ECS task definitions by Terraform.

---

## Tech Stack

**Backend:** Python 3.13 · BeautifulSoup · Selenium · PyMuPDF · OpenAI SDK  
**Frontend:** Streamlit · Pandas · NumPy  
**Database:** PostgreSQL (AWS RDS) — star-schema optimised for time-series filtering  
**Infrastructure:** Terraform · Docker · AWS (ECS, RDS, S3, Lambda, SES, ALB, ECR, CloudWatch)

---

## Roadmap

- [ ] Multi-council support (Lewisham boundary data already included)
- [ ] RAG chatbot fully integrated into the dashboard UI
- [ ] Subscriber self-service portal (manage alert preferences)
- [ ] Public API for third-party integrations
