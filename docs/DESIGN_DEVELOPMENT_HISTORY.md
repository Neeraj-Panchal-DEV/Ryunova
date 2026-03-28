# RyuNova Platform – Design development history

This document sequences the main queries and requests that shaped the RyuNova Platform design. It is for future reference when extending or explaining how the system was developed.

**Application name:** RyuNova Platform  
**Primary use case:** Coffee machine (and related) products; business use for listing management, channel integration, order review and fulfillment.  
**Schema:** [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) (all objects use `ryunova_` prefix).

---

## Sequenced requests (chronological)

### 1. Design and architecture (high-level)

- **Request:** Design and architecture for an application to manage a coffee machine product database with auto-listing to eBay, Facebook Marketplace, Gumtree, and optionally others when a “list” flag is set; engines for listing, sales, and delisting; and admin interfaces. High-level framework first.
- **Outcome:** High-level architecture plan (product DB, listing/delist/sales engines, channel adapters, job queue). Tech stack confirmed: **FastAPI** (API), **Django** (frontend/admin UI), PostgreSQL, Celery/Redis (workers optional for later MVP).

---

### 2. Database schema (full)

- **Request:** Database schema document for the same app: product listing, CRUD, user management, OAuth, flexible channels, channel management (auth/integration), historical listings, S3 image storage, audit of changes after first listing, listing/removed/sold dates per channel, per-channel overrides (e.g. pricing), and a full list of PostgreSQL schema objects. References: Shopify (coffeemachinewarehouse.com.au), Gumtree, eBay.
- **Outcome:** Full schema document ([DATABASE_SCHEMA.md](DATABASE_SCHEMA.md)) with enums, tables (users, user_roles, oauth_tokens, channels, channel_config, channel_credentials, categories, channel_category_mapping, product_master, product_channel_list_flag, product_channel_override, product_image, listing, listing_history, sale, audit_log, listing_job), indexes, and CRUD mapping.

---

### 3. Add usedcoffeegear.com as a channel

- **Request:** Add usedcoffeegear.com as a channel and ensure the design allows adding more channels without schema change (normalised list flags).
- **Outcome:** usedcoffeegear added to known channels; list flags kept in **product_channel_list_flag** (one row per product per channel) so new channels require only data + adapter, no schema change. Extensibility section (Section 16) documents “adding new channels.”

---

### 4. Configuration tables (app, system, user, notifications)

- **Request:** Configuration tables for application and system: name, copyright, license, developer details, key (reference only), notification settings and how to send, version info; plus user settings.
- **Outcome:** **app_config** (category + config_key/value; application and system scope), **user_settings** (per-user key/value), **notification_config** (transport, config JSONB, events array). Document history and schema updated.

---

### 5. Review vs LitCommerce and eChannelHub; Amazon, inventory, order import/fulfillment

- **Request:** Review against LitCommerce and eChannelHub and extend design: add **Amazon**, **inventory management** (quantity, reserved, locations, low-stock, sync), **order import** from multiple channels with **source channel info** for **integrated order fulfillment** (order + order_line tables).
- **Outcome:** Design review table added to schema doc. **Amazon** in channels. **Inventory module:** inventory_location, inventory_level (quantity, reserved, low_stock_threshold). **Order import module:** order (channel_id, external_order_id, source_channel_info, fulfillment fields), order_line (product_id, listing_id, etc.) for single-place order review and fulfillment.

---

### 6. Application name RyuNova Platform – prefix all database objects

- **Request:** Use "RyuNova Platform" as the application name and apply **RyuNova as a prefix for all database objects** (tables, enums, etc.).
- **Outcome:** All schema objects in [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) use the **`ryunova_`** prefix (e.g. ryunova_users, ryunova_listing_status, ryunova_order, ryunova_order_line). Title and document history updated; architecture plan aligned (RyuNova Platform naming and scope).

---

## Key modules (as discussed)

| Module | Purpose |
|--------|--------|
| **Product master & overrides** | Single source of truth for products; per-channel list flags and overrides (title, price, etc.). |
| **User management & OAuth** | Users, roles, OAuth tokens for application login (e.g. SSO). |
| **App / system / user config & notifications** | App branding, version, keys (refs only); user settings; how and when to send notifications. |
| **Channel registry & integration** | Channels table + channel_config + channel_credentials; pluggable adapters (eBay, Facebook, Gumtree, Shopify, usedcoffeegear, Amazon, etc.). |
| **Categories** | Internal category tree; channel_category_mapping for channel-specific category IDs. |
| **Listing lifecycle** | listing, listing_history, sale; list → update status + listed_at; end → ended_at; sold → sold_at. |
| **Inventory management** | inventory_location, inventory_level; quantity, reserved, low_stock_threshold; sync to channels; reserve on order. |
| **Order import & fulfillment** | order, order_line; import from any channel; source_channel_info; single place for order review and fulfillment. |
| **Audit** | audit_log for changes to product_master, product_channel_override, listing (after first listing). |
| **Listing jobs** | listing_job (optional queue persistence); list/update/delist jobs. |
| **Images** | product_image; S3 storage (bucket/key in DB). |

The application can be extended (e.g. more channels, reporting, 3PL integration, shipping labels) without changing this core set of modules; new features add data or application logic rather than mandatory schema changes where possible.

---

## Related documents

| Document | Description |
|----------|-------------|
| [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) | Full PostgreSQL schema (RyuNova Platform; ryunova_-prefixed tables, enums, indexes, CRUD mapping). |
| [DEPLOYMENT_EC2_ALB.md](DEPLOYMENT_EC2_ALB.md) | Production deployment (EC2, ALB, GitHub Actions). |

---

*Last updated: 2026-03-12. Use this history to trace why certain tables, modules, or naming choices exist.*
