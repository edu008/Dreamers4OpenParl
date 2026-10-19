-- 0006_rule_stage.sql – Stufe `rule` für Labels aus Regeln für Routinegeschäfte
--
-- Vereidigungen, Rücktritte, Einbürgerungen, Budgets und Rechnungen bekommen ihr Thema per Regel
-- aus dem Titel, ohne Modellaufruf (classify/rules.py). Die Stufe macht sie von Modell-Labels
-- unterscheidbar.

ALTER TABLE classification_jobs DROP CONSTRAINT classification_jobs_stage_check;
ALTER TABLE classification_jobs ADD CONSTRAINT classification_jobs_stage_check
    CHECK (stage IN ('8b', '70b', 'rule'));
ALTER TABLE affair_tags DROP CONSTRAINT affair_tags_stage_check;
ALTER TABLE affair_tags ADD CONSTRAINT affair_tags_stage_check
    CHECK (stage IN ('8b', '70b', 'human', 'rule'));
