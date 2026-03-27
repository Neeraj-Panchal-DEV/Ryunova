# RyuNova Platform – Design and development

This folder contains all **RyuNova Platform** design and development documentation: schema, design history, and architecture plans.

**Application name:** RyuNova Platform  
**Purpose:** Listing management, channel integration, order review and fulfillment across multiple sales channels (primary use case: coffee machine and related products).

**Technology stack (confirmed):** **FastAPI** for the API backend; **Django** for the frontend (admin UI).

## Contents

| Item | Description |
|------|-------------|
| [MVP1_BUILD_AND_DELIVERY.md](MVP1_BUILD_AND_DELIVERY.md) | **MVP1 handoff:** what was built (DB, API, Django UI, docs), scope in/out, smoke checklist. |
| [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) | Full PostgreSQL schema: ryunova_-prefixed tables, enums, indexes, CRUD mapping, extensibility. |
| [DESIGN_DEVELOPMENT_HISTORY.md](DESIGN_DEVELOPMENT_HISTORY.md) | Chronological sequence of design requests and outcomes; key modules. |
| [UX_REQUIREMENTS_AND_STANDARDS.md](UX_REQUIREMENTS_AND_STANDARDS.md) | UX requirements and standards: minimalist (Uber-inspired), compact layout, components, accessibility. |
| [DEPLOYMENT_DOCKER_EC2.md](DEPLOYMENT_DOCKER_EC2.md) | End deployment: Docker/Docker Compose on single EC2, GitHub Actions, ryunova.dragonandpeaches.com.au; list of services and suggested images. |
| [MVP1_READINESS_AND_SKILLS.md](MVP1_READINESS_AND_SKILLS.md) | MVP1 readiness (do we have everything?); MVP1 schema subset; skills needed to build and run the application. |
| [CONVERSATION_HISTORY.md](CONVERSATION_HISTORY.md) | Conversation history: main topics and decisions from design and documentation work (for review and reference). |
| [plans/](plans/) | Architecture and microservice plans (RyuNova Platform Architecture, Microservice Architecture). |
| [plans/ryunova_build_proposal_content.plan.md](plans/ryunova_build_proposal_content.plan.md) | Build proposal content plan (assurance, agile, 2-month MVPs). |
| [RyuNova_Build_Proposal_Content_PRINT.html](RyuNova_Build_Proposal_Content_PRINT.html) | Print-ready HTML of the build proposal content plan. |

## Plans

- **RyuNova Platform Architecture** – High-level design, goals, key modules, core components, data model, technology options, flow, channel integration.
- **RyuNova Platform Microservice Architecture** – Microservice boundaries, recommended services, communication (sync/async), document updates.

Plans under `plans/` are copies for reference; Cursor may also keep plan state under `.cursor/plans/` outside this repo.
