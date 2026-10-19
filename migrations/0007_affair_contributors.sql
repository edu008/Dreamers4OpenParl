-- 0007_affair_contributors.sql – Beteiligte an Geschäften aus contributors.ndjson.gz
--
-- Urheberinnen und Urheber, Mitunterzeichnende, Kommissionen und weitere Beteiligte mit Rolle und
-- Partei, damit der Evaluationsbericht die Qualität je Partei zeigt (Bias-Prüfung, CHALLENGE.md).
-- Wie die übrigen Quelltabellen ohne Fremdschlüssel. Anders als sie ohne raw: Der Originaldatensatz
-- wäre bei 1.4 Mio. Zeilen rund 1.5 GB, gebraucht werden nur Rolle und Partei.

CREATE TABLE affair_contributors (
    id                bigint PRIMARY KEY,
    affair_id         bigint,  -- leer bei Beteiligten an News und Sitzungen
    type              text,  -- person oder group
    role              text,  -- role_harmonized: author, cosign, speaker …
    role_external_id  text,  -- Rolle der Quelle; die Berichterstattung im Bund ist correspondent
    name              text,
    party             text,  -- party_harmonized_de
    position          integer,
    updated_at        timestamptz
);
CREATE INDEX affair_contributors_affair_idx ON affair_contributors (affair_id);
