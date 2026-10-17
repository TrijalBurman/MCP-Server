"""Keep complete, query-relevant evidence records inside the local model budget.

These checks establish which excerpts and citation numbers were supplied. They
do not establish whether a generated claim is entailed by an excerpt.
"""
from __future__ import annotations

import json
import re
from collections import Counter

from .ollama import fit_context

EVIDENCE_PREFIX = "UNTRUSTED DOCUMENT EVIDENCE:\n"
_WINDOWS = (1000, 800, 600, 400, 240, 120, 60)
_WORDS = re.compile(r"[^\W_]+", re.UNICODE)
_STOP_WORDS = set(
    "what which who is are was were the a an of for to from in on by and or "
    "does do did how it its my your tell me all about use using answer at most "
    "sentences sentence with local document documents evidence cite supplied "
    "file files source sources please if absent say not".split()
)
_CITATION = re.compile(r"\[(?:sources?\s*:\s*)?(\d+(?:\s*,\s*\d+)*)\]", re.I)
_BRACKETS = re.compile(r"\[([^\[\]\n]*)\]")


def _excerpt(text: str, question: str, size: int) -> tuple[str, int]:
    """Choose an exact contiguous window, keeping informative query terms nearby."""
    if len(text) <= size:
        return text, 0
    terms = set(_WORDS.findall(question.casefold())) - _STOP_WORDS
    if not terms:
        return text[:size], 0
    hits = [match.start() for match in _WORDS.finditer(text)
            if match.group().casefold() in terms]
    starts = {0, len(text) - size}
    starts.update(max(0, min(len(text) - size, start - size // 3)) for start in hits)

    def relevance(start):
        counts = Counter(_WORDS.findall(text[start:start + size].casefold()))
        return (len(terms.intersection(counts)),
                sum(min(counts[term], 2) for term in terms), -start)

    offset = max(starts, key=relevance)
    return text[offset:offset + size], offset


def prepare_evidence(messages: list, sources: list, question: str,
                     schemas: list | None, context_size: int) -> tuple[list, list | None, list]:
    """Fit whole numbered records and return exactly the excerpts shown to the model.

    All sources receive the same character allowance before any source is
    omitted. Serialization (including outer JSON escaping) is checked through
    the production fitter, rather than estimated from raw character lengths.
    The returned payload has already been fitted, so Ollama's subsequent fit is
    idempotent. Inputs are not modified.

    For another tool round, callers must remove the previous evidence message
    and pass the full original source pool again. Passing the returned excerpts
    back as the source pool would progressively shorten them. Tool-result
    messages should carry metadata, with document text packed here once.
    """
    candidates = [source for source in sources if isinstance(source.get("text"), str)
                  and source["text"].strip()]
    if not candidates:
        fitted, fitted_schemas = fit_context(messages, schemas, context_size)
        return fitted, fitted_schemas, []

    cache = {}

    def trial(count, size):
        visible, records = [], []
        for index, source in enumerate(candidates[:count]):
            key = index, size
            if key not in cache:
                cache[key] = _excerpt(source["text"], question, size)
            text, offset = cache[key]
            number = index + 1
            record = {"source_number": number, "title": str(source.get("title", "Document"))[:160],
                      "text": text}
            records.append(record)
            excerpt = {**source, "source_number": number, "text": text}
            if isinstance(source.get("start"), int):
                excerpt["start"] = source["start"] + offset
                excerpt["end"] = excerpt["start"] + len(text)
            visible.append(excerpt)
        evidence = {"role": "system", "content": EVIDENCE_PREFIX +
                    json.dumps(records, ensure_ascii=False, separators=(",", ":"))}
        fitted, fitted_schemas = fit_context([*messages, evidence], schemas, context_size)
        if evidence in fitted:
            # No partially serialized record can be accepted: equality requires
            # the complete evidence message to survive unchanged.
            return fitted, fitted_schemas, visible
        return None

    count = len(candidates)
    for size in _WINDOWS:
        result = trial(count, size)
        if result is not None:
            return result

    # Find the largest ranked prefix that fits the minimum fair allowance.
    # Only reach this branch after every source together has been attempted.
    low, high = 0, count - 1
    while low < high:
        middle = (low + high + 1) // 2
        if trial(middle, _WINDOWS[-1]) is not None:
            low = middle
        else:
            high = middle - 1
    if low:
        for size in _WINDOWS:
            result = trial(low, size)
            if result is not None:
                return result
    fitted, fitted_schemas = fit_context(messages, schemas, context_size)
    return fitted, fitted_schemas, []


def _without_code(text: str) -> str:
    """Mask Markdown code spans and fences before looking for prose citations."""
    lines, fence = [], None
    for line in text.splitlines(keepends=True):
        delimiter = re.match(r" {0,3}(`{3,}|~{3,})([^\n]*)", line)
        if fence:
            lines.append(re.sub(r"[^\n]", " ", line))
            if delimiter and delimiter[1][0] == fence[0] and len(delimiter[1]) >= len(fence) \
                    and not delimiter[2].strip():
                fence = None
        elif delimiter:
            fence = delimiter[1]
            lines.append(re.sub(r"[^\n]", " ", line))
        else:
            lines.append(line)
    prose = "".join(lines)
    runs = list(re.finditer(r"`+", prose))
    pieces, cursor, index = [], 0, 0
    while index < len(runs):
        opening = runs[index]
        closing = next((j for j in range(index + 1, len(runs))
                        if len(runs[j][0]) == len(opening[0])), None)
        if closing is None:
            index += 1
            continue
        end = runs[closing].end()
        pieces.extend((prose[cursor:opening.start()],
                       re.sub(r"[^\n]", " ", prose[opening.start():end])))
        cursor, index = end, closing + 1
    pieces.append(prose[cursor:])
    return "".join(pieces)


def citation_numbers(text: str) -> list[int]:
    """Read [1], [1, 2] and [Source: 1, 2] in prose, ignoring Markdown code."""
    return [int(number) for match in _CITATION.finditer(_without_code(text))
            for number in re.findall(r"\d+", match.group(1))]


def valid_citations(text: str, source_count: int) -> bool:
    """Check supported numeric citation syntax and bounds, without semantic claims.

    No citations is valid here; callers decide whether a particular answer
    requires one. Numeric ranges are deliberately unsupported rather than
    silently accepting an unverified endpoint or expanding an enormous range.
    Numeric indexes inside inline or fenced Markdown code are not citations.
    """
    prose = _without_code(text)
    for match in _BRACKETS.finditer(prose):
        body = match.group(1).strip()
        citation_like = re.match(r"(?:sources?\s*:|\d)", body, re.I)
        if citation_like and _CITATION.fullmatch(match.group()) is None:
            return False
    return all(1 <= number <= source_count for match in _CITATION.finditer(prose)
               for number in map(int, re.findall(r"\d+", match.group(1))))
