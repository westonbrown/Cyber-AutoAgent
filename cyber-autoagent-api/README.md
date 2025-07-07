# Cyber‑AutoAgent API

A cloud‑agnostic service that accepts a JSON pentest job, runs a Strands‑powered Cyber‑AutoAgent worker in an isolated container, and exposes status and artefacts through a REST/JSON interface.

--

## 0.5 Current Setup/Testing Instructions

- `cd cyber-autoagent-api`
- `docker compose up --build`
- `curl -X POST http://localhost:8000/v1/jobs -H "Content-Type: application/json" -d '{"target":"https://example.com","objective":"test"}'`

---

## 1  Goals

* **Stateless public API** – keep the HTTP tier thin so it can scale horizontally.
* **Queued, long‑running jobs** – the request returns immediately while work happens in the background.
* **Pluggable infrastructure** – Redis/Kafka, MinIO/S3, Docker/Kubernetes can be swapped without rewriting code.
* **Clear separation of concerns** – API, queue, workers, storage, and database each have a single, well‑defined role.

---

## 2  Planned Architecture

```
┌──────────┐    HTTPS     ┌──────────────┐        Redis Streams       ┌─────────────┐
│  Client  │ ───────────▶ │  API Server  │ ─────▶│     Queue     │ ───▶│ Worker Pool │
└──────────┘              │ (FastAPI)    │                          └──────┬──────┘
        ▲                 └─────┬────────┘                                 │
        │                       │   SQLAlchemy                             │
        │                       │                                          ▼
        │                 ┌─────▼──────┐                        ┌─────────────┐
        │                 │ Postgres   │                        │  MinIO /    │
        │                 │  jobs DB   │                        │   S3‑API    │
        │                 └────────────┘                        └─────────────┘
```

### Stack at a Glance

| Layer          | Current Choice     | Other Options  |
| -------------- | ------------------ | ----------------- |
| API Framework  | **FastAPI**        | Express, NestJs   |
| Job Queue      | **Redis 6**        | RabbitMQ, Kafka   |
| Worker Runtime | **Celery**         | RQ, Kombu         |
| Database       | **PostgreSQL**     | MySQL, Cockroach  |
| Object Storage | **MinIO**          | AWS S3, GCS       |
| Orchestration  | **Docker Compose** | Kubernetes, Nomad |

---

## 3  Component Responsibilities

| Component        | Responsibility                                                                                           |
| ---------------- | -------------------------------------------------------------------------------------------------------- |
| **API Server**   | Validate requests, enqueue jobs, expose status & artefact endpoints, enforce JWT auth & rate‑limits.     |
| **Job Queue**    | Buffer jobs; provide back‑pressure; let workers pull at their own pace.                                  |
| **Worker Pool**  | Pop a job, launch Cyber‑AutoAgent (Strands) inside Docker, stream progress, upload artefacts, update DB. |
| **PostgreSQL**   | Source of truth for job metadata, status, progress %.                                                    |
| **Object Store** | Durable storage for evidence, reports, logs; presigned download URLs.                                    |

---

## 4  Data / Control Flow

1. **POST /jobs** – client submits a job definition (target, objective, etc.).
2. API writes `jobs` row (**PENDING**) and pushes JSON payload onto Redis stream `jobs`.
3. Worker consumes the stream entry, changes status to **RUNNING** and calls the Strands agent.
4. On completion, artefacts are uploaded to MinIO under `jobs/{id}/`, DB row is updated to **SUCCEEDED** (or **FAILED**).
5. Client polls **GET /jobs/{id}** or waits for webhook (TODO) and then downloads artefacts.

---

## 5  Repository Structure

```
cyber-autoagent-api/
├── api/            # FastAPI service
│   ├── main.py
│   ├── models.py
│   ├── routes/
│   └── db/
├── worker/         # Celery worker & agent runner
├── common/         # Shared utilities (storage, settings)
├── docker-compose.yml
├── Dockerfile.api
├── Dockerfile.worker
└── pyproject.toml
```

---

## 6  Milestones

> These milestones describe functionality gates—**no specific dates included**.

| Milestone                          | What is delivered                                                                                                              |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **1 – Scaffold & Hello‑World**     | Docker‑Compose stack; FastAPI POST/GET; Redis queue; Postgres `jobs` table; worker prints "hello" and marks job **SUCCEEDED**. |
| **2 – Real Agent Execution**       | Worker runs Cyber‑AutoAgent, pushes final report to MinIO; artefact listing and presigned download endpoint.                   |
| **3 – Robustness + Observability** | Task retries, progress %, JSON logs to stdout; `/healthz` endpoints.                                                           |
| **4 – Auth & Basic Tenancy**       | JWT verification, `tenant_id` column, simple rate limiting.                                                                    |
| **5 – CI/CD & Packaging**          | Poetry + Ruff + pytest; GitHub Actions build/push images; comprehensive README with local dev instructions.                    |

---

## 7  Future Enhancements (TODO)

* Server‑Sent Events / WebSocket stream for live agent events.
* Usage metering & billing integration.
* Kubernetes Helm chart and horizontal pod autoscaling.
* Row‑level security and field‑level encryption for multi‑tenant compliance.
* SLA tiers with priority queues and dedicated worker pools.
* Audit‑log chaining and tamper‑evident artefact signatures.