"""Klassifikationstext: HTML, Quellen, Sprache und Länge (PRD F3)."""

from parltopics.inputs import INPUT_MAX_CHARS, compose, strip_html, text_blocks


def text_row(row_id: int, text_type: str, text: str, language: str = "de") -> dict:
    return {"id": row_id, "text_type": text_type, "language": language, "text": text}


def never(text: str) -> str:
    raise AssertionError(f"Spracherkennung unnötig aufgerufen: {text!r}")


def test_strip_html_keeps_text_and_paragraphs():
    html = (
        "<p>Der&nbsp;Bundesrat <span style='color:red'>wird</span></p>"
        "<p>beauftragt</p><script>alarm()</script>"
    )
    assert strip_html(html) == "Der Bundesrat wird\nbeauftragt"
    assert strip_html("Bilaterale&amp;nbsp;III &amp;amp; EU") == "Bilaterale III & EU"


def test_compose_cleans_titles_too():
    affair = {"title_de": "Hitzesommer&nbsp;2026"}
    assert compose(affair, [("de", "Text")], None, never)[0] == "Hitzesommer 2026\nText"


def test_text_blocks_drop_titles_and_answers_and_put_the_submitted_text_first():
    rows = [
        text_row(1, "Antwort BR / Büro", "<p>Antwort</p>"),
        text_row(2, "Begründung", "<p>Weil</p>"),
        text_row(3, "Titel des Geschäftes", "Titel"),
        text_row(4, "Eingereichter Text", "<p>Der Bundesrat</p>"),
        text_row(5, "Réponse CF / Bureau", "Réponse", "fr"),
        text_row(6, "Lead", "<p> </p>"),
    ]
    assert text_blocks(rows) == [("de", "Der Bundesrat"), ("de", "Weil")]


def test_compose_takes_texts_with_the_title_in_their_language():
    affair = {"title_de": "Titel", "title_fr": "Titre"}
    assert compose(affair, [("fr", "Texte déposé")], None, never) == (
        "Titre\nTexte déposé",
        "fr",
        "texts",
    )


def test_compose_falls_back_to_the_first_document_then_the_title():
    affair = {"title_de": "Titel"}
    doc = {"language": "de", "text": "<p>Erstes Dokument</p>"}
    assert compose(affair, [], doc, never) == ("Titel\nErstes Dokument", "de", "first_doc")
    unknown = {"language": None, "text": "Texte"}
    assert compose(affair, [], unknown, lambda _: "fr") == ("Titel\nTexte", "fr", "first_doc")
    assert compose(affair, [], None, lambda _: "de") == ("Titel", "de", "title_only")
    assert compose({}, [], None, never) is None


def test_compose_cuts_long_texts():
    text, _, _ = compose({"title_de": "T"}, [("de", "x" * 10_000)], None, never)
    assert len(text) == INPUT_MAX_CHARS


def test_compose_prefers_the_long_title_in_each_language():
    affair = {"title_de": "Hitze", "title_long_de": "Motion Muster. Hitze in Städten"}
    assert compose(affair, [], None, lambda _: "de")[0] == "Motion Muster. Hitze in Städten"
    only_short_fr = {"title_fr": "Chaleur", "title_long_de": "Motion Muster. Hitze"}
    assert compose(only_short_fr, [("fr", "Texte")], None, never)[0] == "Chaleur\nTexte"
