# Roulette-Kaki

## Table of Contents

1. [Overview](#1-overview)
2. [Features](#2-features)
3. [Tech Stack](#3-tech-stack)
4. [Prerequisites](#4-prerequisites)
5. [Quick Start](#5-quick-start)
6. [Configuration](#6-configuration)
7. [API Reference](#7-api-reference)
8. [General Workflow](#8-general-workflow)
9. [Data Sources](#9-data-sources)
10. [Troubleshooting](#10-troubleshooting)
11. [Testing & Utilities](#11-testing--utilities)
12. [Security & Privacy](#12-security--privacy)
13. [Roadmap](#13-roadmap)

## 1. Overview

Roulette-Kaki was created as part of the SimplifyNext Agentic AI Hackathon 2026.

Understanding and following developments in policy is important for individual Singaporeans as policy impacts their day-to-day living.
Unfortunately, policies are often long, dry and complex, requiring significant time and effort to understand.
Additionally, it is difficult to follow proposed changes to policy as these discussions are often hidden under hours of parliamentary debate.
This results in Singaporeans often being more politically apathetic and being unprepared for policy change that they could have known about if they were more in tune with news and debates.

## 2. Features

Roulette-Kaki aims to resolve this issue through two main functions: a policy summariser and a debate summariser.

The policy summariser summarises existing policy and presents it in a news-article-like way, pulling and citing information from both official and unofficial sources.

The debate summariser summarises the content of a parliamentary debate session.

Users may consult an AI helper, allowing them to narrow down relevant information, which further aids in their decision making.

## 3. Tech Stack

### Front end

- React
- Tailwind CSS
- Vite

### Back end

#### FastAPI

#### API services

- YouTube (Google) API
- AWS Bedrock
- Google
- DuckDuckGo

#### AWS

- AWS AI services
- S3
- DynamoDB
- Lambda
- Bedrock

## 4. Prerequisites

The following dependencies are required to run the program:

- FastAPI 0.115.0 or later
- uvicorn[standard] 0.32.0 or later
- boto3 1.35.0 or later
- pydantic 2.9.0 or later
- requests 2.31.0 or later
- beautifulsoup4 4.12.0 or later
- httpx 0.27.0 or later
- mangum 0.19.0 or later

## 5. Quick Start

1. Create a virtual environment and install Python dependencies:

	 ```bash
	 python -m venv .venv && source .venv/bin/activate
	 pip install -r requirements.txt
	 ```

2. Configure credentials and app settings (see [Configuration](#6-configuration)).

3. Run the backend:

	 ```bash
	 uvicorn backend.main:app --reload
	 ```

4. Visit `http://127.0.0.1:8080/docs` for interactive API docs.

5. Run the frontend:

	 ```bash
	 cd frontend && npm install && npm run dev
	 ```

### Run locally

```bash
uvicorn backend.main:app --reload
```

Visit Swagger UI at `http://127.0.0.1:8080/docs`.

## 6. Configuration

## 7. API Reference

The API is implemented in `application/backend/main.py`. When running in API-only mode, the endpoints use the paths below. When the built frontend is served by the backend, prefix API paths with `/api`.

### General

- `GET /`
- `GET /health`

### Policy query

- `POST /query`
	- Body: `{ question, urls?, session_id?, language? }`
	- Returns: `{ answer, session_id, language }`
- `GET /query/sessions/{session_id}`
	- Returns the stored query session.

### Parliamentary debates

- `GET /sittings?limit=6&offset=0`
	- Returns available parliamentary sittings.
- `GET /debates`
	- Returns cached debate digests.
- `GET /debates/{date}?refresh=false&language=English`
	- Returns the digest for a parliamentary sitting.
- `POST /debates/{date}/chat`
	- Body: `{ session_id?, message, topic_id?, language? }`
	- Returns: `{ session_id, reply, topics_used, grounded }`
- `POST /debates/{date}/flashcards/topic/{topic_id}`
	- Body: `{ count? }`
	- Returns a generated flashcard deck for a debate topic.
- `POST /debates/{date}/flashcards/from-chat`
	- Body: `{ reply_text, topic_ids?, count? }`
	- Returns a generated flashcard deck from a chat reply.

### Language and audio

- `POST /translate`
	- Body: `{ text, target_language, source_language? }`
	- Returns: `{ translated_text, target_language }`
- `POST /transcribe`
	- Body: `{ audio_b64, mime? }`
	- Returns: `{ text, transcript }`
- `POST /translate/audio`
	- Body: `{ audio_b64, target_language, mime? }`
	- Returns: `{ translated_text, target_language }`

## 8. General Workflow

1. Browse available parliamentary sittings with `GET /sittings`.
2. Fetch a debate digest with `GET /debates/{date}`.
3. Review the summarised topics and select a relevant topic.
4. Ask the AI helper follow-up questions with `POST /debates/{date}/chat`.
5. Generate flashcards from a topic or chat response when useful.
6. Use `POST /query` to search for current policy information from official and unofficial sources.
7. Use translation or transcription endpoints when working with supported languages or audio input.

## 9. Data Sources

## 10. Troubleshooting

## 11. Testing & Utilities

## 12. Security & Privacy

- Keep `.env` out of source control and rotate AWS credentials regularly.
- Grant Bedrock permissions only for the models and regions the application requires.
- Avoid logging or persisting sensitive user inputs beyond what is necessary to maintain a session.

## 13. Roadmap
