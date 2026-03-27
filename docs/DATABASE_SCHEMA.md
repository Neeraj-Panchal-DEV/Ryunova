# Database Schema – RyuNova Platform (Coffee Machine Product & Multi-Channel Listing Application)

**Application name:** RyuNova Platform. All database objects use the **`ryunova_`** prefix (e.g. `ryunova_users`, `ryunova_listing_status`).

**Purpose:** PostgreSQL schema for product master data, per-channel overrides, user management, OAuth, channel registry and credentials, listing lifecycle (list/remove/sold), **inventory management**, **order import and fulfillment** (integrated place with source channel info), image storage (S3), and audit of changes after first listing.

---

## Design review: LitCommerce and eChannelHub

This design is informed by [LitCommerce](https://litcommerce.com/multichannel-listing-tool/) and [eChannelHub](https://www.echannelhub.com/) so the application can deliver similar power with simple connect-and-manage across multiple marketplaces (including **Amazon**), plus automation and a single place for order fulfillment.

| Capability | LitCommerce / eChannelHub | This design |
|------------|---------------------------|-------------|
| **Multi-channel connect** | 20+ marketplaces (Amazon, eBay, Etsy, Shopify, Walmart, etc.); centralized dashboard | `ryunova_channels` registry; adapters per channel; **Amazon** included; extend via data only |
| **Listing automation** | Bulk edit, templates, rules, auto-publish, sync titles/prices | Listing engine + `ryunova_product_channel_override`; listing jobs; automation via jobs and rules (app logic) |
| **Inventory sync** | Near-instant sync (e.g. 15 min), oversell protection, threshold alerts | **Inventory module:** `ryunova_inventory_location`, `ryunova_inventory_level`; reserved qty; sync status; low-stock thresholds in config |
| **Order import** | Import orders from all channels into one dashboard; status tabs (Ready to Ship, Shipping, Completed) | **Order import module:** `ryunova_order` (source `channel_id`, `external_order_id`, status, fulfillment); `ryunova_order_line` linked to product/listing; single integrated place with source channel info |
| **Order fulfillment** | Centralized processing; routing to 3PL/FBA/warehouse; packing slips; shipping integration | `ryunova_order.fulfillment_status`, `ryunova_order.fulfillment_notes`; `ryunova_order_line` for line-level fulfillment; source channel retained for each order |
| **Unified experience** | One system, no re-platforming | Single DB: products, listings, inventory, orders; UI can show one list of orders with channel filter and fulfillment workflow |

The schema below adds **inventory management** and **order import/fulfillment** modules and includes **Amazon** as a channel so the application can support powerful automation and simple multi-marketplace management in one integrated place.

---

**Reference examples:**
- **Shopify (Coffee Machine Warehouse):** [Wega Polaris 2 Group – coffeemachinewarehouse.com.au](https://coffeemachinewarehouse.com.au/products/wega-polaris-2-group-low-cup-custom-bronze) – title, brand, sale/regular price, quantity, description, features/specs, multiple images, dimensions, power, collections/categories.
- **eBay:** [La Marzocco GB5 – eBay Australia](https://www.ebay.com.au/itm/177950330482) – item number, title, condition, price, postage, seller notes, brand, model, category hierarchy, item specifics (Water Source, Color, Features, Country of Origin), images.
- **Gumtree:** [Coffee machines listing – Gumtree](https://www.gumtree.com.au/web/listing/coffee-machines/1340526539) – title, price, location, description, category, images.
- **Used Coffee Gear:** [usedcoffeegear.com](https://usedcoffeegear.com) – dedicated website for placing used coffee machines and related products; products are listed/synced to the site as a channel.
- **Amazon:** Amazon marketplace(s); listings, inventory, and orders (FBA or merchant-fulfilled) via Amazon APIs; supported as a first-class channel alongside eBay, Shopify, etc.

---

## 1. Schema object list (PostgreSQL)

| Type    | Name |
|---------|------|
| Enum    | `ryunova_listing_status` |
| Enum    | `ryunova_product_condition` |
| Enum    | `ryunova_audit_entity_type` |
| Enum    | `ryunova_audit_action` |
| Enum    | `ryunova_order_status` (optional; or use VARCHAR) |
| Enum    | `ryunova_fulfillment_status` (optional; or use VARCHAR) |
| Table   | `ryunova_users` |
| Table   | `ryunova_user_roles` |
| Table   | `ryunova_oauth_tokens` |
| Table   | `ryunova_app_config` |
| Table   | `ryunova_user_settings` |
| Table   | `ryunova_notification_config` |
| Table   | `ryunova_channels` |
| Table   | `ryunova_channel_config` |
| Table   | `ryunova_channel_credentials` |
| Table   | `ryunova_categories` |
| Table   | `ryunova_brands` |
| Table   | `ryunova_channel_category_mapping` |
| Table   | `ryunova_product_master` |
| Table   | `ryunova_product_channel_list_flag` |
| Table   | `ryunova_product_channel_override` |
| Table   | `ryunova_product_image` |
| Table   | `ryunova_listing` |
| Table   | `ryunova_listing_history` |
| Table   | `ryunova_inventory_location` |
| Table   | `ryunova_inventory_level` |
| Table   | `ryunova_order` |
| Table   | `ryunova_order_line` |
| Table   | `ryunova_sale` |
| Table   | `ryunova_audit_log` |
| Table   | `ryunova_listing_job` |
| Index   | (see per-table) |
| Trigger | `ryunova_audit_trigger_product_master` (optional) |
| Trigger | `ryunova_audit_trigger_listing` (optional) |

---

## 2. Enums

```sql
CREATE TYPE ryunova_listing_status AS ENUM (
  'draft',      -- prepared, not yet sent to channel
  'pending',    -- job queued
  'listed',     -- live on channel
  'ended',      -- manually ended or expired
  'sold',       -- sold on channel
  'error'       -- last sync failed
);

CREATE TYPE ryunova_product_condition AS ENUM (
  'new',
  'used',
  'refurbished'
);

CREATE TYPE ryunova_audit_entity_type AS ENUM (
  'product_master',
  'product_channel_override',
  'listing'
);

CREATE TYPE ryunova_audit_action AS ENUM (
  'create',
  'update',
  'delete'
);

-- Optional enums for order/fulfillment (can use VARCHAR in app instead)
CREATE TYPE ryunova_order_status AS ENUM (
  'pending', 'imported', 'acknowledged', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded'
);

CREATE TYPE ryunova_fulfillment_status AS ENUM (
  'unfulfilled', 'partial', 'fulfilled', 'shipped', 'delivered', 'cancelled'
);
```

---

## 3. User management and OAuth (app auth)

### 3.1 `ryunova_users`

Stores application users (admin/operators who manage products and listings).

| Column       | Type                     | Constraints | Description |
|-------------|--------------------------|-------------|-------------|
| id          | UUID                     | PK, DEFAULT gen_random_uuid() | |
| email       | VARCHAR(255)             | NOT NULL, UNIQUE | Login identifier |
| display_name| VARCHAR(255)             | | |
| password_hash | VARCHAR(255)           | | Null if OAuth-only |
| avatar_s3_key | VARCHAR(512)           | | Optional; relative key under API `upload_dir` (same pattern as product media); public URL built with `api_public_url` + `media_url_prefix`. |
| is_platform_user | BOOLEAN             | NOT NULL, DEFAULT false | Platform operator (same concept as legacy **is_system_user**): all-org access, create organisations, invite to any org, PATCH admin user flags. At least one must remain. Canonical column name — use **is_platform_user**. |
| user_admin_access | BOOLEAN          | NOT NULL, DEFAULT false | Organisation user admin: may invite users only into orgs they belong to (`POST /admin/users/invite`). |
| email_verified_at | TIMESTAMPTZ       | | Required before login. |
| is_active   | BOOLEAN                  | NOT NULL, DEFAULT true | |
| created_at  | TIMESTAMPTZ              | NOT NULL, DEFAULT now() | |
| updated_at  | TIMESTAMPTZ              | NOT NULL, DEFAULT now() | |

Multi-tenant membership: **`ryunova_user_organisations`** (user_id, organisation_id). Organisation rows: **`ryunova_organisations`** — `name`, `slug` (unique), optional `description`, optional `logo_s3_key` (company logo, same URL pattern as avatars).

### 3.2 `ryunova_user_roles`

Roles for authorization (e.g. admin, operator, viewer).

| Column   | Type         | Constraints | Description |
|----------|--------------|-------------|-------------|
| id       | UUID         | PK, DEFAULT gen_random_uuid() | |
| user_id  | UUID         | NOT NULL, FK → ryunova_users(id) ON DELETE CASCADE | |
| role     | VARCHAR(64)  | NOT NULL    | e.g. 'admin', 'operator', 'viewer' |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() | |

Unique on (user_id, role).

### 3.3 `ryunova_oauth_tokens`

Stores OAuth tokens for **application** login (e.g. Google/Microsoft SSO). Not channel API tokens.

| Column        | Type         | Constraints | Description |
|---------------|--------------|-------------|-------------|
| id            | UUID         | PK, DEFAULT gen_random_uuid() | |
| user_id       | UUID         | NOT NULL, FK → ryunova_users(id) ON DELETE CASCADE | |
| provider      | VARCHAR(64)  | NOT NULL    | e.g. 'google', 'microsoft' |
| access_token  | TEXT         |             | Encrypted or ref to vault preferred |
| refresh_token | TEXT         |             | |
| expires_at    | TIMESTAMPTZ  |             | |
| created_at    | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |
| updated_at    | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |

Unique on (user_id, provider).

---

## 4. Application, system and user configuration

Configuration for application branding, system metadata, per-user settings, and how notifications are sent.

### 4.1 `ryunova_app_config`

Application- and system-level settings (name, copyright, license, developer details, version info, key references). Key-value style so new settings can be added without schema change. **Do not store secrets** here—store vault references or key names only.

| Column       | Type         | Constraints | Description |
|--------------|--------------|-------------|-------------|
| id           | UUID         | PK, DEFAULT gen_random_uuid() | |
| category     | VARCHAR(64)   | NOT NULL   | 'application' \| 'system' – groups config by scope. |
| config_key   | VARCHAR(128) | NOT NULL   | e.g. app_name, copyright, license, developer_name, developer_url, developer_contact, app_version, api_version, schema_version, build_number. For key refs: e.g. app_key_ref, encryption_key_ref (value = vault path or key identifier). |
| config_value | TEXT         |             | Value (plain text or JSON string). For secrets use a reference (e.g. vault path), not the actual key. |
| description  | VARCHAR(512)  |             | Optional description of the setting. |
| created_at   | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |
| updated_at   | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |

Unique on (category, config_key). Index on (category).

**Example keys (application):** app_name, copyright, license, developer_name, developer_url, developer_contact_email, app_version, api_version, schema_version, build_number, app_key_ref.

**Example keys (system):** timezone, default_locale, maintenance_mode, log_level.

### 4.2 `ryunova_user_settings`

Per-user preferences (display name override, theme, and notification preferences). Extensible key-value per user.

| Column      | Type         | Constraints | Description |
|-------------|--------------|-------------|-------------|
| id          | UUID         | PK, DEFAULT gen_random_uuid() | |
| user_id     | UUID         | NOT NULL, FK → ryunova_users(id) ON DELETE CASCADE | |
| setting_key | VARCHAR(128) | NOT NULL   | e.g. display_name_override, theme, notify_listing_success, notify_listing_failure, notify_sale, notification_email, digest_frequency. |
| setting_value| TEXT        |             | Value (plain or JSON). |
| created_at  | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |
| updated_at  | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |

Unique on (user_id, setting_key). Index on (user_id).

### 4.3 `ryunova_notification_config`

**How** to send notifications (transport and destination) and **when** (which events). System-level; multiple configs allowed (e.g. one for email, one for webhook).

| Column        | Type         | Constraints | Description |
|---------------|--------------|-------------|-------------|
| id            | UUID         | PK, DEFAULT gen_random_uuid() | |
| name          | VARCHAR(128) | NOT NULL   | e.g. 'Listing alerts (email)', 'Sales webhook'. |
| transport     | VARCHAR(64)  | NOT NULL   | 'email' \| 'smtp' \| 'webhook' \| 'in_app' \| 'sms' (extensible). |
| config        | JSONB        |             | Transport-specific config. Email/SMTP: smtp_host, smtp_port, from_address, auth_ref (vault ref for password). Webhook: webhook_url, headers (optional). In-app: optional target role or user list. |
| events        | JSONB        |             | Array of events that trigger this notification: e.g. ['listing_success', 'listing_failure', 'listing_ended', 'sale', 'job_failed']. |
| is_active     | BOOLEAN      | NOT NULL, DEFAULT true | |
| created_at    | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |
| updated_at    | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |

Index on (is_active).

**Example config (SMTP):** `{"smtp_host":"smtp.example.com","smtp_port":587,"from_address":"noreply@app.com","auth_ref":"vault:secret/smtp"}`.

**Example config (webhook):** `{"webhook_url":"https://...", "headers":{"X-API-Key":"ref:vault:..."}}`.

---

## 5. Channel registry and integration

### 5.1 `ryunova_channels`

Registry of sales channels. **New channels are added by inserting a row** (no schema change). Each channel has a unique `code` used by the application and adapters.

| Column       | Type         | Constraints | Description |
|-------------|--------------|-------------|-------------|
| id          | UUID         | PK, DEFAULT gen_random_uuid() | |
| code        | VARCHAR(64)  | NOT NULL, UNIQUE | Application identifier: e.g. 'ebay', 'facebook_marketplace', 'gumtree', 'shopify', 'usedcoffeegear' |
| name        | VARCHAR(255) | NOT NULL   | Display name |
| is_active   | BOOLEAN      | NOT NULL, DEFAULT true | |
| config_schema| JSONB       |             | Optional JSON schema for channel-specific config |
| created_at  | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |
| updated_at  | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |

**Known channels (examples):**

| code                   | name                  | Description |
|------------------------|------------------------|-------------|
| amazon                 | Amazon                | Amazon marketplace(s); listings, inventory, orders (FBA or merchant-fulfilled). |
| ebay                   | eBay                  | eBay Australia (or site-specific via config). |
| facebook_marketplace    | Facebook Marketplace  | Meta Facebook Marketplace. |
| gumtree                | Gumtree               | Gumtree Australia. |
| shopify                | Shopify               | Primary store (e.g. coffeemachinewarehouse.com.au). |
| usedcoffeegear         | Used Coffee Gear      | usedcoffeegear.com – website for placing used coffee machines and related products. |

Additional channels can be added by inserting into `ryunova_channels` and configuring `ryunova_channel_config` and `ryunova_channel_credentials`.

### 5.2 `ryunova_channel_config`

Per-channel integration settings (endpoints, rate limits, feature flags). No secrets here.

| Column     | Type         | Constraints | Description |
|------------|--------------|-------------|-------------|
| id         | UUID         | PK, DEFAULT gen_random_uuid() | |
| channel_id | UUID         | NOT NULL, FK → ryunova_channels(id) ON DELETE CASCADE, UNIQUE | |
| api_base_url | VARCHAR(512)|             | Base URL for channel API |
| config     | JSONB        |             | Channel-specific options (e.g. site_id for eBay, marketplace_id) |
| created_at | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |

### 5.3 `ryunova_channel_credentials`

Per-channel **authentication** (API keys, OAuth tokens). Store encrypted or reference to vault; avoid plaintext in DB if possible.

| Column        | Type         | Constraints | Description |
|---------------|--------------|-------------|-------------|
| id            | UUID         | PK, DEFAULT gen_random_uuid() | |
| channel_id    | UUID         | NOT NULL, FK → ryunova_channels(id) ON DELETE CASCADE, UNIQUE | |
| credential_type | VARCHAR(64) | NOT NULL   | e.g. 'oauth2', 'api_key' |
| credentials   | BYTEA or TEXT|             | Encrypted blob or vault reference |
| metadata      | JSONB        |             | e.g. token expiry, scope (non-secret) |
| created_at    | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |
| updated_at    | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |

---

## 6. Categories (optional taxonomy)

### 6.0 `ryunova_brands` (MVP1 / product master)

Lookup table for product brands. Products reference `brand_id` instead of a free-text brand column.

| Column     | Type         | Constraints | Description |
|------------|--------------|-------------|-------------|
| id         | UUID         | PK, DEFAULT gen_random_uuid() | |
| name       | VARCHAR(255) | NOT NULL, UNIQUE | Display name |
| slug       | VARCHAR(255) |             | Optional URL slug |
| description | TEXT        |             | Optional long-form notes |
| sort_order | INT          | DEFAULT 0  | |
| active     | BOOLEAN      | NOT NULL, DEFAULT true | When false, hidden from default list APIs / UI unless “include inactive”. |
| created_by_user_id | UUID | FK → ryunova_users(id) ON DELETE SET NULL | Who created the row |
| updated_by_user_id | UUID | FK → ryunova_users(id) ON DELETE SET NULL | Last editor |
| created_at | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |

### 6.1 `ryunova_categories`

Internal category tree; can be channel-agnostic or shared.

| Column     | Type         | Constraints | Description |
|------------|--------------|-------------|-------------|
| id         | UUID         | PK, DEFAULT gen_random_uuid() | |
| parent_id  | UUID         | FK → ryunova_categories(id) ON DELETE SET NULL | |
| name       | VARCHAR(255) | NOT NULL   | |
| slug       | VARCHAR(255) |             | |
| description | TEXT        |             | Optional long-form notes |
| sort_order | INT          | DEFAULT 0  | |
| active     | BOOLEAN      | NOT NULL, DEFAULT true | When false, hidden from default list APIs / UI unless “include inactive”. |
| created_by_user_id | UUID | FK → ryunova_users(id) ON DELETE SET NULL | Who created the row |
| updated_by_user_id | UUID | FK → ryunova_users(id) ON DELETE SET NULL | Last editor |
| created_at | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |

### 6.2 `ryunova_channel_category_mapping`

Maps internal category to channel-specific category ID/name (e.g. eBay category ID, Shopify collection ID).

| Column        | Type         | Constraints | Description |
|---------------|--------------|-------------|-------------|
| id            | UUID         | PK, DEFAULT gen_random_uuid() | |
| category_id   | UUID         | NOT NULL, FK → ryunova_categories(id) ON DELETE CASCADE | |
| channel_id    | UUID         | NOT NULL, FK → ryunova_channels(id) ON DELETE CASCADE | |
| external_id   | VARCHAR(255) |             | Channel’s category/collection ID |
| external_name | VARCHAR(255) |             | Channel’s category name |
| created_at    | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |
| updated_at    | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |

Unique on (category_id, channel_id).

---

## 7. Product master and per-channel overrides

### 7.1 `ryunova_product_master`

Single source of truth for each product (coffee machine or related). Aligned with Shopify/eBay/Gumtree/usedcoffeegear-style attributes where possible. **Which channels to list to** is stored in `ryunova_product_channel_list_flag` (Section 7.2) so new channels (e.g. usedcoffeegear) can be added without changing this table.

| Column             | Type           | Constraints | Description |
|--------------------|----------------|-------------|-------------|
| id                 | UUID           | PK, DEFAULT gen_random_uuid() | |
| sku                | VARCHAR(128)   | NOT NULL, UNIQUE | |
| title              | VARCHAR(500)   | NOT NULL   | Default title (can be overridden per channel) |
| description        | TEXT           |             | Default product description: **HTML** from the admin rich-text editor (TinyMCE), suitable for channel APIs (e.g. Shopify `body_html`). Plain text is still valid for legacy rows. |
| condition          | ryunova_product_condition | NOT NULL | new / used / refurbished |
| brand_id           | UUID           | FK → ryunova_brands(id) ON DELETE SET NULL | Lookup brand (e.g. Wega, La Marzocco) |
| model              | VARCHAR(255)   |             | |
| category_id        | UUID           | FK → ryunova_categories(id) ON DELETE SET NULL | |
| colour             | VARCHAR(255)   |             | Finish / colour (e.g. for listings and item specifics) |
| length_cm          | NUMERIC(12,3)  |             | Physical length in centimetres (nullable) |
| width_cm           | NUMERIC(12,3)  |             | Physical width in centimetres (nullable) |
| depth_cm           | NUMERIC(12,3)  |             | Physical depth in centimetres (nullable) |
| base_price         | NUMERIC(12,2)  | NOT NULL   | Master price (AUD or base currency) |
| compare_at_price   | NUMERIC(12,2)  |             | “Regular” price for display |
| quantity           | INT            | NOT NULL, DEFAULT 1 | Stock / quantity |
| attributes         | JSONB          |             | Flexible extra specs (power, features, channel-specific keys, etc.). **Colour** and **L/W/D** are stored in dedicated columns above. |
| status             | VARCHAR(32)    | NOT NULL, DEFAULT 'active' | e.g. active, draft, archived |
| active             | BOOLEAN        | NOT NULL, DEFAULT true | Catalog visibility: when false, omitted from default product lists unless “include inactive”. |
| created_at         | TIMESTAMPTZ    | NOT NULL, DEFAULT now() | |
| updated_at         | TIMESTAMPTZ    | NOT NULL, DEFAULT now() | |
| created_by_user_id | UUID           | FK → ryunova_users(id) ON DELETE SET NULL | |
| updated_by_user_id | UUID         | FK → ryunova_users(id) ON DELETE SET NULL | Last editor (API sets on create/update/image upload). |

**API read models** may include derived `created_by_label` / `updated_by_label` (user `display_name` only; no email) for admin UI; not stored in this table.

### 7.2 `ryunova_product_channel_list_flag`

**Per-channel “list to this channel” flag.** One row per product per channel when the product is enabled for listing on that channel. Adding a new channel (e.g. usedcoffeegear) only requires a row in `ryunova_channels` and then rows here—no change to `ryunova_product_master`.

| Column      | Type         | Constraints | Description |
|-------------|--------------|-------------|-------------|
| id          | UUID         | PK, DEFAULT gen_random_uuid() | |
| product_id  | UUID         | NOT NULL, FK → ryunova_product_master(id) ON DELETE CASCADE | |
| channel_id  | UUID         | NOT NULL, FK → ryunova_channels(id) ON DELETE CASCADE | |
| list_enabled| BOOLEAN      | NOT NULL, DEFAULT true | When true, product is eligible to be listed on this channel (e.g. ebay, shopify, usedcoffeegear). |
| created_at  | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |
| updated_at  | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |

Unique on (product_id, channel_id). Index on (channel_id, list_enabled).

**Example channels:** ebay, facebook_marketplace, gumtree, shopify, **usedcoffeegear** (usedcoffeegear.com). Future channels: add row to `ryunova_channels` and use this table for per-product enablement.

### 7.3 `ryunova_product_channel_override`

Per-channel overrides so each product can have channel-specific title, price, discount, description, and extra attributes (e.g. [eBay item specifics](https://www.ebay.com.au/itm/177950330482), or usedcoffeegear.com-specific fields). One row per product per channel when overrides exist.

| Column           | Type           | Constraints | Description |
|------------------|----------------|-------------|-------------|
| id               | UUID           | PK, DEFAULT gen_random_uuid() | |
| product_id       | UUID           | NOT NULL, FK → ryunova_product_master(id) ON DELETE CASCADE | |
| channel_id       | UUID           | NOT NULL, FK → ryunova_channels(id) ON DELETE CASCADE | |
| listing_title   | VARCHAR(500)   |             | Override title for this channel |
| description     | TEXT           |             | Override description |
| price_override   | NUMERIC(12,2)  |             | Override price (null = use master) |
| discount_percent | NUMERIC(5,2)   |             | Optional discount % for this channel |
| compare_at_price_override | NUMERIC(12,2) | | |
| custom_attributes| JSONB          |             | Channel-specific fields (e.g. eBay item specifics, Gumtree location) |
| created_at       | TIMESTAMPTZ   | NOT NULL, DEFAULT now() | |
| updated_at       | TIMESTAMPTZ   | NOT NULL, DEFAULT now() | |

Unique on (product_id, channel_id).

---

## 8. Image storage (S3)

### 8.1 `ryunova_product_image`

Stores **image and video** metadata; actual files live in local upload dir or S3. Application resolves `s3_bucket` + `s3_key` to URL (or uses pre-signed URLs). Exactly one row per product should have **`is_cover`** true (enforced in app on upload/PATCH); the cover is listed **first** in API responses and used as the **listing / channel primary** asset.

| Column      | Type         | Constraints | Description |
|-------------|--------------|-------------|-------------|
| id          | UUID         | PK, DEFAULT gen_random_uuid() | |
| product_id  | UUID         | NOT NULL, FK → ryunova_product_master(id) ON DELETE CASCADE | |
| sort_order  | INT          | NOT NULL, DEFAULT 0 | Gallery order (after cover) |
| media_type  | VARCHAR(16)  | NOT NULL, DEFAULT 'image' | `image` or `video` |
| is_cover    | BOOLEAN      | NOT NULL, DEFAULT false | Primary media for listings and product list thumb |
| s3_bucket   | VARCHAR(255) | NOT NULL   | e.g. 'cmw-product-images' |
| s3_key      | VARCHAR(512) | NOT NULL   | Object key (e.g. 'products/{product_id}/{filename}.jpg') |
| filename    | VARCHAR(255) |             | Original filename |
| content_type| VARCHAR(128) |             | e.g. image/jpeg, video/mp4 |
| size_bytes  | BIGINT       |             | |
| created_at  | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |

**S3 layout example:**  
- Bucket: e.g. `cmw-product-images`  
- Key pattern: `products/{product_id}/{uuid}.{ext}` or `products/{year}/{month}/{product_id}_{sort_order}.{ext}` for organisation.

---

## 9. Listings and lifecycle (list / remove / sold)

### 9.1 `ryunova_listing`

One row per product per channel representing current listing state. Records **when listed**, **when removed (ended)**, and **when sold** (or link to `ryunova_sale`).

| Column             | Type           | Constraints | Description |
|--------------------|----------------|-------------|-------------|
| id                 | UUID           | PK, DEFAULT gen_random_uuid() | |
| product_id         | UUID           | NOT NULL, FK → ryunova_product_master(id) ON DELETE CASCADE | |
| channel_id         | UUID           | NOT NULL, FK → ryunova_channels(id) ON DELETE CASCADE | |
| external_listing_id| VARCHAR(255)   |             | Channel’s listing/item ID (e.g. eBay item number) |
| status             | ryunova_listing_status | NOT NULL, DEFAULT 'draft' | |
| listed_at          | TIMESTAMPTZ    |             | **Date/time first listed** on this channel |
| ended_at           | TIMESTAMPTZ    |             | **Date/time listing ended** (removed or expired) |
| sold_at            | TIMESTAMPTZ    |             | **Date/time sold** on this channel |
| last_synced_at     | TIMESTAMPTZ    |             | Last successful sync with channel |
| error_message      | TEXT           |             | Last error (e.g. rate limit, validation) |
| payload_snapshot   | JSONB          |             | Optional snapshot of payload sent to channel |
| created_at         | TIMESTAMPTZ    | NOT NULL, DEFAULT now() | |
| updated_at         | TIMESTAMPTZ    | NOT NULL, DEFAULT now() | |

Unique on (product_id, channel_id). Index on (channel_id, status), (external_listing_id, channel_id).

### 9.2 `ryunova_listing_history`

Historical record of listing events for audit and reporting: when listed, updated, ended, sold.

| Column       | Type            | Constraints | Description |
|--------------|-----------------|-------------|-------------|
| id           | UUID            | PK, DEFAULT gen_random_uuid() | |
| listing_id   | UUID            | NOT NULL, FK → ryunova_listing(id) ON DELETE CASCADE | |
| event        | VARCHAR(64)     | NOT NULL   | e.g. 'listed', 'updated', 'ended', 'sold' |
| occurred_at  | TIMESTAMPTZ     | NOT NULL, DEFAULT now() | |
| details      | JSONB           |             | Event payload (e.g. external_id, reason) |
| changed_by_user_id | UUID       | FK → ryunova_users(id) ON DELETE SET NULL | |

Index on (listing_id, occurred_at).

### 9.3 `ryunova_sale`

Record of a sale on a channel (optional; can be populated when an order is imported or by Sales engine). For full order and fulfillment workflow use `ryunova_order` and `ryunova_order_line` (Section 11).

---

## 10. Inventory management module

Single view of stock per product (and optionally per location); supports sync to channels and oversell protection. Aligned with [LitCommerce](https://litcommerce.com/blog/multichannel-inventory-management/) and [eChannelHub](https://www.echannelhub.com/) style inventory sync.

### 10.1 `ryunova_inventory_location`

Optional: warehouses, FBA, or “default” so inventory can be tracked per location. If not used, use a single default location.

| Column     | Type         | Constraints | Description |
|------------|--------------|-------------|-------------|
| id         | UUID         | PK, DEFAULT gen_random_uuid() | |
| code       | VARCHAR(64)  | NOT NULL, UNIQUE | e.g. 'default', 'warehouse_1', 'fba_au' |
| name       | VARCHAR(255) | NOT NULL   | Display name |
| is_default | BOOLEAN      | NOT NULL, DEFAULT false | One location should be default for simple setups |
| is_active  | BOOLEAN      | NOT NULL, DEFAULT true | |
| created_at | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |
| updated_at | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |

### 10.2 `ryunova_inventory_level`

Stock level per product (and optionally per location). **Available** = quantity − reserved; used for channel sync and oversell protection.

| Column        | Type         | Constraints | Description |
|---------------|--------------|-------------|-------------|
| id            | UUID         | PK, DEFAULT gen_random_uuid() | |
| product_id    | UUID         | NOT NULL, FK → ryunova_product_master(id) ON DELETE CASCADE | |
| location_id   | UUID         | FK → ryunova_inventory_location(id) ON DELETE CASCADE | Null = default/single location |
| quantity      | INT          | NOT NULL, DEFAULT 0 | On-hand quantity |
| reserved      | INT          | NOT NULL, DEFAULT 0 | Reserved for open orders (so available = quantity − reserved) |
| low_stock_threshold | INT     |             | Alert when quantity ≤ this (can also live in app_config) |
| last_synced_at | TIMESTAMPTZ |             | Last sync to channels |
| created_at    | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |
| updated_at    | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |

Unique on (product_id, location_id). Index on (product_id), (location_id). Application can enforce available ≥ 0 and decrement on order import / reserve.

---

## 11. Order import and fulfillment module

**Integrated place with source channel info for order fulfillment.** Orders imported from any channel (Amazon, eBay, Shopify, etc.) share the same tables so fulfillment can be managed in one place while retaining channel and external IDs.

### 11.1 `ryunova_order`

One row per order imported from a channel. Source channel and external ID are always stored for traceability and sync-back (e.g. shipping confirmation).

| Column            | Type           | Constraints | Description |
|-------------------|----------------|-------------|-------------|
| id                | UUID           | PK, DEFAULT gen_random_uuid() | |
| channel_id        | UUID           | NOT NULL, FK → ryunova_channels(id) ON DELETE RESTRICT | **Source channel** (Amazon, eBay, Shopify, etc.) |
| external_order_id | VARCHAR(255)   | NOT NULL   | Channel’s order ID (e.g. Amazon order ID, eBay order ID) |
| order_date        | TIMESTAMPTZ    | NOT NULL   | Order date from channel |
| status            | VARCHAR(64)    | NOT NULL, DEFAULT 'imported' | e.g. pending, imported, acknowledged, processing, shipped, delivered, cancelled, refunded |
| fulfillment_status| VARCHAR(64)    | NOT NULL, DEFAULT 'unfulfilled' | unfulfilled, partial, fulfilled, shipped, delivered, cancelled |
| total_amount      | NUMERIC(12,2)  |             | Order total |
| currency          | VARCHAR(3)     |             | e.g. AUD |
| customer_email    | VARCHAR(255)   |             | From channel |
| shipping_address  | JSONB          |             | Full or normalized address for fulfillment |
| source_channel_info | JSONB        |             | **Source channel info:** raw or normalized payload from channel (order reference, channel-specific flags, FBA vs merchant, etc.) for fulfillment and sync-back |
| imported_at       | TIMESTAMPTZ    | NOT NULL, DEFAULT now() | When we imported into this system |
| fulfillment_notes | TEXT           |             | Internal notes for fulfillment |
| shipped_at        | TIMESTAMPTZ    |             | When order was shipped (if applicable) |
| tracking_number   | VARCHAR(255)   |             | For sync-back to channel |
| created_at        | TIMESTAMPTZ    | NOT NULL, DEFAULT now() | |
| updated_at        | TIMESTAMPTZ    | NOT NULL, DEFAULT now() | |

Unique on (channel_id, external_order_id). Index on (channel_id), (status), (fulfillment_status), (order_date).

### 11.2 `ryunova_order_line`

Line items for each order; link to product and optionally listing for inventory and channel sync.

| Column             | Type         | Constraints | Description |
|--------------------|--------------|-------------|-------------|
| id                 | UUID         | PK, DEFAULT gen_random_uuid() | |
| order_id           | UUID         | NOT NULL, FK → ryunova_order(id) ON DELETE CASCADE | |
| product_id         | UUID         | NOT NULL, FK → ryunova_product_master(id) ON DELETE RESTRICT | |
| listing_id         | UUID         | FK → ryunova_listing(id) ON DELETE SET NULL | Listing on source channel (if known) |
| external_line_id   | VARCHAR(255) |             | Channel’s line item ID (for sync-back) |
| quantity           | INT          | NOT NULL, DEFAULT 1 | |
| unit_price         | NUMERIC(12,2)|             | Price at time of order |
| fulfillment_status | VARCHAR(64)  | NOT NULL, DEFAULT 'unfulfilled' | unfulfilled, fulfilled, shipped, cancelled |
| created_at         | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |
| updated_at         | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |

Index on (order_id), (product_id). On order import, reserve or decrement `ryunova_inventory_level` (and update `ryunova_listing`/product quantity on channel if applicable). The `ryunova_sale` table (9.3) can be populated from order import for backward compatibility or simple sale tracking per listing.

---

## 12. Audit of changes (after first listing)

### 12.1 `ryunova_audit_log`

Records **who** changed **what** and **when** for ryunova_product_master, ryunova_product_channel_override, and ryunova_listing (e.g. price/title changes after a listing is live). Ensures a record of every change post first listing.

| Column           | Type             | Constraints | Description |
|------------------|------------------|-------------|-------------|
| id               | UUID             | PK, DEFAULT gen_random_uuid() | |
| entity_type      | ryunova_audit_entity_type | NOT NULL   | product_master, product_channel_override, listing |
| entity_id        | UUID             | NOT NULL   | PK of the affected row |
| action           | ryunova_audit_action      | NOT NULL   | create, update, delete |
| old_values       | JSONB            |             | Snapshot of changed columns before (null for create) |
| new_values       | JSONB            |             | Snapshot of changed columns after (null for delete) |
| changed_at       | TIMESTAMPTZ      | NOT NULL, DEFAULT now() | |
| changed_by_user_id | UUID           | FK → ryunova_users(id) ON DELETE SET NULL | |
| ip_address       | INET             |             | Optional |
| user_agent       | VARCHAR(512)     |             | Optional |

Index on (entity_type, entity_id, changed_at), (changed_by_user_id, changed_at).

**Implementation:** Application (or trigger) writes to `ryunova_audit_log` on every update/delete (and optionally create) for `ryunova_product_master`, `ryunova_product_channel_override`, and `ryunova_listing`. Only store changed fields in `old_values`/`new_values` to keep size manageable.

---

## 13. Listing jobs (queue persistence, optional)

### 13.1 `ryunova_listing_job`

If listing jobs are persisted in DB (in addition to or instead of Redis), use this table for durability and visibility.

| Column     | Type         | Constraints | Description |
|------------|--------------|-------------|-------------|
| id         | UUID         | PK, DEFAULT gen_random_uuid() | |
| product_id | UUID         | NOT NULL, FK → ryunova_product_master(id) ON DELETE CASCADE | |
| channel_id | UUID         | NOT NULL, FK → ryunova_channels(id) ON DELETE CASCADE | |
| job_type   | VARCHAR(64)  | NOT NULL   | e.g. 'list', 'update', 'delist' |
| status     | VARCHAR(32)  | NOT NULL, DEFAULT 'pending' | pending, processing, completed, failed |
| payload    | JSONB        |             | |
| result     | JSONB        |             | Response or error |
| created_at | TIMESTAMPTZ  | NOT NULL, DEFAULT now() | |
| processed_at | TIMESTAMPTZ |             | |

Index on (status, created_at).

---

## 14. Indexes summary

| Table                    | Index (logical) |
|--------------------------|-----------------|
| ryunova_users            | UNIQUE(email) |
| ryunova_user_roles       | (user_id, role) UNIQUE; FK user_id |
| ryunova_oauth_tokens     | (user_id, provider) UNIQUE |
| ryunova_app_config       | (category, config_key) UNIQUE; (category) |
| ryunova_user_settings    | (user_id, setting_key) UNIQUE; (user_id) |
| ryunova_notification_config | (is_active) |
| ryunova_channels         | UNIQUE(code) |
| ryunova_channel_config   | UNIQUE(channel_id) |
| ryunova_channel_credentials | UNIQUE(channel_id) |
| ryunova_categories       | (parent_id); index slug if used in lookups |
| ryunova_brands           | UNIQUE(name) |
| ryunova_channel_category_mapping | (category_id, channel_id) UNIQUE |
| ryunova_product_master   | UNIQUE(sku); (category_id); (brand_id); (status); (active); (created_by_user_id); (updated_by_user_id) |
| ryunova_product_channel_list_flag | (product_id, channel_id) UNIQUE; (channel_id, list_enabled) |
| ryunova_product_channel_override | (product_id, channel_id) UNIQUE |
| ryunova_product_image    | (product_id, sort_order) |
| ryunova_listing          | (product_id, channel_id) UNIQUE; (channel_id, status); (external_listing_id, channel_id) |
| ryunova_listing_history  | (listing_id, occurred_at) |
| ryunova_inventory_location | UNIQUE(code) |
| ryunova_inventory_level  | (product_id, location_id) UNIQUE; (product_id); (location_id) |
| ryunova_order            | (channel_id, external_order_id) UNIQUE; (channel_id); (status); (fulfillment_status); (order_date) |
| ryunova_order_line       | (order_id); (product_id) |
| ryunova_sale             | (listing_id); (sold_at) |
| ryunova_audit_log        | (entity_type, entity_id, changed_at); (changed_by_user_id, changed_at) |
| ryunova_listing_job      | (status, created_at); (product_id, channel_id) |

---

## 15. CRUD operations (mapping to schema)

| Operation | Primary tables | Notes |
|-----------|----------------|-------|
| **Product CRUD** | ryunova_product_master, ryunova_product_image, ryunova_product_channel_list_flag, ryunova_product_channel_override | Create/read/update/delete product; which channels to list to via ryunova_product_channel_list_flag; overrides optional per channel. |
| **User CRUD** | ryunova_users, ryunova_user_roles | Create/read/update/delete users and roles. |
| **App/system config** | ryunova_app_config | Key-value for application name, copyright, license, developer, version, key refs. |
| **User settings** | ryunova_user_settings | Per-user preferences and notification options. |
| **Notification config** | ryunova_notification_config | How to send (transport + config) and which events trigger notifications. |
| **OAuth (app login)** | ryunova_users, ryunova_oauth_tokens | Link SSO provider to user; refresh tokens. |
| **Channel management** | ryunova_channels, ryunova_channel_config, ryunova_channel_credentials | Add/edit channels; store credentials securely. |
| **Listing lifecycle** | ryunova_listing, ryunova_listing_history, ryunova_sale | List → update status + listed_at; end → ended_at; sold → sold_at + sale row. |
| **Inventory management** | ryunova_inventory_location, ryunova_inventory_level | Locations (optional); per-product (and per-location) quantity, reserved, low_stock_threshold; sync to channels; reserve on order. |
| **Order import** | ryunova_order, ryunova_order_line | Import orders from any channel; store channel_id + external_order_id + source_channel_info; one integrated place for fulfillment. |
| **Order fulfillment** | ryunova_order, ryunova_order_line | Update fulfillment_status, shipped_at, tracking_number; sync-back to channel; decrement/reserve ryunova_inventory_level. |
| **Audit** | ryunova_audit_log | Insert-only on changes to ryunova_product_master, ryunova_product_channel_override, ryunova_listing. |
| **Images** | ryunova_product_image | CRUD; file operations in S3 (upload/delete object); DB stores s3_bucket, s3_key. |

---

## 16. Extensibility: adding new channels

To add a new channel (e.g. usedcoffeegear.com or any future marketplace):

1. **Insert** a row into `ryunova_channels` with a unique `code` (e.g. `usedcoffeegear`) and `name`.
2. **Configure** `ryunova_channel_config` (api_base_url, config JSONB) and `ryunova_channel_credentials` (auth) for that channel.
3. **Use** `ryunova_product_channel_list_flag` to set which products list to the new channel; no new columns on `ryunova_product_master`.
4. **Optionally** add rows to `ryunova_product_channel_override` for channel-specific title, price, or attributes.
5. **Implement** a channel adapter in application code that reads from `ryunova_channels`, `ryunova_channel_config`, and `ryunova_channel_credentials` and writes listing state to `ryunova_listing` and `ryunova_listing_history`.

No PostgreSQL schema migration is required for new channels; only data and application code.

---

## 17. Document history

| Date       | Change |
|------------|--------|
| 2026-03-12 | Initial schema: product master, overrides, users, OAuth, channels, credentials, listings, history, sales, audit, images (S3), listing jobs. |
| 2026-03-12 | Review: added channel **usedcoffeegear** (usedcoffeegear.com); normalised list flags into **product_channel_list_flag** so additional channels can be added without schema change; documented known channels and extensibility. |
| 2026-03-12 | Added **application and system configuration** tables: **app_config** (name, copyright, license, developer details, version info, key refs), **user_settings** (per-user preferences and notification settings), **notification_config** (transport, how to send, which events trigger notifications). |
| 2026-03-12 | **Design review (LitCommerce & eChannelHub):** Redesigned for powerful automation and simple connect-and-manage across marketplaces. Added **Amazon** to channels. Added **inventory management module** (inventory_location, inventory_level; quantity, reserved, low_stock_threshold). Added **order import module** (order, order_line) with source channel_id, external_order_id, source_channel_info for **integrated order fulfillment** from all channels. |
| 2026-03-12 | **Application name RyuNova Platform:** All database objects (tables, enums, triggers) use the **`ryunova_`** prefix (e.g. ryunova_users, ryunova_listing_status). |
