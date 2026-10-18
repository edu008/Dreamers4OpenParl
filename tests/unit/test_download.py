import json

import httpx
import pytest

from parltopics.download import BASE_URL, download, select_files

FILES = {
    "affairs.ndjson.gz": b"a" * 10,
    "texts/texts_CHE.ndjson.gz": b"t" * 5,
    "texts/texts_ZH.ndjson.gz": b"z",
}


def make_index(created: str = "2026-10-18T01:00:00Z", sizes: dict[str, int] | None = None) -> dict:
    sizes = sizes or {name: len(body) for name, body in FILES.items()}

    def part(name: str) -> dict:
        return {
            "filename": name.split("/")[-1],
            "url": f"{BASE_URL}/{name}",
            "size": sizes[name],
            "row_count": 1,
            "created": created,
        }

    return {
        "files": [
            {"entity": "affairs", "type": "single", **part("affairs.ndjson.gz")},
            {"entity": "votes", "type": "single", **part("affairs.ndjson.gz")},
            {
                "entity": "texts",
                "type": "split",
                "directory": "texts/",
                "files": [part("texts/texts_CHE.ndjson.gz"), part("texts/texts_ZH.ndjson.gz")],
            },
        ]
    }


def client_for(index: dict, requests: list[str]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/exports/")
        requests.append(path)
        if path == "index.json":
            return httpx.Response(200, json=index)
        return httpx.Response(200, content=FILES[path])

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_select_files_filters_entities_and_bodies():
    paths = [f["path"] for f in select_files(make_index(), ["CHE"])]
    assert paths == ["affairs.ndjson.gz", "texts/texts_CHE.ndjson.gz"]
    assert len(list(select_files(make_index()))) == 3


def test_second_run_downloads_only_changed_files(tmp_path):
    requests: list[str] = []
    assert download(tmp_path, client=client_for(make_index(), requests), echo=lambda _: None) == (
        3,
        0,
    )
    assert (tmp_path / "texts" / "texts_CHE.ndjson.gz").read_bytes() == b"t" * 5
    assert json.loads((tmp_path / "index.json").read_text())["files"]

    requests.clear()
    assert download(tmp_path, client=client_for(make_index(), requests), echo=lambda _: None) == (
        0,
        3,
    )
    assert requests == ["index.json"]

    newer = make_index(created="2026-10-19T01:00:00Z")
    assert download(tmp_path, client=client_for(newer, requests), echo=lambda _: None) == (3, 0)


def test_size_mismatch_keeps_old_file(tmp_path):
    index = make_index(sizes={name: 99 for name in FILES})
    with pytest.raises(RuntimeError, match="statt 99 Bytes"):
        download(tmp_path, client=client_for(index, []), echo=lambda _: None)
    assert not (tmp_path / "affairs.ndjson.gz").exists()
    assert not (tmp_path / "index.json").exists()
