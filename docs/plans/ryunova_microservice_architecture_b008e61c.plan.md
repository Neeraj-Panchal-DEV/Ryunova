---
name: RyuNova Platform Microservice Architecture
overview: Enable the RyuNova Platform design to follow a microservice architecture and recommend the key microservices, with clear service boundaries, ownership of schema/domains, and communication patterns (sync API and async events).
todos: []
isProject: false
---

# RyuNova Platform microservice architecture

## Objective

- **Enable** the existing RyuNova Platform design to follow a **microservice architecture** (update architecture plan and related docs).
- **Recommend** the **key microservices** needed for listing, channel integration, order review and fulfillment, with clear boundaries and communication.

---

## 1. Microservice architecture principles to apply

- **Single responsibility per service** – Each service owns one bounded context and its data (or a small set of related tables).
- **Communication** – **Sync** (REST or gRPC) for request/response; **async** (message queue / events) for listing jobs, order import, audit, and notifications to avoid tight coupling and support scaling.
- **Data ownership** – Each service owns its tables; other services access via API or events. Option: start with **shared database, separate schemas or logical ownership** for simplicity, then move to **database-per-service** when scaling or team boundaries require it.
- **API Gateway** – Single entry point for the admin UI; routing, auth, and (optionally) aggregation of backend services.
- **Resilience** – Retries, circuit breakers, and idempotency for cross-service and channel-adapter calls.

---

## 2. Recommended key microservices


| #   | Microservice                      | Ownership (ryunova_* tables / responsibility)                                                                            | Purpose                                                                                                                                                                                                                                                           |
| --- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **API Gateway**                   | None (no domain DB)                                                                                                      | Single entry; route to backend services; auth (validate tokens with Identity); rate limit; optional BFF aggregation.                                                                                                                                              |
| 2   | **Product & Catalog Service**     | product_master, product_channel_list_flag, product_channel_override, product_image, categories, channel_category_mapping | Product CRUD; per-channel list flags and overrides; categories and channel category mapping; image metadata (S3 refs).                                                                                                                                            |
| 3   | **Identity & Config Service**     | users, user_roles, oauth_tokens, app_config, user_settings                                                               | User CRUD; OAuth/login; app and system config; per-user settings.                                                                                                                                                                                                 |
| 4   | **Channel Registry Service**      | channels, channel_config, channel_credentials                                                                            | Channel definitions and credentials; config for adapters (no secrets in other services).                                                                                                                                                                          |
| 5   | **Listing Service**               | listing, listing_history, sale                                                                                           | Listing lifecycle state (draft → listed → ended/sold); history and sale records; source of truth for “is this product listed on channel X?”.                                                                                                                      |
| 6   | **Inventory Service**             | inventory_location, inventory_level                                                                                      | Locations; quantity, reserved, low_stock_threshold; reserve/release on order; sync to channels (called by Order and Listing Orchestrator).                                                                                                                        |
| 7   | **Order Service**                 | order, order_line                                                                                                        | Order import from channels; source_channel_info; fulfillment status; single place for order review and fulfillment.                                                                                                                                               |
| 8   | **Listing Orchestrator (Worker)** | listing_job (consumes from queue)                                                                                        | Consumes listing jobs; runs List / Sales / Delist engines; calls Channel Adapters; updates Listing Service and Inventory Service; publishes events (e.g. listing_success, sale).                                                                                  |
| 9   | **Channel Adapters**              | None (stateless)                                                                                                         | Pluggable adapters (eBay, Facebook, Gumtree, Shopify, usedcoffeegear, Amazon): translate product/listing to channel API; auth and rate limits. Can be **embedded in Listing Orchestrator** or a separate **Channel Integration Service** that Orchestrator calls. |
| 10  | **Notification Service**          | notification_config                                                                                                      | How/when to send notifications; receives events (listing_success, listing_failure, sale, etc.) and sends email/webhook/in-app.                                                                                                                                    |
| 11  | **Audit Service**                 | audit_log                                                                                                                | Receives audit events (product/listing/override changes) and persists; or other services push via API.                                                                                                                                                            |


**Optional / later:**

- **Reporting Service** – Read-only views or replicated data for dashboards and reports.
- **3PL / Shipping Service** – When extending to shipping labels and 3PL integration.

---

## 3. High-level flow (microservices)

- **Admin UI** → **API Gateway** → **Product**, **Identity**, **Channel Registry**, **Listing**, **Inventory**, **Order** (sync).
- **Product Service** (on list-flag change) → enqueue **listing job** → **Listing Orchestrator** consumes → calls **Channel Adapters** (using **Channel Registry** for config/creds) → updates **Listing Service** (and optionally **Inventory**).
- **Listing Orchestrator** (Sales engine) → import orders from adapters → write/update **Order Service**; update **Listing Service** (sold); optionally **Inventory** (reserve/decrement).
- **Order Service** / **Listing Service** / **Product Service** → publish **audit events** → **Audit Service**; publish **notification events** → **Notification Service**.

---

## 4. Communication and infrastructure

- **Sync:** REST or gRPC between Gateway and backend services; between Listing Orchestrator and Listing, Inventory, Order, Channel Registry (and Channel Adapters if separate).
- **Async:** Message broker (e.g. **Redis** + Celery, **RabbitMQ**, or **Kafka**) for: listing jobs, order-import events, audit events, notification events.
- **Auth:** Identity Service issues JWT or session; API Gateway validates and forwards; backend services validate token or accept gateway-validated identity.

---

## 5. Document updates to apply

1. **Architecture plan** ([coffee_machine_listing_app_architecture_1452ab43.plan.md](coffee_machine_listing_app_architecture_1452ab43.plan.md))
  - Add a **Microservice architecture** section: principles, recommended microservices table (as above), and a **mermaid diagram** showing services and sync/async flows (API Gateway, Product, Identity, Channel Registry, Listing, Inventory, Order, Listing Orchestrator, Channel Adapters, Notification, Audit).
  - Update **High-level architecture** (Section 3) to state that the system is designed as microservices; optionally replace or supplement the current diagram with a microservice view.
  - In **Core components**, align rows with service ownership (e.g. Product Service, Listing Service, Order Service, Listing Orchestrator, Notification Service, Audit Service).
2. **Design development history** ([../DESIGN_DEVELOPMENT_HISTORY.md](../DESIGN_DEVELOPMENT_HISTORY.md))
  - Add a new **Sequenced request**: “Enable design to follow microservice architecture and recommend key microservices.”
  - Outcome: microservice principles; list of 11 recommended microservices with ownership and communication (sync/async).
3. **DATABASE_SCHEMA.md** (optional)
  - Add a short **Microservice ownership** subsection (e.g. in “Schema object list” or new section): map each ryunova_* table to the owning microservice (Product & Catalog, Identity & Config, Channel Registry, Listing, Inventory, Order, Notification, Audit). Listing job table owned by Listing Orchestrator (or shared queue persistence).

---

## 6. Diagram sketch (for plan doc)

New mermaid in the architecture plan:

- **Left:** Admin UI → API Gateway.
- **Gateway** → Product, Identity, Channel Registry, Listing, Inventory, Order (sync).
- **Product / Order / external** → **Message queue** (listing jobs, events).
- **Listing Orchestrator** ← queue; → Channel Adapters; → Listing, Inventory, Order (sync).
- **Channel Adapters** → external channel APIs.
- **Listing / Order / Product** → **Audit Service**, **Notification Service** (async events).

This keeps the existing “engines + adapters” logic but places them inside a **Listing Orchestrator** microservice and clarifies which services own which data and how they communicate.

---

## Summary

- **Enable** microservice architecture by documenting principles, service list, ownership, and sync/async communication.
- **Recommend** these **key microservices**: API Gateway, Product & Catalog, Identity & Config, Channel Registry, Listing, Inventory, Order, Listing Orchestrator (with Channel Adapters), Notification, Audit—with optional Reporting and 3PL later.
- **Update** the architecture plan (new section + diagram + core components), design development history (new request/outcome), and optionally DATABASE_SCHEMA (table-to-service mapping).

