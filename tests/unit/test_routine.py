from pathlib import Path

from parltopics.classify.queue import Job
from parltopics.classify.routine import ROUTINE_MODEL, match_routine
from parltopics.registry import load_registry

ROOT = Path(__file__).resolve().parents[2]


def _job(text: str, source: str = "title_only", task: str = "classify:aps") -> Job:
    return Job(
        affair_id=500,
        task=task,
        attempts=1,
        run_id=1,
        text=text,
        input_hash="h",
        language="de",
        source=source,
    )


def test_match_routine_classifies_oaths_naturalisations_elections_and_budgets():
    registry = load_registry(ROOT / "registry" / "tags.yaml")
    known = {t.tag_id: t for t in registry.tags}

    # 1. Vereidigung -> aps:1.2.4 (Parlament)
    oath_res = match_routine(
        _job("[Metadaten: Kanton/Gremium: BS]\nVereidigung neuer Mitglieder des Grossen Rates"),
        known,
    )
    assert oath_res is not None
    r_pass, r_out = oath_res
    assert r_pass.model_version == ROUTINE_MODEL
    assert [lbl.tag_id for lbl in r_pass.labels] == ["aps:1.2.4"]
    assert r_pass.labels[0].evidence == "Vereidigung neuer Mitglieder des Grossen Rates"
    assert r_pass.labels[0].evidence_verified is True
    assert r_out.summary_de == "Vereidigung neuer Mitglieder des Grossen Rates"

    # 2. Einbürgerung -> aps:7.1.5 (Staatsangehörigkeit)
    nat_res = match_routine(
        _job(
            "[Metadaten: Kanton/Gremium: BS | Typ: Naturalisation]\n"
            "106 Aufnahmen (42 Gesuche) in das Bürgerrecht der Stadt Basel"
        ),
        known,
    )
    assert nat_res is not None
    assert [lbl.tag_id for lbl in nat_res[0].labels] == ["aps:7.1.5"]

    # 3a. Parlaments-/Kommissionswahl & Rücktritt -> aps:1.2.4 (Parlament)
    elec_res = match_routine(
        _job("115 Ersatzwahl in die Kommission für Raumplanung für den Rest der Amtsdauer"),
        known,
    )
    assert elec_res is not None
    assert [lbl.tag_id for lbl in elec_res[0].labels] == ["aps:1.2.4"]

    # 3b. Richter-/Staatsanwaltswahl -> aps:1.2.6 (Judikative)
    judge_res = match_routine(
        _job("Wahl eines Mitglieds des Obergerichts für den Rest der Amtsperiode"),
        known,
    )
    assert judge_res is not None
    assert [lbl.tag_id for lbl in judge_res[0].labels] == ["aps:1.2.6"]

    # 4. Jahresrechnung / Voranschlag -> aps:8.2.1 (Budget)
    budget_res = match_routine(
        _job("Voranschlag 2026 und Aufgaben- und Finanzplan 2027-2029"),
        known,
    )
    assert budget_res is not None
    assert [lbl.tag_id for lbl in budget_res[0].labels] == ["aps:8.2.1"]


def test_match_routine_skips_policy_interventions():
    registry = load_registry(ROOT / "registry" / "tags.yaml")
    known = {t.tag_id: t for t in registry.tags}

    # Politische Vorstösse zu Einbürgerung, Budget oder Wahlen müssen ans LLM gehen
    assert (
        match_routine(
            _job(
                "[Metadaten: Kanton/Gremium: ZH | Typ: Motion]\n"
                "Motion betreffend Einbürgerung von Jugendlichen der zweiten Generation"
            ),
            known,
        )
        is None
    )
    assert (
        match_routine(
            _job("Interpellation: Auswirkungen der Spardebatte auf das Budget 2026"),
            known,
        )
        is None
    )
    assert (
        match_routine(
            _job("Änderung des Gesetzes über die politischen Rechte (Ersatzwahl)"),
            known,
        )
        is None
    )
