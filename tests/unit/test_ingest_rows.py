from parltopics.ingest import (
    affair_row,
    body_row,
    contributor_row,
    doc_row,
    parse_line,
    text_row,
)


def test_parse_line_drops_nul():
    assert parse_line(b'{"text": "a\\u0000b"}') == {"text": "ab"}


def test_body_row_splits_languages():
    row = body_row(
        {
            "id": 1,
            "body_key": "BE",
            "name": "Bern",
            "name_de": None,
            "type": "canton",
            "languages": "DE, FR",
        }
    )
    assert (row["name"], row["level"], row["languages"]) == ("Bern", "canton", ["de", "fr"])


def test_affair_row_takes_first_url_and_date_only():
    row = affair_row(
        {
            "id": 2,
            "body_key": "VD",
            "begin_date": "2023-05-30T00:00:00",
            "url_external_de": None,
            "url_external_fr": "https://vd.ch/x",
        }
    )
    assert (row["begin_date"], row["url_external"], row["title_de"]) == (
        "2023-05-30",
        "https://vd.ch/x",
        None,
    )


def test_text_row_keeps_other_languages_in_raw():
    row = text_row(
        {
            "id": 3,
            "affair_id": 2,
            "text_de": None,
            "text_fr": "fr",
            "text_it": "it",
            "type_fr": "Texte déposé",
            "text_format": "html",
        }
    )
    assert (row["language"], row["text"], row["text_type"]) == ("fr", "fr", "Texte déposé")
    assert "text_fr" not in row["raw"].obj and row["raw"].obj["text_it"] == "it"


def test_text_row_without_text():
    row = text_row({"id": 4, "affair_id": 2})
    assert (row["language"], row["text"]) == (None, None)


def test_doc_row_parent_from_parent_type():
    row = doc_row(
        {
            "id": 5,
            "parent_type": "meeting",
            "meeting_id": 9,
            "affair_id": None,
            "date": "2020-06-10T00:00:00",
            "text": "inhalt",
            "category_harmonized": "agenda",
        }
    )
    assert (row["parent_id"], row["doc_date"], row["category"], row["text"]) == (
        9,
        "2020-06-10",
        "agenda",
        "inhalt",
    )
    assert "text" not in row["raw"].obj
    assert doc_row({"id": 6, "parent_type": "session"})["parent_id"] is None


def test_contributor_row_keeps_role_and_harmonized_party_without_raw():
    row = contributor_row(
        {
            "id": 7,
            "affair_id": 2,
            "type": "person",
            "role_harmonized": "author",
            "role_external_id": "correspondent",
            "fullname": "Anna Muster",
            "party_de": "Grüne Emmen",
            "party_harmonized_de": "Die Grünen",
            "position": 3,
        }
    )
    assert (row["role"], row["role_external_id"], row["name"], row["party"], row["position"]) == (
        "author",
        "correspondent",
        "Anna Muster",
        "Die Grünen",
        3,
    )
    assert "raw" not in row
    assert contributor_row({"id": 8, "news_id": 5, "type": "group"})["affair_id"] is None
