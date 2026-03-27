# RyuNova Platform – Conversation history

This file records the main conversation topics and decisions from the design and documentation work for RyuNova Platform, so they can be read and reviewed later.

**Application:** RyuNova Platform (listing, channel integration, order review and fulfillment; primary use case: coffee machine products.)  
**Location:** All RyuNova design and development docs live under the `RyuNova/` folder.

---

## 1. Application naming and database prefix

- **Request:** Use “RyuNova” as the application name and apply it as a prefix for all database objects (tables, enums, etc.).
- **Done:** All schema objects in [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) use the **`ryunova_`** prefix (e.g. `ryunova_users`, `ryunova_listing_status`, `ryunova_order`). Document title and history updated.
- **Later:** Application was renamed to **RyuNova Platform** across documentation (title, README, plans, deployment, design history).

---

## 2. Organising content under RyuNova folder

- **Request:** Move all plans and anything related to RyuNova design and development under a new top folder called RyuNova.
- **Done:**
  - Created **`RyuNova/`** at repo root.
  - Moved **DATABASE_SCHEMA.md** and **DESIGN_DEVELOPMENT_HISTORY.md** from `globalcoffee/Coffee_Machine_Listing_App/` into `RyuNova/`.
  - Created **`RyuNova/plans/`** and copied RyuNova-related plan files from `.cursor/plans/` (architecture and microservice plans).
  - Updated cross-references in docs and plans to use `RyuNova/` paths.
  - Removed the old `globalcoffee/Coffee_Machine_Listing_App/` files and empty directory.
  - Added **RyuNova/README.md** as the index for the folder.

---

## 3. Microservice architecture

- **Request:** Enable design to follow microservice architecture and recommend key microservices.
- **Done:** A plan was created (and content reflected in architecture docs) with: microservice principles; recommended services (API Gateway, Product & Catalog, Identity & Config, Channel Registry, Listing, Inventory, Order, Listing Orchestrator, Channel Adapters, Notification, Audit); sync/async communication; and option to start with a single server (consolidated API + worker) then split later.

---

## 4. Proposal content for client (2-month build, agile, MVPs)

- **Request:** Create proposal content for building the application for the coffee machine client: assurance that the app will make staff life easier, key communication points, agile delivery, and a 2-month MVP sequence.
- **Done:** A plan was created for the proposal content: assurance points (one place for products, orders in one place, less manual work, time back for team, built in small steps); key messages; agile method; MVP sequence (MVP1 Foundation, MVP2 List to channels, MVP3 Orders and fulfillment view, MVP4 Inventory and polish) over 2 months; steps to build progressively. The actual proposal document can be written from that plan.

---

## 5. UX requirements and standards

- **Request:** Create a document listing UX requirements and standards for the application using a minimalist theme (Uber-like), with a compact design so more content can be shown on the same page.
- **Done:** Created [UX_REQUIREMENTS_AND_STANDARDS.md](UX_REQUIREMENTS_AND_STANDARDS.md) covering: design principles (minimalist, compact, scannable, consistent, accessible); typography, colour, spacing; layout (compact tables, forms, filter bar); components (buttons, status, empty/loading states); key screens (product list, product detail, listings, orders, channels); responsiveness; WCAG 2.1 AA. Reference: Uber-style minimalism with compact density.

---

## 6. Deployment (Docker, EC2, GitHub Actions)

- **Request:** Create a document showing end deployment status using Docker and Docker Compose, based on the architecture, with the product deployed via GitHub Actions to an EC2 server and accessible at ryunova.dragonandpeaches.com.au; list services and suggest key Docker containers/images; single server solution.
- **Done:** Created [DEPLOYMENT_DOCKER_EC2.md](DEPLOYMENT_DOCKER_EC2.md) with: single-server architecture diagram; list of six services (proxy, ryunova-api, ryunova-worker, ryunova-web, postgres, redis); suggested Docker images (official + custom for API, worker, web); end deployment status checklist; example Docker Compose; GitHub Actions deploy outline; summary table. URL: https://ryunova.dragonandpeaches.com.au.

---

## 7. Technology stack: FastAPI + Django

- **Request:** Confirm we will use FastAPI for the API and Django for the frontend.
- **Done:** Confirmed and documented:
  - **FastAPI** for the API backend.
  - **Django** for the frontend (admin UI); Django serves the UI and consumes the FastAPI API (e.g. Gunicorn in production).
  - Updated: [README.md](README.md), both architecture plans in [plans/](plans/), [DEPLOYMENT_DOCKER_EC2.md](DEPLOYMENT_DOCKER_EC2.md) (ryunova-web = Django + Gunicorn), and [DESIGN_DEVELOPMENT_HISTORY.md](DESIGN_DEVELOPMENT_HISTORY.md).

---

## 8. Git add, commit, push

- **Request:** Run git add, commit, and push.
- **Done:** Staged all changes, committed with a message covering RyuNova docs, UX standards, reorg (ROMS_Docs, globalcoffee, etc.), and other new content; pushed to `origin/main` (55 files changed).

---

## 9. MVP1 readiness and skills

- **Request:** Confirm whether we have all information to build the application for the first milestone (MVP1) as per the plan; user already has the database installed locally; list what skills are needed to build and run the application.
- **Done:** Created [MVP1_READINESS_AND_SKILLS.md](MVP1_READINESS_AND_SKILLS.md) which:
  - Confirms we have enough to build MVP1: schema (with MVP1 subset: users, user_roles, categories, product_master, product_image, product_condition enum), stack (FastAPI + Django + PostgreSQL), UX standards, deployment outline; Redis/Celery can wait until MVP2.
  - Lists MVP1 schema subset to create first in the local DB.
  - Lists skills: core (Python, FastAPI, Django, PostgreSQL, SQL, HTML/CSS/JS basics, auth); then REST, file storage; then Redis, Celery, Docker, channel APIs for MVP2+; and optional (Pydantic, SQLAlchemy, HTMX, EC2, Nginx, GitHub Actions).
  - Suggests next steps: create MVP1 schema locally, implement FastAPI (Product + Categories + Auth), implement Django (product list, product form, login).

---

## 10. Conversation history file

- **Request:** Put the conversation history into a file so it can be read and viewed again.
- **Done:** This file ([CONVERSATION_HISTORY.md](CONVERSATION_HISTORY.md)) was created to record the main conversation topics and outcomes.

---

## Related documents

| Document | Description |
|----------|-------------|
| [README.md](README.md) | RyuNova folder index and contents. |
| [DESIGN_DEVELOPMENT_HISTORY.md](DESIGN_DEVELOPMENT_HISTORY.md) | Chronological design requests and outcomes (product/schema focus). |
| [MVP1_READINESS_AND_SKILLS.md](MVP1_READINESS_AND_SKILLS.md) | First milestone readiness and skills. |

---

*Last updated to capture conversation history for review. Add new entries here when significant decisions or requests are made.*
