"""Review-Entscheide schreiben (PRD F9): bestätigen, verwerfen, ändern, hinzufügen, zurücknehmen.

Eine Aktion ändert nur Status und Review-Felder von Labels, gelöscht wird nichts, und schreibt eine
Zeile in reviews, alles in einer Transaktion. Von Hand gesetzte Labels tragen stage='human'. Der
Worker lässt sie und bestätigte Labels stehen und übernimmt ein verworfenes Thema bei gleichem Text
wieder als verworfen (classify.queue.HUMAN).
"""

import psycopg
from fastapi import HTTPException

from parltopics.api.schemas import ReviewIn

# (status, review_status) des Labels nach der Aktion
DECISIONS = {
    "confirm": ("active", "confirmed"),
    "reject": ("rejected", "rejected"),
    "change": ("rejected", "changed"),
}

ACTIVE = """
SELECT id FROM affair_tags
WHERE affair_id = %(affair_id)s AND tag_id = %(tag_id)s AND status = 'active'
FOR UPDATE
"""
# Das zuletzt entschiedene Label des Themas, auch ein verworfenes.
REVIEWED = """
SELECT id, stage, status FROM affair_tags
WHERE affair_id = %(affair_id)s AND tag_id = %(tag_id)s AND review_status IS NOT NULL
  AND status IN ('active', 'rejected')
ORDER BY reviewed_at DESC NULLS LAST, id DESC
LIMIT 1
FOR UPDATE
"""
DECIDE = """
UPDATE affair_tags
SET status = %(status)s, review_status = %(review_status)s, reviewed_by = %(reviewed_by)s,
    reviewed_at = CASE WHEN %(reviewed_by)s::text IS NULL THEN NULL ELSE now() END
WHERE id = %(id)s
"""
TAG = "SELECT 1 FROM tags WHERE tag_id = %(tag_id)s AND status = 'active'"
RETIRED = "SELECT 1 FROM tags WHERE tag_id = %(tag_id)s AND status = 'retired'"
# Von Hand gesetzt: Konfidenz 1, ohne Beleg, zum Text, den die Person gesehen hat.
ADD = """
INSERT INTO affair_tags (affair_id, tag_id, scheme, confidence, task, stage, model_version,
                         prompt_version, registry_version, input_hash, review_status,
                         reviewed_by, reviewed_at)
SELECT i.affair_id, t.tag_id, t.scheme, 1, 'review', 'human', 'human', 'human',
       t.registry_version, i.input_hash, 'confirmed', %(user_name)s, now()
FROM affair_inputs i JOIN tags t ON t.tag_id = %(tag_id)s
WHERE i.affair_id = %(affair_id)s
RETURNING id
"""
LOG = """
INSERT INTO reviews (affair_id, affair_tag_id, action, new_tag_id, comment, user_name)
VALUES (%(affair_id)s, %(label_id)s, %(action)s, %(new_tag_id)s, %(comment)s, %(user_name)s)
"""


def apply(conn: psycopg.Connection, review: ReviewIn) -> None:
    """Führt die Aktion aus; HTTPException 404 ohne passendes Label oder Thema, 409 bei Konflikt."""
    params = review.model_dump()
    try:
        with conn.transaction():
            label_id = _act(conn.cursor(), review, params)
            conn.execute(LOG, {**params, "label_id": label_id})
    except psycopg.errors.UniqueViolation as error:
        raise HTTPException(409, "Für das Thema gibt es schon ein aktives Label") from error
    except psycopg.errors.CheckViolation as error:
        if error.diag.constraint_name != "reviews_action_check":
            raise
        raise HTTPException(
            503, "Die Datenbank kennt undo noch nicht: Migration 0004 fehlt (parltopics db migrate)"
        ) from error


def _act(cursor: psycopg.Cursor, review: ReviewIn, params: dict) -> int:
    """Ändert die Labels und gibt die ID des Labels zurück, das reviews protokolliert."""
    if review.action == "add":
        return _add(cursor, params)
    if review.action == "undo":
        return _undo(cursor, params)
    row = cursor.execute(ACTIVE, params).fetchone()
    if row is None:
        raise HTTPException(
            404, f"Kein aktives Label {review.tag_id} an Geschäft {review.affair_id}"
        )
    status, review_status = DECISIONS[review.action]
    decision = {"status": status, "review_status": review_status, "reviewed_by": review.user_name}
    cursor.execute(DECIDE, {"id": row[0], **decision})
    if review.action == "change":
        _add(cursor, {**params, "tag_id": review.new_tag_id})
    return row[0]


def _add(cursor: psycopg.Cursor, params: dict) -> int:
    if cursor.execute(TAG, params).fetchone() is None:
        raise HTTPException(404, f"Thema {params['tag_id']} unbekannt oder nicht aktiv")
    row = cursor.execute(ADD, params).fetchone()
    if row is None:
        raise HTTPException(404, f"Geschäft {params['affair_id']} hat keinen Klassifikationstext")
    return row[0]


def _undo(cursor: psycopg.Cursor, params: dict) -> int:
    # Auf einem zurückgezogenen Thema bleiben die Entscheide stehen; undo machte ein Label ohne
    # Entscheid wieder aktiv. Wer es ändern will, legt das Thema neu an.
    if cursor.execute(RETIRED, params).fetchone() is not None:
        raise HTTPException(409, f"Thema {params['tag_id']} ist zurückgezogen")
    row = cursor.execute(REVIEWED, params).fetchone()
    if row is None:
        raise HTTPException(
            404, f"Kein Entscheid zu {params['tag_id']} an Geschäft {params['affair_id']}"
        )
    label_id, stage, status = row
    if stage == "human" and status == "active":
        cursor.execute("UPDATE affair_tags SET status = 'superseded' WHERE id = %s", (label_id,))
    else:
        # Bestätigt: wieder offen. Verworfen: wieder aktiv, ausser ein anderes ist aktiv (409).
        reset = {"status": "active", "review_status": None, "reviewed_by": None}
        cursor.execute(DECIDE, {"id": label_id, **reset})
    return label_id
