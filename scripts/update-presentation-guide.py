"""Update the retained twelve-page guide from its current Markdown speech.

Run with a Python environment containing lxml. This edits only document.xml in
the retained DOCX package; styles, headers, footer fields, tables and the diagram
remain source-derived. PDF export/rendering is a separate review step.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from zipfile import ZipFile

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def clean(text: str) -> str:
    return text.replace("–", "-").replace("—", "-").replace("‑", "-").replace("’", "'")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path,
                        default=ROOT / "output/presentation/localmind-demo-and-speaking-guide.docx")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "output/presentation/localmind-demo-and-speaking-guide.docx")
    parser.add_argument("--script", type=Path, default=ROOT / "output/presentation/10-minute-group-script.md")
    args = parser.parse_args()
    markdown = args.script.read_text()
    speakers = ["Trijal Burman", "Tiya Singh", "Gayatri Rajesh Apotikar", "Nimita Jestin"]
    speech_slots = [[66, 68, 70, 72, 74], [80, 82, 84, 86, 88], [94, 96, 98, 100],
                    [114, 116, 118, 120, 122, 124]]
    sections = re.split(r"(?m)^## ", markdown)[1:5]
    word_counts = {}
    replacements = {}
    for name, section, slots in zip(speakers, sections, speech_slots, strict=True):
        assert section.startswith(name + " — "), f"Unexpected speaking order for {name}"
        blocks = re.findall(r"\*\*Action:\*\* [^\n]+\n\n(.*?)(?=\n\n\*\*Action:|\Z)",
                            section.strip(), re.S)
        assert len(blocks) == len(slots), (name, len(blocks), len(slots))
        for index, text in zip(slots, blocks, strict=True):
            replacements[index] = text.strip()
        word_counts[name] = len(re.findall(r"\b[\w]+(?:[-'][\w]+)*\b", " ".join(blocks)))
    assert 1000 <= sum(word_counts.values()) <= 1100, word_counts

    replacements.update({
        1: "A ten minute presentation updated 17 October 2026",
        2: "Use this guide to explain LocalMind, run a prepared two minute demonstration and answer viva questions. The speaking pages match the current Markdown script. Read only speech paragraphs aloud; operation cues, preparation and optional answers are outside the ten minute timing.",
        18: "The diagram shows the document workflow. The app handles greetings without a model or retrieval. File inventories use MCP index metadata. Document questions use the local API, SQLite evidence, the MCP stdio server and Ollama inference; the browser displays the result for review.",
        20: "RAG means retrieval augmented generation. Search finds relevant passages and supplies selected evidence with the question. Current records preserve the actual filename, path and document identifier. Cards group excerpts from one file while keeping original citation numbers. Retrieval and real references still do not guarantee a correct claim.",
        28: "Prepare before the clock starts. Show only the two supplied sample files. Verify the chosen workspace is running; this update does not establish that the separate demo on port 8766 is ready.",
        30: "After normal Linux setup, run bash output/presentation/start-presentation-demo.sh from the checkout root. It uses separate sample data on port 8766 and the shared local model service. Preserve normal data and close private tabs.",
        32: "In Settings, refresh runtime status and verify readiness. Source defaults remain Qwen3 4B / 8192. The optional Qwen3.5 9B / 12288 profile needs more memory. Warm the model beforehand; an HDD cold load may take a minute or longer.",
        38: "Read lighthouse-project.md at Storage decision. Rehearse the question on page 4 after the model is loaded. The ten second wait limit applies to this warmed demonstration. Keep the source reader available.",
        42: "Use examples/knowledge inside your checkout; on Windows use the actual checkout path followed by \\examples\\knowledge. The normal app address is http://127.0.0.1:8765. The Linux demo uses http://127.0.0.1:8766 when its launcher is running.",
        52: "The retained 17 October context-repair rehearsal returned SQLite with a source and preserved memory. That dated record was not repeated for the latest greeting and metadata fixes. Check the demo before presenting; prepared rehearsal evidence is not a fresh live result.",
        87: "Operate  Y5  Point to source identities, then return to Library and hand over.",
        115: "Operate  N2  Point to the historical generation baseline of 0/24.",
        119: "Operate  N4  Show historical summaries and the separate later 9B probe.",
        136: "The browser calls a loopback FastAPI service. Approved files become text and chunks in SQLite. Retrieval selects evidence through the local MCP stdio server and Ollama runs the downloaded model. Greetings bypass that retrieval flow. File inventories use actual index metadata, and source cards group excerpts while keeping citation numbers.",
        151: "No. We use existing downloaded Qwen and EmbeddingGemma models. The project concerns the application, retrieval, persistence, tool interface and evaluation. Supplying retrieved context at request time does not train or fine-tune model weights.",
        154: "Source defaults are qwen3:4b-instruct-2507-q4_K_M, EmbeddingGemma and 8192 context tokens. This Linux laptop also used the optional qwen3.5:9b-q4_K_M / 12288 profile, with partial CPU offload. Hardware: RTX 5050 with 8 GB VRAM, Ryzen 7 250 and 16 GB RAM. The small development probe is not a universal model ranking; native Windows GPU inference remains unmeasured.",
        166: "The old estimate missed JSON escaping and UTF-8 cost, which could discard evidence. The repaired fitter retained references in 64/64 historical replay requests within budget. Current records also preserve exact filenames, paths and document identifiers; oversized metadata does not starve every later fitting record. Greetings bypass retrieval, and substantive document answers pass citation checks. These safeguards do not establish general factual accuracy.",
        169: "No. A real citation can still fail to support a claim. Uncited substantive document replies, including imperative requests, can get one tool-free retry. Invalid references fail directly, and failed retries retain safe original excerpts. Grouped cards keep original citation numbers. We still inspect the source passage.",
        172: "There is no completeness guarantee. MCP pagination fetches supported extracted text and long summaries process sections, but reduction can lose facts. The historical experiment retained 10/24 requested values across three summaries and was not rerun. Current question answering uses query-centered excerpts instead of fixed prefixes; bounded context can still omit facts.",
        178: "The database is not encrypted and local access checks do not defeat every threat. Latest suites: 163 Linux tests; 200 Windows-copy tests on Linux with six native checks skipped. The earlier native CI result of 178 tests per interpreter checked a previous commit. Native Windows GPU inference remains unmeasured. Future work includes long-document coverage, held-out evaluation and local OCR.",
        181: "Keep evidence coverage, transport and generated answers separate. Current suites passed 163 Linux tests and 200 Windows-copy tests on Linux, with six native checks skipped. The table separates historical experiments from the later small development probe.",
        185: "Latest metadata checks returned 7 indexed files, 1 exact api.md match and 0 matches for an absent test filename. One hello check took 0.0931 seconds with no model or retrieval call; this is not model-answer latency. No OCR is included, the database is unencrypted, and native Windows GPU inference is unmeasured.",
        187: "Only with extra time: open a sample source and choose Summarize in chat, or request a project plan with two milestones and labeled assumptions. Both are reviewable generated drafts. They do not prove full summary coverage or create a finished software project.",
        191: "• Explain the greeting, metadata and citation repairs without claiming perfect answers or universal model superiority. The earlier Windows CI run checked a previous commit.",
        192: "• Keep historical research, the small 9B probe and current software checks separate. Next work includes long-document coverage, held-out evaluation, local OCR and Windows GPU testing.",
    })
    with ZipFile(args.reference) as archive:
        entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
    parts = dict((info.filename, data) for info, data in entries)
    tree = etree.fromstring(parts["word/document.xml"])
    body = tree.find("w:body", NS)
    assert body is not None and len(body) == 194, "The retained guide slot map has changed"
    assert "".join(body[0].xpath(".//w:t/text()", namespaces=NS)) == "LocalMind demo and speaking guide"

    def set_text(element, text):
        nodes = element.xpath(".//w:t", namespaces=NS)
        assert nodes, "Expected an existing plain text slot"
        nodes[0].text = clean(text)
        nodes[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        for node in nodes[1:]:
            node.text = ""

    for index, text in replacements.items():
        assert body[index].tag == "{" + NS["w"] + "}p", index
        set_text(body[index], text)

    result_rows = [
        ["Historical retrieval", "96/96 at top five", "Lexical and hybrid evidence coverage on the authored corpus."],
        ["Historical generation", "0/24 per method", "Original fitter dropped the reference block."],
        ["Historical repair replay", "RAG 7/24; MCP 3/24", "64/64 requests retained evidence. Reused questions; not held-out validation."],
        ["Small later 9B probe", "8/8 known; 2/2 unknown", "Post-selected development checks; not general accuracy. Extra short-summary check failed."],
        ["Historical summaries", "10/24 fact values", "Three documents; not rerun after the repair."],
    ]
    rows = body[182].findall("w:tr", NS)
    assert len(rows) == 6
    for row, texts in zip(rows[1:], result_rows, strict=True):
        for cell, text in zip(row.findall("w:tc", NS), texts, strict=True):
            set_text(cell, text)
    parts["word/document.xml"] = etree.tostring(tree, encoding="UTF-8", xml_declaration=True, standalone=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".docx.tmp")
    with ZipFile(temporary, "w") as archive:
        for info, _ in entries:
            archive.writestr(info, parts[info.filename])
    temporary.replace(args.output)
    print(json.dumps({"output": str(args.output), "spoken_words": word_counts,
                      "total_spoken_words": sum(word_counts.values()),
                      "changed_package_parts": ["word/document.xml"]}, indent=2))


if __name__ == "__main__":
    main()
