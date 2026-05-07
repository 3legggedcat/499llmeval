from __future__ import annotations

import argparse
import json
import math
import os
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile

from pypdf import PdfReader


DEFAULT_MODEL = os.getenv("LITELLM_MODEL", "js2/gpt-oss-120b")
DEFAULT_API_BASE = os.getenv("LITELLM_API_BASE", "https://llm-api.cyverse.ai/v1")
DEFAULT_TEMPERATURE = float(os.getenv("LITELLM_TEMPERATURE", "0.3"))
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9']+")

STUDY_GUIDE_PROMPT = """You are a study guide writer.

Use only the retrieved document content to generate a study guide.
Requirements:
- Focus on the most important ideas, definitions, processes, and relationships in the material.
- Organize the output with clear section headings.
- Include concise explanations, key takeaways, and a short review checklist at the end.
- Keep the wording clear and student-facing.
- Do not invent facts that are not supported by the provided material.
"""


@dataclass
class DocumentChunk:
    section_number: int
    text: str
    section_type: str

    @property
    def label(self) -> str:
        return f"{self.section_type} {self.section_number}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a study guide from a PDF or PPTX file using local retrieval."
    )
    parser.add_argument(
        "document",
        type=Path,
        help="Path to the .pdf or .pptx file to ingest.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="How many sections to retrieve for the final prompt.",
    )
    parser.add_argument(
        "--question",
        default="Generate a study guide from this material.",
        help="User request to answer with RAG context.",
    )
    parser.add_argument(
        "--backend",
        choices=("ollama", "litellm"),
        default="ollama",
        help="Model backend to use. Default is local Ollama so no API key is required.",
    )
    return parser.parse_args()


def extract_pdf_chunks(pdf_path: Path) -> list[DocumentChunk]:
    reader = PdfReader(str(pdf_path))
    chunks: list[DocumentChunk] = []

    for index, page in enumerate(reader.pages, start=1):
        page_text = (page.extract_text() or "").strip()
        if page_text:
            chunks.append(
                DocumentChunk(section_number=index, text=page_text, section_type="Page")
            )

    return chunks


def extract_pptx_chunks(pptx_path: Path) -> list[DocumentChunk]:
    slide_pattern = re.compile(r"ppt/slides/slide(\d+)\.xml$")
    namespace = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    chunks: list[DocumentChunk] = []

    with ZipFile(pptx_path) as archive:
        slide_members = []
        for name in archive.namelist():
            match = slide_pattern.match(name)
            if match:
                slide_members.append((int(match.group(1)), name))

        for slide_number, member_name in sorted(slide_members):
            with archive.open(member_name) as slide_file:
                tree = ET.parse(slide_file)

            text_runs = [
                node.text.strip()
                for node in tree.findall(".//a:t", namespace)
                if node.text and node.text.strip()
            ]
            slide_text = "\n".join(text_runs).strip()
            if slide_text:
                chunks.append(
                    DocumentChunk(
                        section_number=slide_number,
                        text=slide_text,
                        section_type="Slide",
                    )
                )

    return chunks


def extract_document_chunks(document_path: Path) -> list[DocumentChunk]:
    if not document_path.exists():
        raise FileNotFoundError(f"Document file not found: {document_path}")

    suffix = document_path.suffix.lower()
    if suffix == ".pdf":
        chunks = extract_pdf_chunks(document_path)
    elif suffix == ".pptx":
        chunks = extract_pptx_chunks(document_path)
    else:
        raise ValueError("Input file must be a .pdf or .pptx file.")

    if not chunks:
        raise ValueError(
            "No text could be extracted from the document. Make sure it contains selectable text."
        )

    return chunks


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


class LocalRetriever:
    def __init__(self, chunks: list[DocumentChunk]) -> None:
        self.chunks = chunks
        self.doc_tokens = [tokenize(chunk.text) for chunk in chunks]
        self.doc_freq = Counter()

        for tokens in self.doc_tokens:
            for token in set(tokens):
                self.doc_freq[token] += 1

        self.doc_vectors = [self._tf_idf(tokens) for tokens in self.doc_tokens]

    def _tf_idf(self, tokens: Iterable[str]) -> dict[str, float]:
        counts = Counter(tokens)
        total = sum(counts.values()) or 1
        vector: dict[str, float] = {}

        for token, count in counts.items():
            tf = count / total
            idf = math.log((1 + len(self.chunks)) / (1 + self.doc_freq[token])) + 1
            vector[token] = tf * idf

        return vector

    def search(self, query: str, top_k: int) -> list[DocumentChunk]:
        query_vector = self._tf_idf(tokenize(query))
        scored: list[tuple[float, DocumentChunk]] = []

        for chunk, doc_vector in zip(self.chunks, self.doc_vectors):
            score = cosine_similarity(query_vector, doc_vector)
            scored.append((score, chunk))

        ranked = sorted(scored, key=lambda item: item[0], reverse=True)
        results = [chunk for score, chunk in ranked if score > 0][:top_k]
        return results or self.chunks[:top_k]


def cosine_similarity(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0

    numerator = sum(weight * right.get(token, 0.0) for token, weight in left.items())
    left_norm = math.sqrt(sum(weight * weight for weight in left.values()))
    right_norm = math.sqrt(sum(weight * weight for weight in right.values()))

    if left_norm == 0 or right_norm == 0:
        return 0.0

    return numerator / (left_norm * right_norm)


def build_prompt(question: str, retrieved_chunks: list[DocumentChunk]) -> str:
    context = "\n\n".join(
        f"{chunk.label}\n{chunk.text}" for chunk in retrieved_chunks
    )
    return (
        f"{STUDY_GUIDE_PROMPT}\n"
        f"User request: {question}\n\n"
        f"Retrieved document context:\n{context}\n\n"
        "Generate the study guide now."
    )


def create_llm():
    from llama_index.llms.litellm import LiteLLM

    api_key = os.getenv("LITELLM_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "Set LITELLM_API_KEY before running this script."
        )

    return LiteLLM(
        model=DEFAULT_MODEL,
        api_base=DEFAULT_API_BASE,
        api_key=api_key,
        temperature=DEFAULT_TEMPERATURE,
    )


def generate_with_ollama(prompt: str) -> str:
    payload = json.dumps(
        {
            "model": DEFAULT_OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        DEFAULT_OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Could not reach the local Ollama server. Start Ollama and pull a model "
            f"such as `{DEFAULT_OLLAMA_MODEL}`."
        ) from exc

    result = body.get("response", "").strip()
    if not result:
        raise RuntimeError("Ollama returned an empty response.")
    return result


def generate_study_guide(
    document_path: Path, question: str, top_k: int, backend: str
) -> str:
    chunks = extract_document_chunks(document_path)
    retriever = LocalRetriever(chunks)
    retrieved = retriever.search(question, top_k=top_k)
    prompt = build_prompt(question, retrieved)

    if backend == "ollama":
        return generate_with_ollama(prompt)

    llm = create_llm()
    response = llm.complete(prompt)
    return response.text.strip()


def main() -> None:
    args = parse_args()
    study_guide = generate_study_guide(
        args.document, args.question, args.top_k, args.backend
    )
    print(study_guide)


if __name__ == "__main__":
    main()
