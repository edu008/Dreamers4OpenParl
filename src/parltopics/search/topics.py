"""Themen in einer Suchanfrage erkennen (F15): zuerst über die Bezeichnungen der Registry, sonst
mit einem Vorschlag von 8B.

Die Volltextsuche findet ein Geschäft nur in seiner eigenen Sprache: «Digitalisierung» trifft kein
französisches Geschäft aus Genf. Erkennt die Suche ein Thema, sucht sie darum auch mit seinen
Bezeichnungen in DE, FR und IT und nimmt die Geschäfte mit diesem Label dazu. Erkannt wird über
ganze Wörter, ohne Akzente und Grossschreibung, Tippfehler ab sechs Buchstaben. Erkennt die
Registry nichts, schlägt 8B höchstens drei Themen vor (search_topics_v1); es zählen nur Themen der
Registry. Vorschläge bleiben je Anfrage im Speicher, damit jede Seite derselben Suche dieselben
Themen hat.
"""

import asyncio
import re
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Literal

import httpx

from parltopics.config import Settings
from parltopics.llm import LLMClient, extract_json, load_prompt
from parltopics.registry import Registry, Tag
from parltopics.wiki.tree import Page, subtree_tag_ids

LANGS = ("de", "fr", "it")
TYPO_MIN = 6  # kürzere Wörter nur genau: «Bauen» ist nicht «Bauern»
TYPO_RATIO = 0.85
WORD = re.compile(r"\w+")
OR = re.compile(r"\s+or\s+", re.IGNORECASE)  # das ODER von websearch_to_tsquery
AS_TYPED = re.compile(r'"|(?:^|\s)-\w')  # Wortfolge oder Ausschluss: so suchen, wie getippt
PROMPT = "search_topics_v1"
SUGGESTED_MAX = 2  # mit drei brachte «Energiewende» auch den allgemeinen Umweltschutz: 48'000
SUGGEST_SECONDS = 5.0
CACHE_MAX = 256


def plain(word: str) -> str:
    """Ohne Akzente: «numérisation» wie «numerisation»."""
    return "".join(c for c in unicodedata.normalize("NFKD", word) if not unicodedata.combining(c))


def words(text: str) -> list[str]:
    """Wörter klein und ohne Akzente, zum Vergleich mit den Bezeichnungen."""
    return [plain(word.casefold()) for word in WORD.findall(unicodedata.normalize("NFC", text))]


@dataclass(frozen=True)
class Label:
    tag_id: str
    text: str
    lang: str | None  # None: versteckte Bezeichnung, Sprache offen
    weight: int  # 2 bevorzugt, 1 alternativ, 0 versteckt
    words: tuple[str, ...]


@dataclass(frozen=True)
class Match:
    start: int
    end: int
    label: Label
    similarity: float  # 1.0: genau


@dataclass(frozen=True)
class Group:
    """Ein erkanntes Thema: alle Bezeichnungen je Sprache für die Treffer, für den Rang nur die
    Namen, mit denen die Anfrage es meint (names, None: Sprache offen)."""

    tag_id: str
    terms: dict[str | None, list[str]]
    names: dict[str | None, str]


@dataclass(frozen=True)
class Branch:
    """Ein Teil der Anfrage zwischen «or»: wie getippt, dazu seine Themen und übrigen Wörter."""

    text: str | None  # None: nur die Themen (Vorschlag von 8B)
    groups: tuple[Group, ...] = ()
    rest: tuple[str, ...] = ()  # Wörter ausserhalb der Themen, wie getippt


@dataclass(frozen=True)
class Found:
    tag_id: str
    name_de: str
    source: Literal["registry", "llm"]
    typed: str | None = None  # die Wörter der Anfrage
    label: str | None = None  # die Bezeichnung, die sie trafen
    typo: bool = False


@dataclass(frozen=True)
class Plan:
    query: str
    branches: tuple[Branch, ...]
    found: tuple[Found, ...] = ()
    labelled: tuple[str, ...] = ()  # Tags mit Unterthemen: ihre Geschäfte gehören dazu
    model_version: str | None = None
    prompt_version: str | None = None

    @property
    def groups(self) -> list[Group]:
        unique = {group.tag_id: group for branch in self.branches for group in branch.groups}
        return list(unique.values())

    def terms(self) -> dict[str, list[str]]:
        """Die Bezeichnungen der erkannten Themen je Sprache, ohne versteckte Schreibweisen;
        leer ohne Thema."""
        if not self.groups:
            return {}
        found: dict[str, list[str]] = {lang: [] for lang in LANGS}
        for group in self.groups:
            for lang in LANGS:
                found[lang] += [t for t in group.terms.get(lang, []) if t not in found[lang]]
        return found


def as_typed(query: str) -> Plan:
    """Die Suche ohne Themen, so wie getippt (expand=false)."""
    return Plan(query, tuple(Branch(part) for part in OR.split(query)))


def _labels(tag: Tag) -> list[Label]:
    texts = []
    for lang in LANGS:
        preferred = getattr(tag.pref_label, lang)
        texts += [(preferred, lang, 2)] if preferred else []
        texts += [(alt, lang, 1) for alt in getattr(tag.alt_labels, lang)]
    texts += [(hidden, None, 0) for hidden in tag.hidden_labels]
    labels = (
        Label(tag.tag_id, text, lang, weight, tuple(words(text))) for text, lang, weight in texts
    )
    return [label for label in labels if label.words]


class Vocabulary:
    """Die Bezeichnungen der aktiven Tags: genau über ihre Wörter (auch zusammengeschrieben, wie
    «egovernment»), für Tippfehler nach Anfangsbuchstabe und Zahl der Wörter."""

    def __init__(self, registry: Registry, tree: dict[str, Page]) -> None:
        self.registry, self.tree = registry, tree
        self.tags = {tag.tag_id: tag for tag in registry.tags if tag.status == "active"}
        self.keys = {tag.slug or tag.tag_id: tag.tag_id for tag in self.tags.values()}
        self.labels = {tag_id: _labels(tag) for tag_id, tag in self.tags.items()}
        self.exact: dict[tuple[str, ...], list[Label]] = {}
        self.typos: dict[tuple[str, int], list[Label]] = {}
        for label in (label for labels in self.labels.values() for label in labels):
            self.exact.setdefault(label.words, []).append(label)
            if len(label.words) > 1:
                self.exact.setdefault(("".join(label.words),), []).append(label)
            if len(" ".join(label.words)) >= TYPO_MIN:
                key = (label.words[0][0], len(label.words))
                self.typos.setdefault(key, []).append(label)
        self.longest = max((len(key) for key in self.exact), default=1)

    def find(self, query: list[str]) -> list[Match]:
        """Bezeichnungen in den Wörtern, ohne Überlappung: genau vor Tippfehler, längere vor
        kürzeren, bevorzugte vor alternativen und versteckten."""
        candidates = []
        for start in range(len(query)):
            for end in range(start + 1, min(len(query), start + self.longest) + 1):
                window = tuple(query[start:end])
                hits = self.exact.get(window, [])
                if end - start > 1:
                    hits = hits + self.exact.get(("".join(window),), [])
                candidates += [Match(start, end, label, 1.0) for label in hits]
                text = " ".join(window)
                if hits or len(text) < TYPO_MIN:
                    continue
                for label in self.typos.get((text[0], len(window)), []):
                    other = " ".join(label.words)
                    if abs(len(other) - len(text)) > 2:
                        continue
                    similarity = SequenceMatcher(None, text, other).ratio()
                    if similarity >= TYPO_RATIO:
                        candidates.append(Match(start, end, label, similarity))

        def order(match: Match) -> tuple:
            length = len(" ".join(match.label.words))
            return (match.similarity < 1, -length, -match.label.weight, -match.similarity)

        chosen: list[Match] = []
        for match in sorted(candidates, key=order):
            if all(match.end <= other.start or match.start >= other.end for other in chosen):
                chosen.append(match)
        return sorted(chosen, key=lambda match: match.start)

    def group(self, tag_id: str, via: Label | None = None) -> Group:
        """Das Thema für die Suche. Für den Rang zählen seine bevorzugten Bezeichnungen, wenn die
        Anfrage es beim Namen nannte (oder 8B es vorschlug: via None), sonst nur die getroffene:
        «Velo» ist ein Synonym der Verkehrspolitik, ihre Geschäfte ohne Velo sollen nicht vorn
        stehen."""
        terms: dict[str | None, list[str]] = {}
        for label in self.labels[tag_id]:
            terms.setdefault(label.lang, []).append(label.text)
        tag = self.tags[tag_id]
        if via is not None and via.weight < 2:
            return Group(tag_id, terms, {via.lang: via.text})
        names = {lang: getattr(tag.pref_label, lang) for lang in LANGS}
        return Group(tag_id, terms, {lang: name for lang, name in names.items() if name})

    def subtree(self, tag_id: str) -> list[str]:
        return subtree_tag_ids(self.tree, tag_id) or [tag_id]

    def resolve(self, keys: list[str]) -> list[str]:
        """Tag-IDs zu den Schlüsseln von 8B. Ein falsch abgeschriebener Schlüssel zählt, wenn er
        als Ganzes eine Bezeichnung trifft: 8B schrieb «gewasserschutz» statt «gewaesserschutz»."""
        found: list[str] = []
        for key in keys:
            tag_id = self.keys.get(key) or (key if key in self.tags else None)
            if tag_id is None:
                query = words(key)
                matches = self.find(query)
                whole = len(matches) == 1 and (matches[0].start, matches[0].end) == (0, len(query))
                tag_id = matches[0].label.tag_id if whole else None
            if tag_id is not None and tag_id not in found:
                found.append(tag_id)
        return found


_cached: tuple[Registry, Vocabulary] | None = None


def vocabulary(registry: Registry, tree: dict[str, Page]) -> Vocabulary:
    """Das Verzeichnis zur Registry, einmal je geladene Registry: es aufzubauen kostet ~30 ms."""
    global _cached
    if _cached is None or _cached[0] is not registry:
        _cached = (registry, Vocabulary(registry, tree))
    return _cached[1]


def understand(vocab: Vocabulary, query: str) -> Plan:
    """Die Themen der Anfrage aus der Registry, je Teil zwischen «or». Ein Teil mit Wortfolge
    ("…") oder Ausschluss (-wort) bleibt, wie getippt. Gelabelte Geschäfte zählen nur für einen
    Teil, der genau ein Thema ist: sonst fehlten die übrigen Bedingungen."""
    branches, found, labelled = [], {}, []
    for part in OR.split(query):
        text = unicodedata.normalize("NFC", part)
        spans = list(WORD.finditer(text))
        query_words = [plain(span[0].casefold()) for span in spans]
        matches = [] if AS_TYPED.search(part) else vocab.find(query_words)
        covered = {i for match in matches for i in range(match.start, match.end)}
        rest = tuple(span[0].casefold() for i, span in enumerate(spans) if i not in covered)
        named = sorted(matches, key=lambda match: match.label.weight)  # der Name zuletzt: er gilt
        groups = {
            match.label.tag_id: vocab.group(match.label.tag_id, match.label) for match in named
        }
        branches.append(Branch(part, tuple(groups.values()), rest))
        for match in matches:
            tag = vocab.tags[match.label.tag_id]
            typed = text[spans[match.start].start() : spans[match.end - 1].end()]
            typo = match.similarity < 1
            found.setdefault(
                tag.tag_id,
                Found(tag.tag_id, tag.pref_label.de, "registry", typed, match.label.text, typo),
            )
        if len(groups) == 1 and not rest:
            labelled += vocab.subtree(next(iter(groups)))
    return Plan(query, tuple(branches), tuple(found.values()), tuple(dict.fromkeys(labelled)))


_suggested: OrderedDict[tuple[str, str, str], tuple[tuple[str, ...], str]] = OrderedDict()


async def suggest(
    settings: Settings,
    vocab: Vocabulary,
    query: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Plan:
    """Themen von 8B, wenn die Registry keine erkennt. openai.APIError, TimeoutError oder
    JSONExtractionError: kein Vorschlag, der Aufrufer sucht dann wie getippt."""
    prompt = load_prompt(settings.prompts_dir, PROMPT)
    cache_key = (vocab.registry.registry_version, prompt.version, " ".join(words(query)))
    if cache_key in _suggested:
        _suggested.move_to_end(cache_key)
        tag_ids, model = _suggested[cache_key]
    else:
        topics = [
            {
                "key": tag.slug or tag.tag_id,
                "de": tag.pref_label.de,
                "fr": tag.pref_label.fr or "",
                "it": tag.pref_label.it or "",
            }
            for tag in vocab.tags.values()
        ]
        messages = prompt.messages({"topics": topics}, {"query": query})
        async with LLMClient(settings, transport=transport) as client:
            reply = await asyncio.wait_for(client.chat(messages, attempts=1), SUGGEST_SECONDS)
        data = extract_json(reply.content)
        keys = data.get("topics") if isinstance(data, dict) else None
        keys = [k for k in keys if isinstance(k, str)] if isinstance(keys, list) else []
        tag_ids, model = tuple(vocab.resolve(keys)[:SUGGESTED_MAX]), reply.model
        _suggested[cache_key] = (tag_ids, model)
        while len(_suggested) > CACHE_MAX:
            _suggested.popitem(last=False)
    groups = tuple(vocab.group(tag_id) for tag_id in tag_ids)
    return Plan(
        query,
        (*as_typed(query).branches, *(Branch(None, (group,)) for group in groups)),
        tuple(Found(tag_id, vocab.tags[tag_id].pref_label.de, "llm") for tag_id in tag_ids),
        tuple(dict.fromkeys(s for tag_id in tag_ids for s in vocab.subtree(tag_id))),
        model_version=model,
        prompt_version=prompt.version,
    )
