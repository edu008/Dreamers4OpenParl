-- 0004_review_undo.sql – Review-Aktion undo
--
-- POST /v1/reviews nimmt den letzten Entscheid zu einem Thema zurück (PRD F9) und protokolliert das
-- als eigene Zeile in reviews. Die Labels ändern dabei nur ihren Status, gelöscht wird nichts.

ALTER TABLE reviews DROP CONSTRAINT reviews_action_check;
ALTER TABLE reviews ADD CONSTRAINT reviews_action_check
    CHECK (action IN ('confirm', 'reject', 'change', 'add', 'undo'));
