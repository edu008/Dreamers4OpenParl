-- 0001_init.sql – Grundschema von ParlTopics (PRD 0.3, Anhang C)
--
-- Quelltabellen haben keine Fremdschlüssel, damit der Bulk-Import nicht an einem einzelnen
-- fehlerhaften Verweis scheitert. raw enthält den Originaldatensatz. Die Felder der Quelltabellen
-- werden in M0 gegen die Exporte geprüft und bei Bedarf mit einer neuen Migration angepasst.
-- Bestehende Migrationen werden nie geändert.

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;  -- vorbereitet für Embeddings (ADR 0003), aktuell ungenutzt

-- Quelldaten ------------------------------------------------------------------------------------

CREATE TABLE bodies (
    id          bigint PRIMARY KEY,
    body_key    text NOT NULL UNIQUE,
    name        text,
    level       text,
    languages   text[] NOT NULL DEFAULT '{}',
    raw         jsonb NOT NULL,
    updated_at  timestamptz
);

CREATE TABLE affairs (
    id                  bigint PRIMARY KEY,
    body_key            text NOT NULL,
    body_id             bigint,
    number              text,
    external_id         text,
    title_de            text,
    title_fr            text,
    title_it            text,
    title_rm            text,
    type_harmonized_en  text,
    begin_date          date,
    url_external        text,
    raw                 jsonb NOT NULL,
    updated_at          timestamptz
);
CREATE INDEX affairs_body_date_idx ON affairs (body_key, begin_date);

CREATE TABLE affair_texts (
    id          bigint PRIMARY KEY,
    affair_id   bigint NOT NULL,
    text_type   text,
    language    text,
    format      text,
    text        text,
    raw         jsonb NOT NULL,
    updated_at  timestamptz
);
CREATE INDEX affair_texts_affair_idx ON affair_texts (affair_id);

CREATE TABLE affair_docs (
    id           bigint PRIMARY KEY,
    parent_type  text,
    parent_id    bigint,
    name         text,
    category     text,
    doc_date     date,
    language     text,
    text         text,
    raw          jsonb NOT NULL,
    updated_at   timestamptz
);
CREATE INDEX affair_docs_parent_idx ON affair_docs (parent_type, parent_id);

-- Aufbereitung ----------------------------------------------------------------------------------

CREATE TABLE affair_inputs (
    affair_id   bigint PRIMARY KEY REFERENCES affairs (id),
    text        text NOT NULL,
    language    text,
    source      text NOT NULL CHECK (source IN ('texts', 'first_doc', 'title_only')),
    input_hash  text NOT NULL,
    built_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE search_documents (
    affair_id   bigint PRIMARY KEY REFERENCES affairs (id),
    language    text,
    document    tsvector NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX search_documents_fts_idx ON search_documents USING gin (document);

-- Registry (Spiegel von registry/tags.yaml) -----------------------------------------------------

CREATE TABLE tags (
    tag_id                   text PRIMARY KEY,
    scheme                   text NOT NULL CHECK (scheme IN ('aps', 'adhoc')),
    status                   text NOT NULL CHECK (status IN ('proposed', 'active', 'merged', 'retired')),
    parent_id                text REFERENCES tags (tag_id) DEFERRABLE INITIALLY DEFERRED,
    merged_into              text REFERENCES tags (tag_id) DEFERRABLE INITIALLY DEFERRED,
    name_de                  text NOT NULL,
    name_fr                  text,
    name_it                  text,
    name_rm                  text,
    desc_de                  text NOT NULL,
    desc_fr                  text,
    desc_it                  text,
    aliases                  text[] NOT NULL DEFAULT '{}',
    unreviewed_translations  text[] NOT NULL DEFAULT '{}',
    match_text               text NOT NULL,
    content_hash             text NOT NULL,
    registry_version         text NOT NULL,
    updated_at               timestamptz NOT NULL DEFAULT now(),
    CHECK ((status = 'merged') = (merged_into IS NOT NULL))
);
CREATE INDEX tags_match_trgm_idx ON tags USING gin (match_text gin_trgm_ops);

CREATE TABLE registry_syncs (
    id                bigserial PRIMARY KEY,
    registry_version  text NOT NULL,
    file_hash         text NOT NULL,
    scheme_hashes     jsonb NOT NULL,
    synced_at         timestamptz NOT NULL DEFAULT now()
);

-- Steuerung -------------------------------------------------------------------------------------

CREATE TABLE classification_runs (
    id                serial PRIMARY KEY,
    kind              text NOT NULL CHECK (kind IN ('full', 'daily', 'adhoc', 'reclassify', 'eval')),
    task              text NOT NULL,
    params            jsonb NOT NULL DEFAULT '{}',
    registry_version  text NOT NULL,
    scheme_hash       text NOT NULL,
    prompt_version    text NOT NULL,
    started_at        timestamptz NOT NULL DEFAULT now(),
    finished_at       timestamptz,
    n_total           integer NOT NULL DEFAULT 0,
    n_done            integer NOT NULL DEFAULT 0,
    n_failed          integer NOT NULL DEFAULT 0,
    n_escalated       integer NOT NULL DEFAULT 0
);

CREATE TABLE classification_jobs (
    affair_id       bigint NOT NULL REFERENCES affairs (id),
    task            text NOT NULL,
    status          text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'pending', 'done', 'failed')),
    priority        integer NOT NULL DEFAULT 100,
    stage           text CHECK (stage IN ('8b', '70b')),
    input_hash      text,
    prompt_version  text,
    scheme_hash     text,
    run_id          integer REFERENCES classification_runs (id),
    worker_id       text,
    locked_at       timestamptz,
    attempts        integer NOT NULL DEFAULT 0,
    last_error      text,
    updated_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (affair_id, task),
    CHECK (status <> 'pending' OR (worker_id IS NOT NULL AND locked_at IS NOT NULL))
);
CREATE INDEX classification_jobs_queue_idx ON classification_jobs (task, status, priority);
CREATE INDEX classification_jobs_pending_idx ON classification_jobs (locked_at) WHERE status = 'pending';

CREATE TABLE job_events (
    id           bigserial PRIMARY KEY,
    affair_id    bigint NOT NULL,
    task         text NOT NULL,
    from_status  text,
    to_status    text NOT NULL,
    reason       text,
    run_id       integer,
    worker_id    text,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX job_events_job_idx ON job_events (affair_id, task, created_at);

-- Labels und Review -----------------------------------------------------------------------------

CREATE TABLE affair_tags (
    id                 bigserial PRIMARY KEY,
    affair_id          bigint NOT NULL REFERENCES affairs (id),
    tag_id             text NOT NULL REFERENCES tags (tag_id),
    scheme             text NOT NULL,
    confidence         numeric(4, 3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    evidence           text,
    evidence_verified  boolean NOT NULL DEFAULT false,
    task               text NOT NULL,
    stage              text NOT NULL CHECK (stage IN ('8b', '70b', 'human')),
    model_version      text NOT NULL,
    prompt_version     text NOT NULL,
    registry_version   text NOT NULL,
    input_hash         text NOT NULL,
    run_id             integer REFERENCES classification_runs (id),
    status             text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'rejected', 'superseded')),
    review_status      text CHECK (review_status IN ('confirmed', 'rejected', 'changed')),
    reviewed_by        text,
    reviewed_at        timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX affair_tags_active_uq
    ON affair_tags (affair_id, tag_id, input_hash, prompt_version) WHERE status = 'active';
CREATE INDEX affair_tags_tag_idx ON affair_tags (tag_id, affair_id) WHERE status = 'active';
CREATE INDEX affair_tags_affair_idx ON affair_tags (affair_id);

CREATE TABLE reviews (
    id             bigserial PRIMARY KEY,
    affair_id      bigint NOT NULL REFERENCES affairs (id),
    affair_tag_id  bigint REFERENCES affair_tags (id),
    action         text NOT NULL CHECK (action IN ('confirm', 'reject', 'change', 'add')),
    new_tag_id     text REFERENCES tags (tag_id),
    comment        text,
    user_name      text NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX reviews_affair_idx ON reviews (affair_id);

-- Vorschläge ------------------------------------------------------------------------------------

CREATE TABLE tag_proposals (
    id              bigserial PRIMARY KEY,
    group_key       text NOT NULL UNIQUE,
    name_de         text NOT NULL,
    desc_de         text,
    reason          text,
    recommendation  text CHECK (recommendation IN ('new', 'duplicate_of', 'child_of')),
    related_tag_id  text REFERENCES tags (tag_id),
    model_version   text,
    run_id          integer REFERENCES classification_runs (id),
    status          text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'pending', 'done')),
    decision        text CHECK (decision IN ('accepted', 'merged', 'rejected')),
    decided_by      text,
    decided_at      timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CHECK ((status = 'done') = (decision IS NOT NULL))
);

CREATE TABLE tag_proposal_raw (
    id             bigserial PRIMARY KEY,
    affair_id      bigint NOT NULL REFERENCES affairs (id),
    run_id         integer REFERENCES classification_runs (id),
    name_de        text NOT NULL,
    desc_de        text,
    reason         text,
    model_version  text NOT NULL,
    proposal_id    bigint REFERENCES tag_proposals (id),
    created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX tag_proposal_raw_ungrouped_idx ON tag_proposal_raw (run_id) WHERE proposal_id IS NULL;

CREATE TABLE tag_proposal_affairs (
    proposal_id  bigint NOT NULL REFERENCES tag_proposals (id),
    affair_id    bigint NOT NULL REFERENCES affairs (id),
    PRIMARY KEY (proposal_id, affair_id)
);

-- Agent -----------------------------------------------------------------------------------------

CREATE TABLE agent_runs (
    id                bigserial PRIMARY KEY,
    kind              text NOT NULL CHECK (kind IN ('search', 'adhoc')),
    query             text NOT NULL,
    tool_calls        jsonb NOT NULL DEFAULT '[]',
    answer            text,
    cited_affair_ids  bigint[] NOT NULL DEFAULT '{}',
    model_version     text NOT NULL,
    prompt_version    text NOT NULL,
    duration_ms       integer,
    status            text NOT NULL CHECK (status IN ('ok', 'no_results', 'limit_reached', 'error')),
    created_at        timestamptz NOT NULL DEFAULT now()
);
