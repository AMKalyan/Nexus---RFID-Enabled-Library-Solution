# Data Dictionary

Database: PostgreSQL 16. Three schemas:

| Schema | Purpose | Application access |
|---|---|---|
| `legacy_ilms` | Simulated existing ILMS records (A-01) | `SELECT` only |
| `nexus` | Nexus application data | Read/write; `audit_log` is insert/select only |
| `staging` | Migration staging area | Read/write |

Conventions:
- Primary keys are `uuid` unless noted.
- Timestamps are `timestamptz` in UTC.
- Columns marked **PII** are masked in logs and exports for roles without the `member.pii.read` permission.

## legacy_ilms (read-only)

| Table | Column | Type | Notes |
|---|---|---|---|
| `catalogue` | `bib_no` | int PK | Legacy bibliographic number |
| | `title`, `author`, `publisher` | text | |
| | `isbn` | varchar(17) | |
| | `pub_year` | int | |
| `accession` | `acc_no` | varchar(20) PK | Legacy accession number |
| | `bib_no` | int FK → catalogue | |
| | `call_no`, `location` | text | |
| | `status` | varchar(10) | `AV`, `IS`, `LS`, `WD` |
| `borrower` | `borrower_id` | varchar(20) PK | |
| | `name`, `email`, `phone` | text | **PII** |
| | `category` | varchar(10) | `UG`, `PG`, `FAC`, `STAFF` |

## nexus: identity and access

| Table | Column | Type | Notes |
|---|---|---|---|
| `role` | `id`, `name` | uuid, text unique | `Admin`, `Librarian`, `CirculationClerk`, `Auditor`, `Patron` |
| `permission` | `code` | text PK | e.g. `circulation.checkout`, `admin.users.write` |
| `role_permission` | `role_id`, `permission_code` | composite PK | |
| `staff_user` | `id` | uuid PK | |
| | `username` | text unique | |
| | `display_name`, `email` | text | **PII** (email) |
| | `password_hash` | text | argon2id |
| | `smartcard_uid` | text unique null | **PII** |
| | `role_id` | uuid FK → role | |
| | `is_active` | bool | |
| | `last_login_at` | timestamptz | |
| `refresh_token` | `id`, `family_id`, `subject_type`, `subject_id`, `token_hash`, `expires_at`, `revoked_at` | | Only the hash is stored; rotated on every refresh; reuse of a revoked token revokes the whole family |

## nexus: catalogue and tagging

| Table | Column | Type | Notes |
|---|---|---|---|
| `bib` | `id` | uuid PK | |
| | `title` | text not null | |
| | `author`, `publisher`, `edition`, `subjects`, `language` | text | |
| | `isbn` | varchar(17) | Checksum validated (ISBN-10/13) |
| | `pub_year` | int | 1000–current year |
| | `source` | enum | `legacy`, `nexus`, `migration` |
| | `legacy_ref` | text null | `catalogue.bib_no` when mirrored from the legacy system |
| | `migration_batch_id` | uuid null | Set when created by a migration |
| | `search_tsv` | tsvector | Trigger-maintained; GIN index |
| `shelf` | `code` | text PK | e.g. `A-01` |
| | `name`, `location`, `call_no_from`, `call_no_to` | text | Call-number range expected on the shelf |
| `item` | `id` | uuid PK | |
| | `bib_id` | uuid FK → bib | |
| | `accession_no` | varchar(20) unique | |
| | `barcode` | varchar(32) unique | |
| | `call_no` | text | |
| | `shelf_code` | text FK → shelf | Home shelf |
| | `item_type` | enum | `lending`, `reference` |
| | `status` | enum | `available`, `on_loan`, `missing`, `in_repair`, `withdrawn` |
| | `price` | numeric(10,2) | |
| | `acquired_on` | date | |
| | `legacy_ref`, `migration_batch_id` | | As for `bib` |
| `rfid_tag` | `id` | uuid PK | |
| | `epc` | varchar(32) unique | Tag identifier |
| | `target_type` | enum | `item`, `member` |
| | `item_id` / `member_id` | uuid FK null | Exactly one is set, matching `target_type` |
| | `security_bit` | bool | true = not checked out (gate alarms) |
| | `status` | enum | `active`, `retired` |
| | `encoded_at`, `encoded_by` | timestamptz, uuid | |
| | `retired_at`, `retire_reason` | | Set when re-tagged or damaged |

Constraint: at most one `active` tag per item and per member (partial unique index).

## nexus: members and circulation

| Table | Column | Type | Notes |
|---|---|---|---|
| `circ_policy` | `category_code` | text PK | `UG`, `PG`, `FAC`, `STAFF` |
| | `loan_days`, `max_items`, `max_renewals` | int | |
| | `fine_per_day`, `fine_limit` | numeric(10,2) | Check-out blocked when open fines > `fine_limit` |
| | `can_borrow_reference` | bool | Default false |
| `member` | `id` | uuid PK | |
| | `card_no` | varchar(20) unique | |
| | `full_name`, `email`, `phone` | text | **PII** |
| | `category_code` | FK → circ_policy | |
| | `status` | enum | `active`, `blocked`, `expired` |
| | `block_reason` | text | |
| | `smartcard_uid` | text unique null | **PII** |
| | `password_hash` | text null | Patron OPAC login (argon2id) |
| | `notify_email`, `notify_sms`, `notify_print` | bool | Notification preferences (FR 09) |
| | `legacy_ref` | text null | `borrower.borrower_id` |
| `loan` | `id` | uuid PK | |
| | `item_id`, `member_id` | FK | Partial unique index: one open loan per item |
| | `issued_at`, `due_at`, `returned_at` | timestamptz | |
| | `renew_count` | int | |
| | `channel` | enum | `ui`, `ncip`, `sip2` |
| | `issued_by`, `returned_by` | uuid null | Staff user, or null for external channel |
| `fine` | `id`, `member_id`, `loan_id` | | |
| | `amount` | numeric(10,2) | |
| | `reason` | enum | `overdue`, `lost`, `damage`, `manual` |
| | `status` | enum | `open`, `paid`, `waived` |
| | `created_at`, `settled_at`, `settled_by` | | |

## nexus: devices, inventory and gate

| Table | Column | Type | Notes |
|---|---|---|---|
| `device` | `code` | text PK | e.g. `GATE-01`, `HH-01` |
| | `device_type` | enum | `staff_station`, `handheld`, `gate`, `smartcard_reader`, `printer`, `camera` |
| | `name`, `location`, `ip_address` | text, text, inet | Feeds the device configuration document (NFR 08) |
| | `config` | jsonb | e.g. linked camera for a gate |
| | `api_key_hash` | text | Device authentication |
| | `last_heartbeat_at`, `status` | | `online` / `offline` from heartbeat age |
| `device_event` | `id` | bigserial PK | |
| | `event_id` | uuid unique | Idempotency key supplied by the device |
| | `device_code`, `event_type`, `payload` (jsonb), `occurred_at`, `received_at`, `processed_at`, `result` | | |
| `inventory_session` | `id`, `shelf_code`, `device_code`, `started_by`, `started_at`, `closed_at`, `status` | | `open`, `closed` |
| `inventory_read` | `session_id`, `epc`, `item_id`, `result`, `read_at` | | `found`, `misplaced`, `unknown`; missing items are computed when the session closes |
| `gate_event` | `id`, `device_code`, `event_id`, `epc`, `item_id`, `accession_no`, `direction` | | |
| | `authorised`, `alarm`, `offline_decision` | bool | `offline_decision` = decided from the security bit while the API was unreachable |
| | `photo_jpeg` | bytea null | Mock CCTV snapshot |
| | `occurred_at`, `notified` | | |
| `footfall` | `device_code`, `hour`, `in_count`, `out_count` | | Aggregated hourly |

## nexus: notifications, audit, operations

| Table | Column | Type | Notes |
|---|---|---|---|
| `notification_outbox` | `id`, `channel` (`email`/`sms`/`print`), `recipient` (**PII**), `template`, `subject`, `body`, `related_type`, `related_id`, `status` (`queued`/`sent`/`failed`), `attempts`, `last_error`, `created_at`, `sent_at` | | Delivered by the worker through the configured adapter |
| `audit_log` | `id` | bigserial PK | Insert/select only for the app role |
| | `occurred_at`, `actor_type` (`staff`/`member`/`device`/`system`/`external`), `actor_id`, `action`, `entity_type`, `entity_id`, `details` (jsonb, masked), `ip`, `correlation_id` | | |
| `app_setting` | `key`, `value` (jsonb), `updated_at`, `updated_by` | | Runtime configuration (e.g. gate alert recipients) |
| `app_version` | `version`, `alembic_rev`, `installed_at`, `notes` | | Version history (FR 11) |
| `migration_batch` | `id`, `source_file`, `source_sha256`, `status` (`staged`/`validated`/`committed`/`rolled_back`/`failed`), `rows_total`, `rows_valid`, `rows_rejected`, `rows_duplicate`, `rows_committed`, `backup_file`, `created_by`, `created_at`, `committed_at` | | |

## staging

| Table | Column | Type | Notes |
|---|---|---|---|
| `import_row` | `batch_id`, `row_no` | composite PK | |
| | `raw` | jsonb | Original cells as read |
| | `accession_no`, `barcode`, `title`, `author`, `isbn`, `publisher`, `pub_year`, `edition`, `subjects`, `call_no`, `shelf_code`, `item_type`, `price`, `acquired_on` | | Normalised values |
| | `status` | enum | `pending`, `valid`, `rejected`, `duplicate` |
| | `reasons` | text[] | Reason codes, e.g. `TITLE_MISSING`, `ISBN_CHECKSUM`, `YEAR_RANGE`, `ACCESSION_FORMAT` |
| | `duplicate_of` | text | `row:<n>` within the file, or `item:<accession_no>` already in the catalogue |
