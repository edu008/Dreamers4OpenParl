-- 0002_wiki_skos.sql – SKOS-Registry, Kurzzusammenfassungen, Seitenbaum und Navigationssuche
-- (PRD 0.4: 7.2, 7.3, 7.9, 7.10; ADR 0007 und 0008)
--
-- Ergänzt 0001, ohne bestehende Tabellen zu ändern. Die Spalten von tags werden so befüllt:
--   name_de/fr/it/rm  = pref_label je Sprache
--   desc_de/fr/it     = definition je Sprache (eine Definition auf Rätoromanisch bleibt in der YAML)
--   aliases           = alt_labels aller Sprachen
--   match_text        = pref_label, alt_labels und hidden_labels zusammen (Trigramm-Suche)
--   parent_id         = Eltern-Code bei APS-Tags (ihr einziges broader), bei Ad-hoc-Tags NULL
-- Vollständig nach SKOS stehen Labels, Beziehungen und Curia-Vista-Mappings in eigenen Tabellen.
-- skos:narrower wird nicht gespeichert, sondern aus broader abgeleitet.

-- Registry nach SKOS ----------------------------------------------------------------------------

CREATE TABLE tag_labels (
    id        bigserial PRIMARY KEY,
    tag_id    text NOT NULL REFERENCES tags (tag_id),
    kind      text NOT NULL CHECK (kind IN ('pref', 'alt', 'hidden')),
    language  text CHECK (language IN ('de', 'fr', 'it', 'rm')),  -- hidden_labels ohne Sprache
    label     text NOT NULL CHECK (label <> ''),
    CHECK ((kind = 'hidden') = (language IS NULL))
);
CREATE UNIQUE INDEX tag_labels_uq ON tag_labels (tag_id, kind, language, label) NULLS NOT DISTINCT;
CREATE UNIQUE INDEX tag_labels_pref_uq ON tag_labels (tag_id, language) WHERE kind = 'pref';
CREATE INDEX tag_labels_trgm_idx ON tag_labels USING gin (label gin_trgm_ops);

-- broader und related; pro Paar nur eine Beziehung, damit beide disjunkt bleiben (SKOS).
-- related ist symmetrisch und wird so gespeichert, wie es in der Registry steht.
CREATE TABLE tag_relations (
    tag_id     text NOT NULL REFERENCES tags (tag_id) DEFERRABLE INITIALLY DEFERRED,
    target_id  text NOT NULL REFERENCES tags (tag_id) DEFERRABLE INITIALLY DEFERRED,
    relation   text NOT NULL CHECK (relation IN ('broader', 'related')),
    PRIMARY KEY (tag_id, target_id),
    CHECK (tag_id <> target_id)
);
CREATE INDEX tag_relations_target_idx ON tag_relations (target_id, relation);

-- exactMatch, closeMatch, broadMatch auf Curia-Vista-Sachbereiche (ersetzt die Mapping-CSV).
-- Die Registry erlaubt derzeit nur curia:; die Tabelle nimmt jedes Präfix an.
CREATE TABLE tag_mappings (
    tag_id      text NOT NULL REFERENCES tags (tag_id),
    target      text NOT NULL CHECK (target ~ '^[a-z]+:[A-Za-z0-9.-]+$'),
    match_type  text NOT NULL CHECK (match_type IN ('exact', 'close', 'broad')),
    PRIMARY KEY (tag_id, target)
);
CREATE INDEX tag_mappings_target_idx ON tag_mappings (target);

-- Kurzzusammenfassung je Geschäft ----------------------------------------------------------------

-- Ein Satz aus Stufe 2 der Klassifikation (summary_de), ohne eigenen Modellaufruf.
-- Wie bei affair_tags: nie löschen, ältere Fassungen auf superseded setzen.
CREATE TABLE affair_summaries (
    id              bigserial PRIMARY KEY,
    affair_id       bigint NOT NULL REFERENCES affairs (id),
    language        text NOT NULL DEFAULT 'de' CHECK (language IN ('de', 'fr', 'it', 'rm')),
    summary         text NOT NULL CHECK (char_length(summary) BETWEEN 1 AND 300),
    task            text NOT NULL,
    stage           text NOT NULL CHECK (stage IN ('8b', '70b', 'human')),
    model_version   text NOT NULL,
    prompt_version  text NOT NULL,
    input_hash      text NOT NULL,
    run_id          integer REFERENCES classification_runs (id),
    status          text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'superseded')),
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX affair_summaries_active_uq
    ON affair_summaries (affair_id, language) WHERE status = 'active';

-- Seitenbaum (ParlWiki) -------------------------------------------------------------------------

-- Eine Zeile pro Seite: heart, Bereich, Kapitel, Tag-Seite oder Querschnittsseite (Ad-hoc-Tag).
-- page_id ist 'heart' oder die tag_id. Status und Besitz folgen den Regeln der Jobs (PRD 7.7).
-- Frontmatter parents und children entstehen beim Export aus parent_id, linked_from und den Kindern.
-- Kennzahlen (stats, n_affairs) entstehen bei jedem Lauf; nur die Zusammenfassung hängt an
-- Schwellen. Phase 1 schreibt Zusammenfassungen auf Deutsch; mehrere Sprachen pro Seite brauchen
-- eine neue Migration.
CREATE TABLE wiki_pages (
    page_id              text PRIMARY KEY,
    kind                 text NOT NULL CHECK (kind IN ('heart', 'bereich', 'kapitel', 'tag', 'querschnitt')),
    tag_id               text UNIQUE REFERENCES tags (tag_id),
    parent_id            text REFERENCES wiki_pages (page_id) DEFERRABLE INITIALLY DEFERRED,
    linked_from          text[] NOT NULL DEFAULT '{}',  -- Kapitel, die eine Querschnittsseite verlinken
    redirect_to          text REFERENCES wiki_pages (page_id) DEFERRABLE INITIALLY DEFERRED,
    path                 text NOT NULL UNIQUE,  -- fest, z. B. tags/aps-6.1.9-digitalisierung.md
    title                text NOT NULL,
    language             text NOT NULL DEFAULT 'de' CHECK (language IN ('de', 'fr', 'it')),
    status               text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'pending', 'done', 'failed')),
    pending_changes      integer NOT NULL DEFAULT 0 CHECK (pending_changes >= 0),
    cited_label_removed  boolean NOT NULL DEFAULT false,
    n_affairs            integer NOT NULL DEFAULT 0 CHECK (n_affairs >= 0),
    stats                jsonb NOT NULL DEFAULT '{}',
    summary_short        text,
    summary_long         text,  -- Absatz aus den Aussagen, für Eltern-Prompts und Export
    statements           jsonb NOT NULL DEFAULT '[]',  -- Aussagen mit affair_ids und page_ids
    cited_affair_ids     bigint[] NOT NULL DEFAULT '{}',
    cited_page_ids       text[] NOT NULL DEFAULT '{}',
    summary_hash         text,
    input_hash           text,
    window_start         date,
    window_end           date,
    model_version        text,
    prompt_version       text,
    registry_version     text,
    review_status        text CHECK (review_status IN ('requested', 'approved', 'rejected')),
    reviewed_by          text,
    reviewed_at          timestamptz,
    worker_id            text,
    locked_at            timestamptz,
    attempts             integer NOT NULL DEFAULT 0,
    last_error           text,
    built_at             timestamptz,
    updated_at           timestamptz NOT NULL DEFAULT now(),
    CHECK ((kind = 'heart') = (page_id = 'heart')),
    CHECK ((kind = 'heart') = (tag_id IS NULL)),
    CHECK ((kind = 'heart') = (parent_id IS NULL)),
    CHECK (tag_id IS NULL OR tag_id = page_id),
    CHECK (redirect_to IS NULL OR redirect_to <> page_id),
    CHECK (status <> 'pending' OR (worker_id IS NOT NULL AND locked_at IS NOT NULL)),
    CHECK (window_start IS NULL OR window_end IS NULL OR window_start <= window_end)
);
CREATE INDEX wiki_pages_parent_idx ON wiki_pages (parent_id);
CREATE INDEX wiki_pages_open_idx ON wiki_pages (kind) WHERE status = 'open';
CREATE INDEX wiki_pages_pending_idx ON wiki_pages (locked_at) WHERE status = 'pending';
CREATE INDEX wiki_pages_cited_idx ON wiki_pages USING gin (cited_affair_ids);

-- Protokoll der Statuswechsel, wie job_events. run_key kennzeichnet einen Seitenlauf;
-- eine eigene Lauf-Tabelle folgt erst, wenn die Statusseite sie braucht.
CREATE TABLE wiki_page_events (
    id               bigserial PRIMARY KEY,
    page_id          text NOT NULL,
    from_status      text,
    to_status        text NOT NULL,
    reason           text,  -- z. B. threshold, max_age, child_changed, cited_label_removed, timeout
    summary_changed  boolean,
    run_key          text,
    worker_id        text,
    created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX wiki_page_events_page_idx ON wiki_page_events (page_id, created_at);

-- Navigationssuche ------------------------------------------------------------------------------

-- Ein Eintrag pro Suche: Suchweg, besuchte Knoten, Filter, Ergebnis. Ohne Treffer gibt es keine
-- Antwort (status <> 'ok' verlangt answer IS NULL). Ruft der Agent die Suche als Werkzeug auf,
-- verweist agent_run_id auf seinen Lauf.
CREATE TABLE search_runs (
    id               bigserial PRIMARY KEY,
    query            text NOT NULL,
    language         text,
    filters          jsonb,
    path             text[] NOT NULL DEFAULT '{}',
    visits           jsonb NOT NULL DEFAULT '[]',
    steps            integer NOT NULL DEFAULT 0 CHECK (steps >= 0),
    fallback_used    boolean NOT NULL DEFAULT false,
    affair_ids       bigint[] NOT NULL DEFAULT '{}',
    answer           text,
    statements       jsonb NOT NULL DEFAULT '[]',
    model_versions   jsonb NOT NULL DEFAULT '{}',  -- {"step": …, "answer": …}
    prompt_versions  jsonb NOT NULL DEFAULT '{}',
    agent_run_id     bigint REFERENCES agent_runs (id),
    duration_ms      integer,
    status           text NOT NULL CHECK (status IN ('ok', 'no_results', 'limit_reached', 'error')),
    created_at       timestamptz NOT NULL DEFAULT now(),
    CHECK (status <> 'ok' OR cardinality(affair_ids) > 0),
    CHECK (status = 'ok' OR answer IS NULL)
);
CREATE INDEX search_runs_created_idx ON search_runs (created_at);
