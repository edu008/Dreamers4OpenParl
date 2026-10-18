-- 0002_one_active_label.sql – höchstens ein aktives Label je Geschäft und Tag
--
-- 0001 erlaubte ein aktives Label je (affair_id, tag_id, input_hash, prompt_version). Damit konnten
-- zwei Aufgaben (z. B. classify:aps und reclassify:<tag>) oder ein alter und ein neuer Text dasselbe
-- Tag gleichzeitig aktiv halten, oder der Worker scheiterte beim Schreiben an einer UniqueViolation.
-- Jetzt gilt: Wer ein Label schreibt, setzt das bisher aktive Label desselben Tags auf superseded,
-- egal aus welcher Aufgabe es stammt (ARCHITEKTUR.md 3.2).

DROP INDEX affair_tags_active_uq;
CREATE UNIQUE INDEX affair_tags_active_uq ON affair_tags (affair_id, tag_id) WHERE status = 'active';
