-- =============================================================================
--  Bidsa / Etimad-Plus  —  PostgreSQL schema (v1)
--  Migration target for the former static-JSON "etimad-plus-viewer" project.
--
--  Design pillars:
--    1. Faithful port of the Python `classify_tender` lifecycle logic
--       (scripts/export_warehouse.py) into a reusable IMMUTABLE SQL function
--       driven by CURRENT_TIMESTAMP through a VIEW.
--    2. Normalised relational core (tenders / awards / lookups) replacing the
--       64-shard SHA-256 JSON scheme — Postgres B-tree/GIN indexing makes the
--       hand-rolled sharding obsolete.
--    3. AI + RAG layer: pgvector embeddings on tenders and a chunked company
--       knowledge base, plus structured columns for multi-agent outputs.
--    4. Multi-tenant SaaS isolation via Row-Level Security on org-scoped tables.
--
--  Money is stored as exact integer *halalas* (BIGINT), mirroring the script's
--  Decimal(str(value)) -> halalas projection. Never use FLOAT for currency.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 0. Extensions
-- -----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- uuid_generate_v4()
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- trigram GIN for ILIKE / fuzzy title search
CREATE EXTENSION IF NOT EXISTS vector;       -- pgvector: embedding column + HNSW/IVFFlat


-- =============================================================================
-- 1. LIFECYCLE LOGIC  (port of classify_tender / normalized_status)
-- =============================================================================

-- Mirror of Python normalized_status(): NFC-normalise, lowercase, strip Arabic
-- diacritics (U+064B..U+065F, U+0670), collapse whitespace. IMMUTABLE so it can
-- be used inside generated columns and expression indexes.
CREATE OR REPLACE FUNCTION norm_status(v text)
RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT btrim(
             regexp_replace(
               regexp_replace(
                 lower(normalize(coalesce(v, ''), NFC)),
                 '[\u064b-\u065f\u0670]', '', 'g'  -- strip harakat + superscript alef (== Python)
               ),
               '\s+', ' ', 'g'
             )
           );
$$;

-- Direct port of classify_tender(). Precedence and evidence rules match the
-- Python source exactly:
--   award proof  ->  cancelled  ->  awarded status  ->  awarding status
--   ->  deadline vs as_of  ->  examination  ->  open  ->  unknown
-- `p_as_of` is a parameter (kept IMMUTABLE); the VIEW below injects
-- CURRENT_TIMESTAMP so lifecycle is always evaluated "as of now".
CREATE OR REPLACE FUNCTION classify_tender_lifecycle(
    p_status              text,
    p_status_id           integer,
    p_deadline            timestamptz,
    p_award_state         text,
    p_has_winners         boolean,
    p_win_amount_halalas  bigint,
    p_bids_count          integer,
    p_as_of               timestamptz
)
RETURNS text
LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
DECLARE
    s                text := norm_status(p_status);
    -- status-term sets copied verbatim from export_warehouse.py
    awarded_re     constant text := '(awarded|award announced|تمت الترسية|تم الترسية|مرساة)';
    awarding_re    constant text := '(awarding stage|award stage|مرحلة الترسية|تحت الترسية)';
    cancelled_re   constant text := '(cancelled|canceled|withdrawn|ملغ|الغيت|سحبت)';
    examination_re constant text := '(closed|expired|evaluation|examination|under review|مغلق|منته|فحص|تقييم|فتح العروض|تحت المراجعة)';
    open_re        constant text := '(active|open|published|نشط|مفتوح)';
    bid_zero         boolean;
    future_no_proof  boolean;
    award_announced  boolean;
BEGIN
    -- bid_count_is_zero(): no bid evidence at all
    bid_zero := coalesce(p_bids_count, 0) = 0
                AND NOT coalesce(p_has_winners, false)
                AND p_win_amount_halalas IS NULL;

    -- future_deadline_without_award_proof(): forbidden "future deadline, no proof"
    future_no_proof := p_deadline IS NOT NULL
                       AND p_deadline >= p_as_of
                       AND p_win_amount_halalas IS NULL
                       AND bid_zero;

    -- award_is_announced()
    award_announced := (
           p_award_state = 'announced'
        OR coalesce(p_has_winners, false)
        OR p_win_amount_halalas IS NOT NULL
        OR s ~ awarded_re
    ) AND NOT future_no_proof;

    IF award_announced           THEN RETURN 'awarded';     END IF;   -- award_evidence
    IF s ~ cancelled_re          THEN RETURN 'cancelled';   END IF;   -- official_status_cancelled
    IF s ~ awarded_re            THEN RETURN 'awarded';     END IF;   -- official_status_awarded
    IF s ~ awarding_re           THEN RETURN 'awarding';    END IF;   -- awarding_stage

    IF p_deadline IS NOT NULL THEN
        IF p_deadline >= p_as_of AND NOT (s ~ examination_re)
            THEN RETURN 'open';          -- deadline_not_elapsed
            ELSE RETURN 'examination';   -- deadline_elapsed_or_terminal_status
        END IF;
    END IF;

    IF s ~ examination_re                       THEN RETURN 'examination'; END IF;
    IF s ~ open_re OR p_status_id = 4           THEN RETURN 'open';        END IF;
    RETURN 'unknown';                            -- insufficient_lifecycle_evidence
END;
$$;

-- Generic updated_at touch trigger
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;


-- =============================================================================
-- 2. LOOKUP TABLES  (agencies / companies / activities / tender types / regions)
--    Public reference data — shared across all tenants, so NOT under RLS.
-- =============================================================================

CREATE TABLE regions (
    id           SERIAL PRIMARY KEY,
    name_ar      text NOT NULL,
    name_en      text,
    UNIQUE (name_ar)
);

CREATE TABLE agencies (
    id            BIGSERIAL PRIMARY KEY,
    external_code text UNIQUE,              -- Etimad AgencyCode
    name_ar       text NOT NULL,
    name_en       text,
    region_id     integer REFERENCES regions(id) ON DELETE SET NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE activities (
    id            BIGSERIAL PRIMARY KEY,
    external_id   text UNIQUE,             -- TenderActivityId
    name_ar       text NOT NULL,
    name_en       text
);

CREATE TABLE tender_types (
    id            BIGSERIAL PRIMARY KEY,
    external_id   text UNIQUE,             -- TenderTypeId
    name_ar       text NOT NULL,
    name_en       text
);

-- Companies act as bidders AND winners; keyed by Commercial Registration number.
CREATE TABLE companies (
    id            BIGSERIAL PRIMARY KEY,
    cr_number     text UNIQUE,             -- Commercial Registration (may be null in raw data)
    name_ar       text NOT NULL,
    name_en       text,
    created_at    timestamptz NOT NULL DEFAULT now()
);


-- =============================================================================
-- 3. CORE: TENDERS  (+ AI output columns + embedding)
-- =============================================================================

-- Constrain lifecycle values to the exact set produced by classify_tender.
CREATE TYPE tender_lifecycle AS ENUM
    ('open', 'awarding', 'examination', 'awarded', 'cancelled', 'unknown');

CREATE TABLE tenders (
    id                  uuid PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- ---- Identity & taxonomy -------------------------------------------------
    reference_number    text NOT NULL UNIQUE,          -- Etimad reference (the shard key in old design)
    title               text NOT NULL,                 -- record.name
    description         text,
    agency_id           bigint REFERENCES agencies(id)     ON DELETE SET NULL,
    activity_id         bigint REFERENCES activities(id)   ON DELETE SET NULL,
    type_id             bigint REFERENCES tender_types(id) ON DELETE SET NULL,
    region_id           integer REFERENCES regions(id)     ON DELETE SET NULL,
    tender_category_hint text,                          -- raw "tenderCategory" (e.g. products/services)

    -- ---- Official status & lifecycle inputs ---------------------------------
    status_text         text,                           -- raw official status string
    status_id           integer,                        -- Etimad statusId (4 == active)
    deadline            timestamptz,                    -- submission / offer deadline
    -- Snapshot of the lifecycle at ingest time (audit); live value comes from the VIEW.
    lifecycle_snapshot  tender_lifecycle,
    lifecycle_basis     text,                           -- tenderCategoryBasis evidence string

    -- ---- Money (exact integer halalas) & bidding ----------------------------
    win_amount_halalas  bigint CHECK (win_amount_halalas IS NULL OR win_amount_halalas >= 0),
    currency            char(3) DEFAULT 'SAR',
    bids_count          integer NOT NULL DEFAULT 0 CHECK (bids_count >= 0),
    has_winners         boolean NOT NULL DEFAULT false, -- denormalised for the lifecycle function

    -- ---- Provenance / freshness (kept as JSONB for auditability) ------------
    component_details   jsonb,                          -- componentDetails blob
    freshness           jsonb,                          -- _freshness
    evidence            jsonb,                          -- _evidence
    provenance          jsonb,                          -- _provenance (sources / fieldSources)
    raw_path            text,                           -- RAW capture path
    parser_version      text,
    source_snapshot_id  text,                           -- manifest run id (e.g. run_123_1)

    -- ---- AI / multi-agent outputs -------------------------------------------
    ai_summary                  text,       -- agent: concise Arabic executive summary
    mandatory_requirements      jsonb,      -- agent: extracted must-have eligibility criteria
    local_content_requirements  jsonb,      -- agent: Saudi local-content / نطاقات obligations
    risk_flags                  jsonb,      -- agent: risk signals [{code, severity, note}]
    ai_model                    text,       -- model id used for the outputs above
    ai_processed_at             timestamptz,

    -- ---- RAG embedding (OpenAI text-embedding-3-small = 1536 dims) -----------
    embedding           vector(1536),

    -- ---- Full-text search (generated tsvector over title + description) ------
    search_vector       tsvector GENERATED ALWAYS AS (
                            setweight(to_tsvector('simple', coalesce(title, '')), 'A') ||
                            setweight(to_tsvector('simple', coalesce(description, '')), 'B') ||
                            setweight(to_tsvector('simple', coalesce(reference_number, '')), 'C')
                        ) STORED,

    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_tenders_updated
    BEFORE UPDATE ON tenders
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =============================================================================
-- 4. AWARDS  (1:1 with a tender)  + winners / bids detail
-- =============================================================================

CREATE TABLE awards (
    id                  uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    tender_id           uuid NOT NULL UNIQUE REFERENCES tenders(id) ON DELETE CASCADE,
    win_amount_halalas  bigint CHECK (win_amount_halalas IS NULL OR win_amount_halalas >= 0),
    currency            char(3) DEFAULT 'SAR',
    award_state         text,                           -- e.g. 'announced'
    award_mode          text,                           -- awardMode
    award_completeness  text,                           -- awardCompleteness
    award_announced_at  timestamptz,                    -- awardAnnouncedAt
    money_consistency   jsonb,                          -- {status, deltaHalalas, method,...}
    award_groups        jsonb,                          -- groups / awardGroups (multi-lot awards)
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- Winning offers (one award can have several winners across lots/groups).
CREATE TABLE award_winners (
    id                  BIGSERIAL PRIMARY KEY,
    award_id            uuid NOT NULL REFERENCES awards(id) ON DELETE CASCADE,
    company_id          bigint REFERENCES companies(id) ON DELETE SET NULL,
    award_halalas       bigint CHECK (award_halalas IS NULL OR award_halalas >= 0),
    group_ref           text,                           -- lot / group identifier
    rank                integer,
    raw                 jsonb                           -- untouched original winner object
);

-- Full bid ledger (allBids) — every participating offer, winners or not.
CREATE TABLE tender_bids (
    id                  BIGSERIAL PRIMARY KEY,
    tender_id           uuid NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    company_id          bigint REFERENCES companies(id) ON DELETE SET NULL,
    bid_halalas         bigint CHECK (bid_halalas IS NULL OR bid_halalas >= 0),
    is_winner           boolean NOT NULL DEFAULT false,
    raw                 jsonb
);


-- =============================================================================
-- 5. SaaS TENANCY  (organizations / users)
-- =============================================================================

CREATE TABLE organizations (
    id            uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    name          text NOT NULL,
    cr_number     text UNIQUE,           -- the tenant's own company, if any
    plan          text NOT NULL DEFAULT 'trial',
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id               uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id  uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email            text NOT NULL UNIQUE,   -- enable the citext extension and switch to CITEXT for case-insensitive uniqueness
    full_name        text,
    role             text NOT NULL DEFAULT 'member',    -- owner / admin / member
    created_at       timestamptz NOT NULL DEFAULT now()
);


-- =============================================================================
-- 6. AI BID MANAGER  —  Company Knowledge Base (RAG)
--    Documents are tenant-owned; embeddings live on the CHUNK table (RAG best
--    practice: one embedding per retrievable passage, not per whole file).
-- =============================================================================

CREATE TABLE knowledge_documents (
    id               uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id  uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    uploaded_by      uuid REFERENCES users(id) ON DELETE SET NULL,
    title            text NOT NULL,
    doc_type         text,                 -- 'company_profile' | 'past_proposal' | 'certificate' | ...
    source_filename  text,
    storage_url      text,                 -- object-store pointer (S3/GCS)
    mime_type        text,
    metadata         jsonb,
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE knowledge_chunks (
    id               uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id      uuid NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    organization_id  uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE, -- denormalised for RLS + filtered ANN
    chunk_index      integer NOT NULL,
    content          text NOT NULL,
    token_count      integer,
    embedding        vector(1536),         -- semantic search vector
    created_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

-- AI-generated bid proposals (the multi-agent Bid Manager output), tenant-scoped.
CREATE TABLE bid_proposals (
    id               uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id  uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    tender_id        uuid NOT NULL REFERENCES tenders(id) ON DELETE CASCADE,
    created_by       uuid REFERENCES users(id) ON DELETE SET NULL,
    status           text NOT NULL DEFAULT 'draft',   -- draft / final / submitted
    proposal_content text,                            -- generated proposal body
    compliance_matrix jsonb,                          -- requirement -> evidence mapping
    ai_model         text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, tender_id)
);

CREATE TRIGGER trg_bid_proposals_updated
    BEFORE UPDATE ON bid_proposals
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- =============================================================================
-- 7. LIVE LIFECYCLE VIEW  (replicates the "as_of" dynamic classification)
--    Query this instead of the tenders table when you need the *current*
--    open/awarding/examination/awarded/cancelled/unknown state.
-- =============================================================================

CREATE OR REPLACE VIEW tenders_live AS
SELECT
    t.*,
    classify_tender_lifecycle(
        t.status_text, t.status_id, t.deadline, a.award_state,
        t.has_winners, t.win_amount_halalas, t.bids_count,
        CURRENT_TIMESTAMP
    ) AS lifecycle_status,
    CASE WHEN t.deadline IS NOT NULL
         THEN GREATEST(0, floor(EXTRACT(EPOCH FROM (t.deadline - CURRENT_TIMESTAMP)) / 86400))::int
    END AS days_remaining,
    (t.deadline IS NOT NULL
        AND t.deadline >= CURRENT_TIMESTAMP
        AND t.deadline <  CURRENT_TIMESTAMP + interval '7 days')  AS within_7,
    (t.deadline IS NOT NULL
        AND t.deadline >= CURRENT_TIMESTAMP
        AND t.deadline <  CURRENT_TIMESTAMP + interval '30 days') AS within_30
FROM tenders t
LEFT JOIN awards a ON a.tender_id = t.id;


-- =============================================================================
-- 8. INDEXES
-- =============================================================================

-- ---- 8a. B-tree: identity, foreign keys, common filters ---------------------
-- reference_number already has a UNIQUE b-tree from the table definition.
CREATE INDEX idx_tenders_agency     ON tenders (agency_id);
CREATE INDEX idx_tenders_activity   ON tenders (activity_id);
CREATE INDEX idx_tenders_type       ON tenders (type_id);
CREATE INDEX idx_tenders_region     ON tenders (region_id);
CREATE INDEX idx_tenders_deadline   ON tenders (deadline);
CREATE INDEX idx_tenders_status_id  ON tenders (status_id);
-- Partial index: the hot path is "still-biddable" tenders with a future deadline.
CREATE INDEX idx_tenders_open_deadline ON tenders (deadline)
    WHERE deadline IS NOT NULL AND win_amount_halalas IS NULL;

CREATE INDEX idx_awards_tender          ON awards (tender_id);
CREATE INDEX idx_award_winners_award    ON award_winners (award_id);
CREATE INDEX idx_award_winners_company  ON award_winners (company_id);
CREATE INDEX idx_tender_bids_tender     ON tender_bids (tender_id);
CREATE INDEX idx_tender_bids_company    ON tender_bids (company_id);

CREATE INDEX idx_kdocs_org      ON knowledge_documents (organization_id);
CREATE INDEX idx_kchunks_doc    ON knowledge_chunks (document_id);
CREATE INDEX idx_kchunks_org    ON knowledge_chunks (organization_id);
CREATE INDEX idx_proposals_org  ON bid_proposals (organization_id);
CREATE INDEX idx_proposals_tender ON bid_proposals (tender_id);
CREATE INDEX idx_users_org      ON users (organization_id);

-- ---- 8b. GIN: full-text + trigram fuzzy search ------------------------------
CREATE INDEX idx_tenders_fts        ON tenders USING gin (search_vector);
-- Trigram index powers ILIKE '%...%' substring matches on Arabic titles.
CREATE INDEX idx_tenders_title_trgm ON tenders USING gin (title gin_trgm_ops);
-- JSONB containment queries on AI outputs (e.g. risk_flags @> '[{"code":"..."}]').
CREATE INDEX idx_tenders_risk_flags ON tenders USING gin (risk_flags);

-- ---- 8c. Vector ANN: HNSW for embeddings ------------------------------------
-- HNSW chosen over IVFFlat: better recall/latency and no ivfflat "train after
-- N rows" step, which suits a continuously-growing SaaS dataset. Cosine ops
-- match normalised OpenAI embeddings. Tune m / ef_construction per data size.
CREATE INDEX idx_tenders_embedding_hnsw
    ON tenders USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_kchunks_embedding_hnsw
    ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);


-- =============================================================================
-- 9. ROW-LEVEL SECURITY  (multi-tenant isolation)
--    Public procurement data (tenders/awards/lookups) is readable by everyone;
--    tenant assets (knowledge base, proposals) are isolated per organization.
--    The app must SET app.current_org = '<org-uuid>' per request/connection.
-- =============================================================================

ALTER TABLE knowledge_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_chunks    ENABLE ROW LEVEL SECURITY;
ALTER TABLE bid_proposals       ENABLE ROW LEVEL SECURITY;

CREATE POLICY org_isolation_kdocs ON knowledge_documents
    USING (organization_id = current_setting('app.current_org', true)::uuid);
CREATE POLICY org_isolation_kchunks ON knowledge_chunks
    USING (organization_id = current_setting('app.current_org', true)::uuid);
CREATE POLICY org_isolation_proposals ON bid_proposals
    USING (organization_id = current_setting('app.current_org', true)::uuid);

COMMIT;

-- =============================================================================
--  Example queries
-- =============================================================================
--  Live "open" board:
--     SELECT reference_number, title, days_remaining
--     FROM tenders_live WHERE lifecycle_status = 'open' ORDER BY deadline;
--
--  Semantic search over tenders (query embedding bound as $1):
--     SELECT reference_number, title, 1 - (embedding <=> $1) AS score
--     FROM tenders ORDER BY embedding <=> $1 LIMIT 20;
--
--  RAG retrieval scoped to a tenant (RLS already filters org):
--     SELECT content FROM knowledge_chunks ORDER BY embedding <=> $1 LIMIT 8;
-- =============================================================================
