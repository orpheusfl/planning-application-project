# RAG Chatbot Lambda — OpenPlan

AWS Lambda function that enables residents to ask natural-language questions about the actual planning documents (PDFs) for any given application.

---

## What It Does

- Accepts a question and an application reference via an API Gateway event
- Connects to RDS to retrieve the application's document page URL
- Scrapes the Idox planning portal for PDF links associated with the application
- Downloads and extracts text from each PDF using PyMuPDF
- Passes the extracted document text and user question to an LLM for a grounded, document-aware response
- Returns the answer as a structured JSON response

This Retrieval-Augmented Generation (RAG) approach ensures answers are anchored to the actual submitted documents, not general knowledge.

---

## Key Files

| File | Description |
|---|---|
| `lambda_function.py` | Lambda handler — parses the event, orchestrates retrieval and LLM call |
| `extract_document_data.py` | Scrapes the council portal for PDF URLs and extracts their text content |

---

## Invoking the Lambda

Send a POST request with a JSON body:

```json
{
  "question": "Will this development overshadow neighbouring properties?",
  "application_number": "PA/2026/01234"
}
```

The Lambda is fronted by API Gateway and its URL is exported from Terraform.

---

## Deploying to AWS

```bash
bash build_and_push_container.sh
```

Builds the container image and pushes it to ECR. The Lambda is configured by Terraform to use this image.

---

## Environment Variables

| Variable | Description |
|---|---|
| `DB_HOST` | RDS PostgreSQL host |
| `DB_PORT` | RDS port |
| `DB_USERNAME` | Database username |
| `DB_PASSWORD` | Database password |
| `DB_NAME` | Database name |
| `OPENAI_API_KEY` | OpenAI API key for the LLM response |

---

## Status

The document extraction and PDF text pipeline is implemented and tested. The Lambda handler is currently a stub that returns a mock response — full LLM integration is the next development milestone.
