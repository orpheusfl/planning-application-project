# Open Plan - Planning Application Data Pipeline and Dashboard

A comprehensive ETL pipeline and interactive dashboard for monitoring planning applications in Tower Hamlets. Scrapes council data, enriches it with AI-powered analysis, and displays it through an intuitive map-based interface.

Designed for: Residents associations, newsletters, and community groups monitoring local development.

## Project Overview

Planning Watchdog automates the discovery and analysis of planning applications across Tower Hamlets. The system:

1. **Extracts** application data from the Tower Hamlets Planning Portal
2. **Transforms** raw data using AI (OpenAI LLM) to generate resident-focused summaries and interest scores
3. **Loads** enriched data into a PostgreSQL RDS database
4. **Dashboard** displays applications on an interactive map with advanced filtering and search
5. **Alerts** Emails sent out to users about new applications matching their interests using SES
6. **RAG Chatbot** chatbot with access to the pdf documents for an application, to enable users to ask questions about documents

# How to Access the Dashboard   

The dashboard is hosted as an ECS service. You can access it at: [Add Link Here]

## How to Deploy and Run the ETL Pipeline and Dashboard on AWS

1. cd into the `terraform` folder
2. run `terraform apply`
3. each sub-folder contains a bash script for building the container, and pushing to the appropriate ECR
 - cd into the sub-folder
 - run  `bash build_and_push_container.sh`

[check if these steps are correct and add similar steps for the pipeline]

## How to Run the ETL Pipeline Locally

[add instructions here on how to build and run the pipeline dockerfile]

## How to Run the Dashboard Locally

[add instructions here on how to build and run the dashboard dockerfile]
