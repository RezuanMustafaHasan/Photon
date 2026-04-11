import re
from collections import Counter


HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")
PAGE_PATTERN = re.compile(r"^Page\s+\d+\b.*$", re.IGNORECASE)
TOKEN_PATTERN = re.compile(r"[a-z0-9]+|[\u0980-\u09ff]+", re.IGNORECASE)
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?।])\s+")
INTRO_QUERY_TOKENS = {
    "start",
    "begin",
    "continue",
    "teach",
    "teachme",
    "intro",
    "introduction",
    "overview",
    "summary",
    "explain",
    "lesson",
    "chapter",
    "topic",
    "শুরু",
    "শুরুকরো",
    "শুরুকরো",
    "শুরুকরি",
    "বুঝাও",
    "বুঝিয়ে",
    "বুঝিয়ে",
    "শেখাও",
    "পড়াও",
    "শেখান",
    "explainmore",
}
STOP_TOKENS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "what",
    "why",
    "how",
    "from",
    "your",
    "have",
    "has",
    "had",
    "are",
    "was",
    "were",
    "will",
    "shall",
    "would",
    "could",
    "should",
    "then",
    "than",
    "into",
    "about",
    "more",
    "please",
    "explain",
    "teach",
    "start",
    "tell",
    "give",
    "show",
    "ami",
    "ki",
    "kano",
    "kibhabe",
    "kibhay",
    "keno",
    "eta",
    "eita",
    "ei",
    "ta",
    "te",
    "er",
    "theke",
    "and",
    "or",
    "of",
    "to",
    "in",
    "is",
    "be",
    "it",
    "a",
    "an",
}


def collapse_whitespace(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_text(value):
    return collapse_whitespace(str(value or "").lower())


def tokenize(value):
    return [
        token
        for token in TOKEN_PATTERN.findall(normalize_text(value))
        if token and len(token) > 1 and token not in STOP_TOKENS
    ]


def normalize_lesson_key(value):
    return normalize_text(value)


def clean_markdown_text(value):
    text = str(value or "")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[Image[^\]]*\]", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"`{1,3}", "", text)
    return text.strip()


def sentence_fragments(text):
    pieces = SENTENCE_SPLIT_PATTERN.split(collapse_whitespace(text))
    return [piece.strip() for piece in pieces if piece.strip()]


def truncate_text(text, max_length=180):
    collapsed = collapse_whitespace(text)
    if len(collapsed) <= max_length:
        return collapsed
    clipped = collapsed[: max_length - 3].rstrip(" ,;:-")
    return f"{clipped}..."


def build_chunk_label(page_label, heading_label, fallback_index):
    if page_label and heading_label:
        return f"{page_label} / {heading_label}"
    if heading_label:
        return heading_label
    if page_label:
        return page_label
    return f"Chunk {fallback_index}"


def split_large_paragraph(paragraph, max_chars):
    paragraph = collapse_whitespace(paragraph)
    if not paragraph:
        return []
    if len(paragraph) <= max_chars:
        return [paragraph]

    sentences = sentence_fragments(paragraph)
    if len(sentences) <= 1:
        return [paragraph[index:index + max_chars].strip() for index in range(0, len(paragraph), max_chars)]

    chunks = []
    current = []
    current_length = 0
    for sentence in sentences:
        sentence_length = len(sentence) + (1 if current else 0)
        if current and current_length + sentence_length > max_chars:
            chunks.append(" ".join(current).strip())
            current = [sentence]
            current_length = len(sentence)
            continue
        current.append(sentence)
        current_length += sentence_length

    if current:
        chunks.append(" ".join(current).strip())

    return [chunk for chunk in chunks if chunk]


def split_section_into_chunks(text, section_label, max_chars=900, max_paragraphs=3):
    paragraphs = [
        collapse_whitespace(paragraph)
        for paragraph in re.split(r"\n\s*\n+", clean_markdown_text(text))
        if collapse_whitespace(paragraph)
    ]

    expanded = []
    for paragraph in paragraphs:
        expanded.extend(split_large_paragraph(paragraph, max_chars))

    chunks = []
    buffer = []
    buffer_length = 0
    for paragraph in expanded:
        paragraph_length = len(paragraph)
        needs_flush = (
            buffer
            and (
                len(buffer) >= max_paragraphs
                or buffer_length + paragraph_length + 1 > max_chars
            )
        )
        if needs_flush:
            chunk_text = "\n\n".join(buffer).strip()
            chunks.append({
                "section_label": section_label,
                "chunk_text": chunk_text,
                "snippet": truncate_text(chunk_text),
            })
            buffer = []
            buffer_length = 0

        buffer.append(paragraph)
        buffer_length += paragraph_length + 1

    if buffer:
        chunk_text = "\n\n".join(buffer).strip()
        chunks.append({
            "section_label": section_label,
            "chunk_text": chunk_text,
            "snippet": truncate_text(chunk_text),
        })

    return chunks


def chunk_lesson_content(raw_content, max_chars=900, max_paragraphs=3):
    content = clean_markdown_text(raw_content)
    if not content:
        return []

    sections = []
    page_label = None
    heading_label = None
    buffer = []

    def flush():
        if not buffer:
            return
        section_text = "\n".join(buffer).strip()
        sections.append({
            "page_label": page_label,
            "heading_label": heading_label,
            "text": section_text,
        })
        buffer.clear()

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            if buffer and buffer[-1] != "":
                buffer.append("")
            continue

        if PAGE_PATTERN.match(line):
            flush()
            page_label = collapse_whitespace(line)
            continue

        heading_match = HEADING_PATTERN.match(line)
        if heading_match:
            flush()
            heading_label = collapse_whitespace(heading_match.group(2))
            continue

        buffer.append(line)

    flush()

    if not sections:
        sections = [{"page_label": None, "heading_label": None, "text": content}]

    chunks = []
    for index, section in enumerate(sections, start=1):
        section_label = build_chunk_label(section.get("page_label"), section.get("heading_label"), index)
        chunks.extend(
            split_section_into_chunks(
                section.get("text"),
                section_label=section_label,
                max_chars=max_chars,
                max_paragraphs=max_paragraphs,
            )
        )

    for index, chunk in enumerate(chunks, start=1):
        chunk["chunk_index"] = index

    return chunks


def annotate_lesson_chunks(lesson_entry, current_lesson_name):
    chapter_name = collapse_whitespace(lesson_entry.get("chapter_name"))
    lesson_name = collapse_whitespace(lesson_entry.get("lesson_name"))
    lesson_key = normalize_lesson_key(lesson_name)
    current_key = normalize_lesson_key(current_lesson_name)
    chunks = chunk_lesson_content(lesson_entry.get("content"))

    for chunk in chunks:
        chunk["chapter_name"] = chapter_name
        chunk["lesson_name"] = lesson_name
        chunk["lesson_key"] = lesson_key
        chunk["is_current_lesson"] = lesson_key == current_key

    return chunks


def is_introductory_question(question):
    normalized = normalize_text(question)
    if not normalized:
        return True

    joined = normalized.replace(" ", "")
    if joined in INTRO_QUERY_TOKENS:
        return True

    tokens = tokenize(question)
    if not tokens:
        return True

    return len(tokens) <= 2 and all(token in INTRO_QUERY_TOKENS for token in tokens)


def score_chunk(question, chunk):
    query_tokens = tokenize(question)
    if not query_tokens:
        return 0

    chunk_tokens = tokenize(chunk.get("chunk_text"))
    heading_tokens = tokenize(chunk.get("section_label"))
    if not chunk_tokens and not heading_tokens:
        return 0

    chunk_counter = Counter(chunk_tokens)
    heading_counter = Counter(heading_tokens)
    unique_query_tokens = list(dict.fromkeys(query_tokens))

    score = 0
    overlap_count = 0
    for token in unique_query_tokens:
        body_hits = chunk_counter.get(token, 0)
        heading_hits = heading_counter.get(token, 0)
        if body_hits or heading_hits:
            overlap_count += 1
            score += 2
            score += min(body_hits, 3)
            score += heading_hits * 3

    normalized_question = normalize_text(question)
    normalized_chunk = normalize_text(chunk.get("chunk_text"))
    if normalized_question and normalized_question in normalized_chunk:
        score += 5

    if overlap_count == 0:
        return 0

    score += min(overlap_count, 4)
    if chunk.get("is_current_lesson"):
        score += 1
    return score


def retrieve_relevant_chunks(raw_content, question, top_k=3):
    chunks = chunk_lesson_content(raw_content)
    if not chunks:
        return {"mode": "empty", "chunks": []}

    if is_introductory_question(question):
        return {
            "mode": "intro",
            "chunks": chunks[: min(top_k, len(chunks))],
        }

    scored = []
    for chunk in chunks:
        score = score_chunk(question, chunk)
        if score > 0:
            scored.append((score, chunk))

    if not scored:
        return {"mode": "no_match", "chunks": []}

    scored.sort(key=lambda item: (item[0], -item[1].get("chunk_index", 0)), reverse=True)
    return {
        "mode": "matched",
        "chunks": [chunk for _score, chunk in scored[:top_k]],
    }


def lesson_source_label(chapter_name, lesson_name):
    chapter_name = collapse_whitespace(chapter_name)
    lesson_name = collapse_whitespace(lesson_name)
    if chapter_name and lesson_name:
        return f"{chapter_name} / {lesson_name}"
    return lesson_name or chapter_name


def retrieve_relevant_lesson_chunks(lesson_entries, question, current_lesson_name, top_k=3):
    if not isinstance(lesson_entries, list):
        lesson_entries = []

    annotated_chunks = []
    for lesson_entry in lesson_entries:
        if not isinstance(lesson_entry, dict):
            continue
        annotated_chunks.extend(annotate_lesson_chunks(lesson_entry, current_lesson_name))

    if not annotated_chunks:
        return {"mode": "empty", "chunks": [], "source_lesson_name": "", "current_lesson_name": collapse_whitespace(current_lesson_name)}

    current_key = normalize_lesson_key(current_lesson_name)

    if is_introductory_question(question):
        current_chunks = [chunk for chunk in annotated_chunks if chunk.get("lesson_key") == current_key]
        selected_chunks = current_chunks or annotated_chunks
        selected_chunks = selected_chunks[: min(top_k, len(selected_chunks))]
        return {
            "mode": "intro",
            "chunks": selected_chunks,
            "source_lesson_name": collapse_whitespace(current_lesson_name),
            "current_lesson_name": collapse_whitespace(current_lesson_name),
        }

    scored_by_lesson = {}
    for chunk in annotated_chunks:
        score = score_chunk(question, chunk)
        if score <= 0:
            continue

        lesson_key = chunk.get("lesson_key") or f"lesson-{chunk.get('chunk_index', 0)}"
        entry = scored_by_lesson.setdefault(
            lesson_key,
            {
                "lesson_name": chunk.get("lesson_name"),
                "chapter_name": chunk.get("chapter_name"),
                "chunks": [],
                "best_score": 0,
            },
        )
        entry["chunks"].append((score, chunk))
        entry["best_score"] = max(entry["best_score"], score)

    if not scored_by_lesson:
        return {
            "mode": "no_match",
            "chunks": [],
            "source_lesson_name": "",
            "current_lesson_name": collapse_whitespace(current_lesson_name),
        }

    ranked_lessons = sorted(
        scored_by_lesson.values(),
        key=lambda item: (
            item["best_score"],
            normalize_lesson_key(item.get("lesson_name")) == current_key,
        ),
        reverse=True,
    )
    selected_lesson = ranked_lessons[0]
    selected_chunks = sorted(
        selected_lesson["chunks"],
        key=lambda item: (item[0], -item[1].get("chunk_index", 0)),
        reverse=True,
    )

    return {
        "mode": "matched",
        "chunks": [chunk for _score, chunk in selected_chunks[:top_k]],
        "source_lesson_name": collapse_whitespace(selected_lesson.get("lesson_name")),
        "source_chapter_name": collapse_whitespace(selected_lesson.get("chapter_name")),
        "current_lesson_name": collapse_whitespace(current_lesson_name),
    }
