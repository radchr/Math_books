"""Git-backed idea & scenario bank (content/bank/*.json) with rebuildable SQLite index."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from math_books.languages import SUPPORTED_LANGUAGES
from math_books.lessons import lesson_path, validate_lesson_data
from math_books.media_io import atomic_json

BANK_STATUSES = ("idea", "draft", "promoted", "produced", "parked")
_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def bank_dir(root: Path) -> Path:
    return root / "content" / "bank"


def bank_entry_path(root: Path, entry_id: str) -> Path:
    if not _ID_RE.fullmatch(entry_id):
        raise ValueError(f"Invalid bank entry ID {entry_id!r}")
    return bank_dir(root) / f"{entry_id}.json"


def index_path(root: Path) -> Path:
    return root / ".cache" / "bank.sqlite"


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key in bank entry: {key}")
        result[key] = value
    return result


def _validate_audience(audience: object) -> dict[str, int]:
    if not isinstance(audience, dict):
        raise ValueError("audience must be an object with min_age and max_age")
    min_age = audience.get("min_age")
    max_age = audience.get("max_age")
    if type(min_age) is not int or type(max_age) is not int or not (5 <= min_age <= max_age <= 99):
        raise ValueError("audience requires integer min_age/max_age within 5..99")
    return {"min_age": min_age, "max_age": max_age}


def _templates_in_entry(entry: dict[str, Any]) -> list[str]:
    templates: set[str] = set()
    core = entry.get("core_concept")
    if isinstance(core, dict):
        for name in core.get("templates_used", []):
            if isinstance(name, str) and name.strip():
                templates.add(name)
    draft = entry.get("lesson_draft")
    if isinstance(draft, dict):
        for scene in draft.get("scenes", []):
            if isinstance(scene, dict):
                visual = scene.get("visual")
                if isinstance(visual, dict) and isinstance(visual.get("template"), str):
                    templates.add(visual["template"])
                else:
                    templates.add("text_card")
    return sorted(templates)


def validate_bank_entry(data: object, expected_id: str | None = None) -> dict[str, Any]:
    """Validate a bank JSON entry (idea/draft/promoted/produced/parked)."""
    if not isinstance(data, dict):
        raise ValueError("Bank entry must be a JSON object")
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported bank entry schema_version")
    entry_id = data.get("id")
    if not isinstance(entry_id, str) or not _ID_RE.fullmatch(entry_id):
        raise ValueError(f"Invalid bank entry id: {entry_id!r}")
    if expected_id is not None and entry_id != expected_id:
        raise ValueError(f"Bank entry id {entry_id!r} does not match filename {expected_id!r}")
    status = data.get("status")
    if status not in BANK_STATUSES:
        raise ValueError(f"Unsupported bank status {status!r}; choose one of {', '.join(BANK_STATUSES)}")
    domain = data.get("domain")
    if not isinstance(domain, str) or not domain.strip():
        raise ValueError("Bank entry requires a non-empty domain")
    theme = data.get("theme", "neutral_dark")
    if not isinstance(theme, str) or not theme.strip():
        raise ValueError("Bank entry theme must be a non-empty string")
    _validate_audience(data.get("audience"))

    tags = data.get("tags", [])
    if not isinstance(tags, list) or any(not isinstance(t, str) or not t.strip() for t in tags):
        raise ValueError("Bank entry tags must be a list of non-empty strings")

    title = data.get("title")
    if not isinstance(title, dict) or set(title) != set(SUPPORTED_LANGUAGES):
        raise ValueError("Bank entry title requires complete uk/ru/en translations")
    if any(not isinstance(v, str) or not v.strip() for v in title.values()):
        raise ValueError("Bank entry title translations must be non-empty")

    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("Bank entry requires a non-empty summary")

    alt_hooks = data.get("alt_hooks", [])
    if not isinstance(alt_hooks, list):
        raise ValueError("alt_hooks must be a list")
    for hook in alt_hooks:
        if not isinstance(hook, dict) or set(hook) != set(SUPPORTED_LANGUAGES):
            raise ValueError("Each alt_hook requires complete uk/ru/en translations")
        if any(not isinstance(v, str) or not v.strip() for v in hook.values()):
            raise ValueError("alt_hook translations must be non-empty")

    draft = data.get("lesson_draft")
    if status in ("draft", "promoted", "produced") and draft is None:
        raise ValueError(f"Bank entry {entry_id!r} with status {status!r} requires lesson_draft")
    if draft is not None:
        if not isinstance(draft, dict):
            raise ValueError("lesson_draft must be an object")
        draft_topic = draft.get("topic", entry_id)
        if not isinstance(draft_topic, str) or not _ID_RE.fullmatch(draft_topic):
            raise ValueError("lesson_draft.topic must be a valid topic slug")
        for lang in SUPPORTED_LANGUAGES:
            validate_lesson_data(draft, draft_topic, lang, source_label=f"bank:{entry_id}")
    return data


def load_bank_entry(root: Path, entry_id: str) -> dict[str, Any]:
    path = bank_entry_path(root, entry_id)
    if not path.is_file():
        raise FileNotFoundError(f"Bank entry not found: {entry_id!r} ({path})")
    raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
    return validate_bank_entry(raw, expected_id=entry_id)


def _source_signature(files: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        stat = path.stat()
        digest.update(f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}\n".encode())
    return digest.hexdigest()


def sync_bank_index(root: Path) -> Path:
    """Rebuild .cache/bank.sqlite from content/bank/*.json whenever source files change."""
    folder = bank_dir(root)
    files = sorted(folder.glob("*.json")) if folder.is_dir() else []
    sig = _source_signature(files)
    db_path = index_path(root)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        row = conn.execute("SELECT value FROM meta WHERE key = 'signature'").fetchone()
        if row is not None and row[0] == sig:
            return db_path

        conn.executescript(
            """
            DROP TABLE IF EXISTS entry_tags;
            DROP TABLE IF EXISTS entry_templates;
            DROP TABLE IF EXISTS entries;
            CREATE TABLE entries (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                domain TEXT NOT NULL,
                theme TEXT NOT NULL,
                min_age INTEGER NOT NULL,
                max_age INTEGER NOT NULL,
                title_uk TEXT NOT NULL,
                title_ru TEXT NOT NULL,
                title_en TEXT NOT NULL,
                summary TEXT NOT NULL,
                promoted_topic TEXT
            );
            CREATE TABLE entry_tags (
                entry_id TEXT NOT NULL,
                tag TEXT NOT NULL,
                PRIMARY KEY (entry_id, tag)
            );
            CREATE TABLE entry_templates (
                entry_id TEXT NOT NULL,
                template TEXT NOT NULL,
                PRIMARY KEY (entry_id, template)
            );
            """
        )
        for path in files:
            entry = validate_bank_entry(
                json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys),
                expected_id=path.stem,
            )
            promoted = entry.get("promoted_lesson")
            promoted_topic = promoted.get("topic") if isinstance(promoted, dict) else None
            conn.execute(
                """
                INSERT INTO entries
                (id, status, domain, theme, min_age, max_age, title_uk, title_ru, title_en, summary, promoted_topic)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry["id"],
                    entry["status"],
                    entry["domain"],
                    entry.get("theme", "neutral_dark"),
                    entry["audience"]["min_age"],
                    entry["audience"]["max_age"],
                    entry["title"]["uk"],
                    entry["title"]["ru"],
                    entry["title"]["en"],
                    entry["summary"],
                    promoted_topic,
                ),
            )
            for tag in set(entry.get("tags", [])):
                conn.execute("INSERT INTO entry_tags (entry_id, tag) VALUES (?, ?)", (entry["id"], tag))
            for template in _templates_in_entry(entry):
                conn.execute("INSERT INTO entry_templates (entry_id, template) VALUES (?, ?)", (entry["id"], template))
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('signature', ?)", (sig,))
        conn.commit()
    finally:
        conn.close()
    return db_path


def query_bank(
    root: Path,
    *,
    status: str | None = None,
    domain: str | None = None,
    tag: str | None = None,
    template: str | None = None,
) -> list[dict[str, Any]]:
    """Query the rebuildable SQLite index for matching scenario bank entries."""
    if status is not None and status not in BANK_STATUSES:
        raise ValueError(f"Unsupported bank status {status!r}")
    db_path = sync_bank_index(root)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        clauses = ["1=1"]
        params: list[Any] = []
        if status is not None:
            clauses.append("e.status = ?")
            params.append(status)
        if domain is not None:
            clauses.append("e.domain = ?")
            params.append(domain)
        if tag is not None:
            clauses.append("EXISTS (SELECT 1 FROM entry_tags t WHERE t.entry_id = e.id AND t.tag = ?)")
            params.append(tag)
        if template is not None:
            clauses.append("EXISTS (SELECT 1 FROM entry_templates m WHERE m.entry_id = e.id AND m.template = ?)")
            params.append(template)

        rows = conn.execute(
            f"SELECT * FROM entries e WHERE {' AND '.join(clauses)} ORDER BY e.id",
            params,
        ).fetchall()
        results: list[dict[str, Any]] = []
        for row in rows:
            eid = row["id"]
            tags = [r[0] for r in conn.execute("SELECT tag FROM entry_tags WHERE entry_id = ? ORDER BY tag", (eid,))]
            templates = [
                r[0]
                for r in conn.execute(
                    "SELECT template FROM entry_templates WHERE entry_id = ? ORDER BY template", (eid,)
                )
            ]
            results.append(
                {
                    "id": eid,
                    "status": row["status"],
                    "domain": row["domain"],
                    "theme": row["theme"],
                    "audience": {"min_age": row["min_age"], "max_age": row["max_age"]},
                    "title": {"uk": row["title_uk"], "ru": row["title_ru"], "en": row["title_en"]},
                    "summary": row["summary"],
                    "promoted_topic": row["promoted_topic"],
                    "tags": tags,
                    "templates": templates,
                }
            )
        return results
    finally:
        conn.close()


def promote_bank_entry(root: Path, entry_id: str, *, topic: str | None = None) -> dict[str, Any]:
    """Export a validated bank draft into content/lessons/<topic>.json while keeping the bank record reusable."""
    from math_books.topics import VIDEO_TOPICS

    entry = load_bank_entry(root, entry_id)
    draft = entry.get("lesson_draft")
    if not isinstance(draft, dict):
        raise ValueError(f"Bank entry {entry_id!r} has no lesson_draft; convert idea to draft before promoting")

    target_topic = topic or str(draft.get("topic", entry_id))
    if target_topic in VIDEO_TOPICS:
        raise ValueError(f"Target topic {target_topic!r} collides with a legacy topic")
    dest = lesson_path(root, target_topic)
    if dest.exists():
        raise FileExistsError(f"Lesson already exists: {dest}; choose a different --topic")

    exported = {**draft, "topic": target_topic}
    if "domain" not in exported and entry.get("domain"):
        exported["domain"] = entry["domain"]
    if "theme" not in exported and entry.get("theme"):
        exported["theme"] = entry["theme"]
    for lang in SUPPORTED_LANGUAGES:
        validate_lesson_data(exported, target_topic, lang, source_label=f"promote:{entry_id}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(dest, exported)

    updated = dict(entry)
    updated["status"] = "promoted"
    updated["promoted_lesson"] = {
        "topic": target_topic,
        "path": str(dest.relative_to(root)),
        "promoted_at": datetime.now(UTC).isoformat(),
    }
    atomic_json(bank_entry_path(root, entry_id), updated)
    sync_bank_index(root)
    return {
        "entry_id": entry_id,
        "topic": target_topic,
        "lesson_path": str(dest),
        "bank_path": str(bank_entry_path(root, entry_id)),
        "status": "promoted",
        "next_steps": [f"uv run math-books review {target_topic} --lang {lang} --init" for lang in SUPPORTED_LANGUAGES],
    }
