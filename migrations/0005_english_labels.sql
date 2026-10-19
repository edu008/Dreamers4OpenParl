-- 0005_english_labels.sql – Englisch als Sprache der Tag-Bezeichnungen
--
-- Alle Sprachen eines Tags hängen an derselben tag_id (registry/tags.yaml, ADR 0007). Neben DE, FR,
-- IT und RM gibt es jetzt englische Namen (pref_label.en) für Suche und Schnittstellen.

ALTER TABLE tag_labels DROP CONSTRAINT tag_labels_language_check;
ALTER TABLE tag_labels ADD CONSTRAINT tag_labels_language_check
    CHECK (language IN ('de', 'fr', 'it', 'rm', 'en'));
