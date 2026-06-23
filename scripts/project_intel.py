#!/usr/bin/env python3
"""Project Intel deterministic CLI for current source-log contracts.

First supported slice:

    Fireflies transcript -> untouched Markdown

Tagging is performed by Codex through the project-tagger skill. The script owns
deterministic mechanics for the current prototype: paths, hashes, derived
worklist status, manifests, validation, and extraction.

This file is not the final orchestration architecture. Long-term scheduling,
durable queue storage, datasource coordination, service boundaries, and review
UX are user-owned architecture decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
FIREFLIES_SOURCE = "Fireflies"
DEFAULT_PROJECT_SOURCES = ("GitHub", "Gmail", "Fireflies", "Drive")
UTC = timezone.utc
ANNOTATION_RE = re.compile(r"^\[([?]?[A-Za-z0-9-]+)\] \{([^}]*)\}$")
POSSIBLE_ANNOTATION_RE = re.compile(r"^\[[^\]]+\]\s*\{.*\}$")
ALLOWED_TAG_STATUSES = {"prepared", "tagged", "needs_review", "failed"}
TAGGER_VERSION = "project-intel-v1"


@dataclass(frozen=True)
class WriteResult:
    path: Path
    status: str
    reason: str | None = None


@dataclass(frozen=True)
class FirefliesRender:
    source_id: str
    title: str
    occurred_at: datetime
    untouched_path: Path
    content_hash: str
    markdown: str
    source_ref: str


@dataclass(frozen=True)
class ProjectRegistry:
    hash: str | None
    canonical_tags: set[str]
    project_tags: set[str]
    special_tags: set[str]
    exact_untagged: str


@dataclass(frozen=True)
class FrontmatterDocument:
    metadata: dict[str, Any]
    body: str
    had_frontmatter: bool


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def make_run_id(dt: datetime | None = None) -> str:
    return iso(dt or utc_now()).replace(":", "").replace("-", "")


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def format_hhmm(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%H%M")


def format_offset(seconds: Any) -> str:
    try:
        total_seconds = max(0, int(float(seconds)))
    except (TypeError, ValueError):
        return "00:00:00"
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def json_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def yaml_quote(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def ensure_relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def split_frontmatter_text(text: str) -> FrontmatterDocument:
    if not text.startswith("---\n"):
        return FrontmatterDocument(metadata={}, body=text, had_frontmatter=False)

    end_marker = text.find("\n---\n", 4)
    if end_marker == -1:
        return FrontmatterDocument(metadata={}, body=text, had_frontmatter=False)

    raw_frontmatter = text[4:end_marker]
    body = text[end_marker + len("\n---\n"):]
    parsed = yaml.safe_load(raw_frontmatter) if raw_frontmatter.strip() else {}
    if not isinstance(parsed, dict):
        parsed = {}
    return FrontmatterDocument(metadata=parsed, body=body, had_frontmatter=True)


def read_frontmatter(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return split_frontmatter_text(path.read_text(encoding="utf-8")).metadata
    except (OSError, yaml.YAMLError):
        return {}


def render_frontmatter(metadata: dict[str, Any], body: str) -> str:
    frontmatter = yaml.safe_dump(
        metadata,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
    return f"---\n{frontmatter}\n---\n\n{body.lstrip()}"


def read_frontmatter_hash(path: Path) -> str | None:
    metadata = read_frontmatter(path)
    content_hash = metadata.get("content_hash")
    if isinstance(content_hash, str) and re.match(r"^sha256:[0-9a-f]{64}$", content_hash):
        return content_hash
    return None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def registry_hash() -> str | None:
    registry_path = ROOT / "data" / "registry" / "project-tags.yaml"
    if not registry_path.exists():
        return None
    return file_sha256(registry_path)


def source_families_hash() -> str | None:
    source_families_path = ROOT / "data" / "registry" / "source-families.yaml"
    if not source_families_path.exists():
        return None
    return file_sha256(source_families_path)


def load_project_registry() -> ProjectRegistry:
    registry_path = ROOT / "data" / "registry" / "project-tags.yaml"
    if not registry_path.exists():
        raise RuntimeError(f"Missing registry: {ensure_relative(registry_path)}")

    canonical_tags: set[str] = set()
    project_tags: set[str] = set()
    special_tags: set[str] = set()
    exact_untagged = "[untagged] {Personal/admin context, not relevant to any AiStudio projects}"

    try:
        payload = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise RuntimeError(f"Invalid registry YAML: {ensure_relative(registry_path)}") from exc

    tags = payload.get("tags")
    if not isinstance(tags, list):
        raise RuntimeError(f"Registry missing `tags` list: {ensure_relative(registry_path)}")

    for entry in tags:
        if not isinstance(entry, dict):
            continue
        tag = entry.get("tag")
        kind = entry.get("kind")
        if not isinstance(tag, str) or not re.match(r"^[A-Za-z0-9-]+$", tag):
            continue
        canonical_tags.add(tag)
        if kind == "project":
            project_tags.add(tag)
        elif kind == "special":
            special_tags.add(tag)
        if tag == "untagged" and isinstance(entry.get("exact_annotation"), str):
            exact_untagged = entry["exact_annotation"]

    return ProjectRegistry(
        hash=registry_hash(),
        canonical_tags=canonical_tags,
        project_tags=project_tags,
        special_tags=special_tags,
        exact_untagged=exact_untagged,
    )


def write_text_if_changed(path: Path, content: str) -> WriteResult:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current == content:
            return WriteResult(path, "unchanged")
    path.write_text(content, encoding="utf-8")
    return WriteResult(path, "written")


def read_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json_if_changed(path: Path, payload: Any) -> WriteResult:
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    return write_text_if_changed(path, text)


def write_untouched(path: Path, content: str, content_hash: str) -> WriteResult:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_hash = read_frontmatter_hash(path)
    if existing_hash == content_hash:
        return WriteResult(path, "unchanged", "content hash unchanged")
    if path.exists() and existing_hash and existing_hash != content_hash:
        path.write_text(content, encoding="utf-8")
        return WriteResult(path, "written", "source content hash changed")
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current == content:
            return WriteResult(path, "unchanged")
    path.write_text(content, encoding="utf-8")
    return WriteResult(path, "written")


def tagged_path_for_untouched(untouched_path: Path) -> Path:
    untouched_root = ROOT / "data" / "raw" / "untouched"
    tagged_root = ROOT / "data" / "raw" / "tagged"
    try:
        return tagged_root / untouched_path.relative_to(untouched_root)
    except ValueError as exc:
        raise RuntimeError(f"Path is not under {ensure_relative(untouched_root)}: {untouched_path}") from exc


def run_json_command(command: list[str]) -> Any:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Command did not return valid JSON: {' '.join(command)}") from exc


def unwrap_fireflies_transcript(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeError("Fireflies response was not a JSON object")
    transcript = payload.get("data", {}).get("transcript")
    if not isinstance(transcript, dict):
        raise RuntimeError("Fireflies response missing data.transcript")
    return transcript


def parse_fireflies_datetime(transcript: dict[str, Any]) -> datetime:
    date_value = transcript.get("date")
    if isinstance(date_value, (int, float)):
        seconds = date_value / 1000 if date_value > 10_000_000_000 else date_value
        return datetime.fromtimestamp(seconds, tz=UTC)

    date_string = transcript.get("dateString")
    if isinstance(date_string, str) and date_string.strip():
        normalized = date_string.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except ValueError:
            pass

    raise RuntimeError("Fireflies transcript missing a parseable occurrence date")


def path_for_fireflies(transcript: dict[str, Any], occurred_at: datetime) -> tuple[Path, Path]:
    source_id = str(transcript.get("id") or "").strip()
    if not source_id:
        raise RuntimeError("Fireflies transcript missing id")
    month = occurred_at.strftime("%Y-%m")
    day = occurred_at.strftime("%Y-%m-%d")
    timestamp = format_hhmm(occurred_at)
    filename = f"transcript_{source_id}_{timestamp}.md"
    untouched = ROOT / "data" / "raw" / "untouched" / FIREFLIES_SOURCE / month / day / filename
    tagged = ROOT / "data" / "raw" / "tagged" / FIREFLIES_SOURCE / month / day / filename
    return untouched, tagged


def normalize_participants(participants: Any) -> list[str]:
    if not isinstance(participants, list):
        return []
    names: list[str] = []
    seen: set[str] = set()
    for item in participants:
        if item is None:
            continue
        for part in str(item).split(","):
            participant = part.strip()
            if participant and participant not in seen:
                names.append(participant)
                seen.add(participant)
    return names


def render_summary_value(value: Any, indent: int = 0) -> list[str]:
    prefix = "  " * indent
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [prefix + line for line in value.splitlines()]
    if isinstance(value, list):
        lines: list[str] = []
        for item in value:
            rendered = render_summary_value(item, indent + 1)
            if not rendered:
                continue
            first, *rest = rendered
            lines.append(f"{prefix}- {first.strip()}")
            lines.extend(rest)
        return lines
    if isinstance(value, dict):
        lines = []
        for key in sorted(value):
            rendered = render_summary_value(value[key], indent + 1)
            if rendered:
                lines.append(f"{prefix}- {key}:")
                lines.extend(rendered)
        return lines
    return [prefix + str(value)]


def render_fireflies_summary(summary: Any) -> str:
    if not isinstance(summary, dict) or not summary:
        return "_No Fireflies summary was included in the source response._\n"

    preferred_order = [
        "gist",
        "short_summary",
        "short_overview",
        "overview",
        "bullet_gist",
        "topics_discussed",
        "action_items",
        "outline",
        "keywords",
        "meeting_type",
        "transcript_chapters",
    ]
    keys = [key for key in preferred_order if key in summary]
    keys.extend(sorted(key for key in summary if key not in set(keys)))

    sections: list[str] = []
    for key in keys:
        lines = render_summary_value(summary.get(key))
        if not lines:
            continue
        title = key.replace("_", " ").title()
        sections.append(f"### {title}\n\n" + "\n".join(lines).strip())
    return "\n\n".join(sections).strip() + "\n"


def iter_speaker_turns(sentences: Any) -> list[dict[str, Any]]:
    if not isinstance(sentences, list):
        return []

    turns: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    for sentence in sentences:
        if not isinstance(sentence, dict):
            continue
        text = str(sentence.get("text") or sentence.get("raw_text") or "").strip()
        if not text:
            continue
        speaker = str(sentence.get("speaker_name") or "Unknown speaker").strip()
        start_time = sentence.get("start_time")
        end_time = sentence.get("end_time")
        entry = {
            "start_time": start_time,
            "end_time": end_time,
            "text": text,
        }

        if current and current["speaker"] == speaker:
            current["sentences"].append(entry)
            current["end_time"] = end_time
            continue

        current = {
            "speaker": speaker,
            "start_time": start_time,
            "end_time": end_time,
            "sentences": [entry],
        }
        turns.append(current)

    return turns


def render_fireflies_transcript(transcript: dict[str, Any], source_payload: Any) -> FirefliesRender:
    occurred_at = parse_fireflies_datetime(transcript)
    untouched_path, _tagged_path = path_for_fireflies(transcript, occurred_at)
    source_id = str(transcript.get("id") or "").strip()
    title = str(transcript.get("title") or source_id).strip()
    source_ref = str(transcript.get("transcript_url") or "").strip()
    if not source_ref:
        source_ref = f"https://app.fireflies.ai/view/{source_id}"
    content_hash = json_hash(source_payload)
    participants = normalize_participants(transcript.get("participants"))
    generated_at = iso(utc_now())

    frontmatter = [
        "---",
        f"source: {yaml_quote(FIREFLIES_SOURCE)}",
        f"source_id: {yaml_quote(source_id)}",
        f"title: {yaml_quote(title)}",
        f"occurred_at: {yaml_quote(iso(occurred_at))}",
        f"source_ref: {yaml_quote(source_ref)}",
        f"content_hash: {yaml_quote(content_hash)}",
        f"generated_at: {yaml_quote(generated_at)}",
        f"source_command: {yaml_quote(f'bin/fireflies-team transcript {source_id} --full')}",
        "---",
        "",
    ]

    lines: list[str] = []
    lines.extend(frontmatter)
    lines.append(f"# Fireflies Transcript: {title}")
    lines.append("")
    lines.append("## Metadata")
    lines.append("")
    lines.append(f"- Transcript id: `{source_id}`")
    lines.append(f"- Occurred at: `{iso(occurred_at)}`")
    lines.append(f"- Source URL: {source_ref}")
    lines.append(f"- Duration: `{transcript.get('duration', 'unknown')}`")
    lines.append(f"- Host: `{transcript.get('host_email') or 'unknown'}`")
    lines.append(f"- Organizer: `{transcript.get('organizer_email') or 'unknown'}`")
    if participants:
        lines.append("- Participants:")
        for participant in participants:
            lines.append(f"  - `{participant}`")
    else:
        lines.append("- Participants: `unknown`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(render_fireflies_summary(transcript.get("summary")).rstrip())
    lines.append("")
    lines.append("## Transcript")
    lines.append("")

    turns = iter_speaker_turns(transcript.get("sentences"))
    if not turns:
        lines.append("_No transcript sentences were included in the source response._")
    for turn in turns:
        start = format_offset(turn.get("start_time"))
        end = format_offset(turn.get("end_time"))
        speaker = turn["speaker"]
        lines.append(f"### {start} - {end} - {speaker}")
        lines.append("")
        for sentence in turn["sentences"]:
            sentence_start = format_offset(sentence.get("start_time"))
            lines.append(f"[{sentence_start}] {sentence['text']}")
        lines.append("")

    markdown = "\n".join(lines).rstrip() + "\n"
    return FirefliesRender(
        source_id=source_id,
        title=title,
        occurred_at=occurred_at,
        untouched_path=untouched_path,
        content_hash=content_hash,
        markdown=markdown,
        source_ref=source_ref,
    )


def write_run_manifest(run_id: str, manifest: dict[str, Any]) -> WriteResult:
    manifest_path = ROOT / "logs" / "runs" / run_id / "manifest.json"
    payload = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    return write_text_if_changed(manifest_path, payload)


def finalize_manifest(manifest: dict[str, Any], started_at: datetime) -> None:
    ended_at = utc_now()
    manifest["ended_at"] = iso(ended_at)
    manifest["duration_seconds"] = round((ended_at - started_at).total_seconds(), 3)
    manifest.setdefault("mutations_performed", False)
    manifest.setdefault("external_delivery", False)


def count_statuses(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        status = str(item.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def validation_report_path(run_id: str) -> Path:
    return ROOT / "logs" / "validation" / f"{run_id}.json"


def cursor_path(project: str, name: str) -> Path:
    return ROOT / "state" / "cursors" / project / f"{name}.json"


def report_path(project: str, run_id: str, ended_at: datetime) -> Path:
    day = ended_at.strftime("%Y-%m-%d")
    return ROOT / "data" / "reports" / project / day / f"{run_id}_state-of-project.md"


def load_source_families() -> list[dict[str, Any]]:
    source_families_path = ROOT / "data" / "registry" / "source-families.yaml"
    if not source_families_path.exists():
        return [
            {
                "name": source,
                "default_project_run": True,
                "reader_status": "not_implemented",
                "lookback_overlap_hours": 48,
            }
            for source in DEFAULT_PROJECT_SOURCES
        ]

    try:
        payload = yaml.safe_load(source_families_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise RuntimeError(f"Invalid source family YAML: {ensure_relative(source_families_path)}") from exc

    families = payload.get("source_families")
    if not isinstance(families, list):
        raise RuntimeError(f"Source family registry missing `source_families`: {ensure_relative(source_families_path)}")

    normalized: list[dict[str, Any]] = []
    for family in families:
        if not isinstance(family, dict):
            continue
        name = family.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        normalized.append(family)
    return normalized


def project_run_source_families() -> list[dict[str, Any]]:
    selected = [
        family for family in load_source_families()
        if family.get("default_project_run") is True
    ]
    if selected:
        return selected
    return [
        {
            "name": source,
            "default_project_run": True,
            "reader_status": "not_implemented",
            "lookback_overlap_hours": 48,
        }
        for source in DEFAULT_PROJECT_SOURCES
    ]


def fireflies_fetch(args: argparse.Namespace) -> int:
    source_id = args.source_id
    command = [str(ROOT / "bin" / "fireflies-team"), "transcript", source_id, "--full"]
    started_at = utc_now()
    run_id = make_run_id(started_at)
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "timestamp": iso(started_at),
        "started_at": iso(started_at),
        "trigger_source": "manual_cli",
        "source": FIREFLIES_SOURCE,
        "source_id": source_id,
        "command": " ".join(["bin/fireflies-team", "transcript", source_id, "--full"]),
        "mutations_performed": False,
        "external_delivery": False,
        "files": [],
        "validation_status": "not_run",
        "uncertain_tag_count": 0,
        "warnings": [],
        "errors": [],
    }

    try:
        payload = run_json_command(command)
        transcript = unwrap_fireflies_transcript(payload)
        rendered = render_fireflies_transcript(transcript, payload)
        untouched_result = write_untouched(
            rendered.untouched_path,
            rendered.markdown,
            rendered.content_hash,
        )
        manifest["title"] = rendered.title
        manifest["occurred_at"] = iso(rendered.occurred_at)
        manifest["content_hash"] = rendered.content_hash
        manifest["source_ref"] = rendered.source_ref
        manifest["files"] = [
            {
                "role": "untouched",
                "path": ensure_relative(untouched_result.path),
                "status": untouched_result.status,
                "reason": untouched_result.reason,
            },
        ]
    except Exception as exc:  # noqa: BLE001 - CLI should manifest failures.
        manifest["errors"].append(str(exc))
        manifest["status"] = "failed"
        finalize_manifest(manifest, started_at)
        manifest_result = write_run_manifest(run_id, manifest)
        print(f"Fireflies fetch failed. Manifest: {ensure_relative(manifest_result.path)}", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1

    manifest["status"] = "ok"
    finalize_manifest(manifest, started_at)
    manifest_result = write_run_manifest(run_id, manifest)

    print(f"Fireflies transcript fetched: {source_id}")
    for file_record in manifest["files"]:
        print(f"- {file_record['role']}: {file_record['status']} {file_record['path']}")
    print(f"- manifest: {ensure_relative(manifest_result.path)}")
    return 0


def parse_int(value: str | None) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def queue_item_for_untouched(untouched_path: Path, current_registry_hash: str | None) -> dict[str, Any]:
    source_metadata = read_frontmatter(untouched_path)
    source_hash = source_metadata.get("content_hash")
    tagged_path = tagged_path_for_untouched(untouched_path)
    item: dict[str, Any] = {
        "source_file": ensure_relative(untouched_path),
        "tagged_file": ensure_relative(tagged_path),
        "source_content_hash": source_hash,
        "registry_hash": current_registry_hash,
    }

    if not tagged_path.exists():
        item["status"] = "needs_tagging"
        item["reason"] = "tagged file does not exist"
        return item

    tagged_metadata = read_frontmatter(tagged_path)
    item["tag_status"] = tagged_metadata.get("tag_status")
    item["tagged_source_content_hash"] = tagged_metadata.get("source_content_hash")
    item["tagged_registry_hash"] = tagged_metadata.get("registry_hash")
    item["uncertain_annotation_count"] = parse_int(tagged_metadata.get("uncertain_annotation_count"))
    item["annotation_count"] = parse_int(tagged_metadata.get("annotation_count"))

    if not tagged_metadata.get("source_content_hash") or not tagged_metadata.get("registry_hash"):
        item["status"] = "stale_metadata"
        item["reason"] = "tagged file missing tagger metadata"
    elif tagged_metadata.get("tag_status") == "prepared":
        item["status"] = "needs_tagging"
        item["reason"] = "tagged copy is prepared but not yet annotated"
    elif tagged_metadata.get("source_content_hash") != source_hash:
        item["status"] = "stale_source"
        item["reason"] = "untouched source content hash changed"
    elif current_registry_hash and tagged_metadata.get("registry_hash") != current_registry_hash:
        item["status"] = "stale_registry"
        item["reason"] = "project registry changed since tagging"
    elif tagged_metadata.get("tag_status") in {"needs_review", "failed"}:
        item["status"] = tagged_metadata.get("tag_status")
        item["reason"] = "tagger marked file for attention"
    elif tagged_metadata.get("tag_status") != "tagged":
        item["status"] = "stale_metadata"
        item["reason"] = "tagged file has unknown tag_status"
    elif item["uncertain_annotation_count"] > 0:
        item["status"] = "needs_review"
        item["reason"] = "uncertain annotations need review"
    else:
        item["status"] = "current"
        item["reason"] = "tagged file metadata matches source and registry"
    return item


def build_queue_payload() -> dict[str, Any]:
    untouched_root = ROOT / "data" / "raw" / "untouched"
    current_registry_hash = registry_hash()
    items = [
        queue_item_for_untouched(path, current_registry_hash)
        for path in sorted(untouched_root.rglob("*.md"))
    ] if untouched_root.exists() else []

    counts: dict[str, int] = {}
    for item in items:
        counts[item["status"]] = counts.get(item["status"], 0) + 1

    payload = {
        "registry_hash": current_registry_hash,
        "total": len(items),
        "counts": counts,
        "items": items,
    }
    return payload


def queue(args: argparse.Namespace) -> int:
    payload = build_queue_payload()
    items = payload["items"]
    counts = payload["counts"]

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print(f"Tagging queue: {len(items)} source log(s)")
    for status in sorted(counts):
        print(f"- {status}: {counts[status]}")

    shown = items if args.all else [item for item in items if item["status"] != "current"]
    for item in shown:
        print(f"- {item['status']}: {item['source_file']} -> {item['tagged_file']}")
        print(f"  reason: {item['reason']}")
    return 0


def resolve_path_argument(path_value: str) -> Path:
    candidate = Path(path_value)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    return candidate.resolve()


def annotation_summary_for_text(text: str, registry: ProjectRegistry) -> tuple[int, int, list[dict[str, Any]]]:
    annotation_count = 0
    uncertain_count = 0
    errors: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        annotation, line_errors = validate_annotation_line(line, line_number, registry)
        errors.extend(line_errors)
        if annotation:
            annotation_count += 1
            if annotation.get("uncertain"):
                uncertain_count += 1
    return annotation_count, uncertain_count, errors


def infer_tag_status(annotation_count: int, uncertain_count: int) -> str:
    if annotation_count == 0:
        return "prepared"
    if uncertain_count > 0:
        return "needs_review"
    return "tagged"


def tag(args: argparse.Namespace) -> int:
    untouched_path = resolve_path_argument(args.path)
    untouched_root = ROOT / "data" / "raw" / "untouched"
    try:
        untouched_path.relative_to(untouched_root)
    except ValueError:
        print(f"Tag command expects a path under {ensure_relative(untouched_root)}", file=sys.stderr)
        print(f"- got: {untouched_path}", file=sys.stderr)
        return 2

    if not untouched_path.exists():
        print(f"Untouched source log does not exist: {ensure_relative(untouched_path)}", file=sys.stderr)
        return 2

    registry = load_project_registry()
    tagged_path = tagged_path_for_untouched(untouched_path)
    source_text = untouched_path.read_text(encoding="utf-8")
    source_doc = split_frontmatter_text(source_text)
    source_metadata = dict(source_doc.metadata)
    source_hash = source_metadata.get("content_hash")
    if not isinstance(source_hash, str) or not re.match(r"^sha256:[0-9a-f]{64}$", source_hash):
        source_hash = file_sha256(untouched_path)

    existing_metadata: dict[str, Any] = {}
    if tagged_path.exists():
        tagged_text = tagged_path.read_text(encoding="utf-8")
        tagged_doc = split_frontmatter_text(tagged_text)
        existing_metadata = dict(tagged_doc.metadata)
        body = tagged_doc.body
    else:
        body = source_doc.body

    annotation_count, uncertain_count, annotation_errors = annotation_summary_for_text(body, registry)
    if annotation_errors:
        print("Tag command found invalid annotation syntax or noncanonical tags.", file=sys.stderr)
        for error in annotation_errors[:20]:
            print(f"- line {error['line']}: {error['code']} - {error['message']}", file=sys.stderr)
        if len(annotation_errors) > 20:
            print(f"- additional errors: {len(annotation_errors) - 20}", file=sys.stderr)
        return 1

    tag_status = infer_tag_status(annotation_count, uncertain_count)
    updates = {
        "source_content_hash": source_hash,
        "tag_status": tag_status,
        "tagger": "codex",
        "tagger_version": TAGGER_VERSION,
        "registry_hash": registry.hash,
        "annotation_count": annotation_count,
        "uncertain_annotation_count": uncertain_count,
    }
    stable = all(existing_metadata.get(key) == value for key, value in updates.items())
    updates["tagged_at"] = existing_metadata.get("tagged_at") if stable and existing_metadata.get("tagged_at") else iso(utc_now())

    tagged_metadata = dict(source_metadata)
    tagged_metadata.update(updates)
    tagged_content = render_frontmatter(tagged_metadata, body)
    result = write_text_if_changed(tagged_path, tagged_content)

    print(f"Tagged copy {result.status}: {ensure_relative(tagged_path)}")
    print(f"- tag_status: {tag_status}")
    print(f"- annotations: {annotation_count}")
    print(f"- uncertain: {uncertain_count}")
    if tag_status == "prepared":
        print("- next: add canonical annotations, then rerun this command")
    return 0


def iter_tagged_logs() -> list[Path]:
    tagged_root = ROOT / "data" / "raw" / "tagged"
    if not tagged_root.exists():
        return []
    return sorted(tagged_root.rglob("*.md"))


def validate_annotation_line(
    line: str,
    line_number: int,
    registry: ProjectRegistry,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    match = ANNOTATION_RE.match(line)
    if not match:
        if POSSIBLE_ANNOTATION_RE.match(line):
            errors.append({
                "line": line_number,
                "code": "invalid_annotation_syntax",
                "message": "Annotation-like line does not match the supported syntax.",
            })
        return None, errors

    raw_tag, note = match.groups()
    annotation = {
        "line": line_number,
        "tag": raw_tag,
        "note": note,
        "uncertain": raw_tag.startswith("?"),
    }
    if not note.strip():
        errors.append({
            "line": line_number,
            "code": "empty_annotation_note",
            "message": "Annotation note must be concise but not empty.",
        })

    if raw_tag.startswith("?"):
        project = raw_tag[1:]
        if project not in registry.project_tags:
            errors.append({
                "line": line_number,
                "code": "invalid_uncertain_tag",
                "message": f"Uncertain tag must refer to a canonical project tag: {raw_tag}",
            })
        annotation["project"] = project
    elif raw_tag == "untagged":
        annotation["project"] = "untagged"
        annotation["special"] = True
        if line != registry.exact_untagged:
            errors.append({
                "line": line_number,
                "code": "invalid_untagged_annotation",
                "message": "The untagged annotation must match the registry exact_annotation.",
            })
    elif raw_tag in registry.project_tags:
        annotation["project"] = raw_tag
    elif raw_tag in registry.special_tags:
        errors.append({
            "line": line_number,
            "code": "invalid_special_tag_usage",
            "message": f"Special tag requires exact supported syntax: {raw_tag}",
        })
        annotation["project"] = raw_tag
    else:
        errors.append({
            "line": line_number,
            "code": "unknown_tag",
            "message": f"Unknown noncanonical tag: {raw_tag}",
        })
        annotation["project"] = raw_tag.lstrip("?")

    return annotation, errors


def validate_tagged_file(path: Path, registry: ProjectRegistry) -> dict[str, Any]:
    metadata = read_frontmatter(path)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not metadata:
        errors.append({
            "line": 1,
            "code": "missing_metadata",
            "message": "Tagged file must include frontmatter metadata.",
        })

    for key in ["source_content_hash", "tag_status", "tagger", "tagged_at", "registry_hash"]:
        if key not in metadata:
            errors.append({
                "line": 1,
                "code": "missing_tagger_metadata",
                "message": f"Tagged file missing `{key}` metadata.",
            })

    tag_status = metadata.get("tag_status")
    if tag_status and tag_status not in ALLOWED_TAG_STATUSES:
        errors.append({
            "line": 1,
            "code": "invalid_tag_status",
            "message": f"Unsupported tag_status `{tag_status}`.",
        })

    untouched_path: Path | None = None
    try:
        tagged_root = ROOT / "data" / "raw" / "tagged"
        untouched_path = ROOT / "data" / "raw" / "untouched" / path.relative_to(tagged_root)
    except ValueError:
        warnings.append({
            "line": 1,
            "code": "tagged_path_outside_contract",
            "message": "Tagged file is not under data/raw/tagged.",
        })
    if untouched_path:
        if not untouched_path.exists():
            errors.append({
                "line": 1,
                "code": "missing_untouched_source",
                "message": f"Matching untouched source log is missing: {ensure_relative(untouched_path)}",
            })
        else:
            untouched_metadata = read_frontmatter(untouched_path)
            untouched_hash = untouched_metadata.get("content_hash")
            if untouched_hash and metadata.get("source_content_hash") != untouched_hash:
                warnings.append({
                    "line": 1,
                    "code": "stale_source_content_hash",
                    "message": "Tagged source_content_hash does not match untouched content_hash.",
                })
    if registry.hash and metadata.get("registry_hash") and metadata.get("registry_hash") != registry.hash:
        warnings.append({
            "line": 1,
            "code": "stale_registry_hash",
            "message": "Tagged registry_hash does not match current project registry.",
        })

    annotation_count = 0
    uncertain_count = 0
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        annotation, line_errors = validate_annotation_line(line, line_number, registry)
        errors.extend(line_errors)
        if annotation:
            annotation_count += 1
            if annotation.get("uncertain"):
                uncertain_count += 1

    if annotation_count == 0:
        warnings.append({
            "line": 1,
            "code": "no_annotations",
            "message": "Tagged file contains no project annotations.",
        })
    if tag_status == "tagged" and annotation_count == 0:
        errors.append({
            "line": 1,
            "code": "tagged_without_annotations",
            "message": "tag_status=tagged requires at least one annotation.",
        })
    if tag_status == "prepared" and annotation_count > 0:
        warnings.append({
            "line": 1,
            "code": "prepared_with_annotations",
            "message": "Tagged file has annotations but tag_status is still prepared; rerun the tag command.",
        })

    declared_annotations = parse_int(metadata.get("annotation_count"))
    declared_uncertain = parse_int(metadata.get("uncertain_annotation_count"))
    if metadata and declared_annotations != annotation_count:
        warnings.append({
            "line": 1,
            "code": "annotation_count_mismatch",
            "message": f"Metadata annotation_count={declared_annotations}, actual={annotation_count}.",
        })
    if metadata and declared_uncertain != uncertain_count:
        warnings.append({
            "line": 1,
            "code": "uncertain_count_mismatch",
            "message": f"Metadata uncertain_annotation_count={declared_uncertain}, actual={uncertain_count}.",
        })

    return {
        "path": ensure_relative(path),
        "status": "ok" if not errors else "failed",
        "annotation_count": annotation_count,
        "uncertain_annotation_count": uncertain_count,
        "errors": errors,
        "warnings": warnings,
    }


def validate_tagged_logs(write_report: bool = True) -> tuple[dict[str, Any], Path | None]:
    registry = load_project_registry()
    files = [validate_tagged_file(path, registry) for path in iter_tagged_logs()]
    error_count = sum(len(file_result["errors"]) for file_result in files)
    warning_count = sum(len(file_result["warnings"]) for file_result in files)
    uncertain_count = sum(file_result["uncertain_annotation_count"] for file_result in files)
    report = {
        "timestamp": iso(utc_now()),
        "registry_hash": registry.hash,
        "status": "ok" if error_count == 0 else "failed",
        "file_count": len(files),
        "error_count": error_count,
        "warning_count": warning_count,
        "uncertain_annotation_count": uncertain_count,
        "files": files,
    }

    if not write_report:
        return report, None

    run_id = make_run_id()
    path = validation_report_path(run_id)
    write_text_if_changed(path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report, path


def validate(args: argparse.Namespace) -> int:
    report, path = validate_tagged_logs(write_report=True)
    print(f"Validation status: {report['status']}")
    print(f"- tagged files: {report['file_count']}")
    print(f"- errors: {report['error_count']}")
    print(f"- warnings: {report['warning_count']}")
    print(f"- uncertain annotations: {report['uncertain_annotation_count']}")
    if path:
        print(f"- report: {ensure_relative(path)}")
    return 0 if report["status"] == "ok" else 1


def is_annotation_line(line: str) -> bool:
    return ANNOTATION_RE.match(line) is not None


def parse_annotation(line: str, line_number: int, registry: ProjectRegistry) -> dict[str, Any]:
    annotation, errors = validate_annotation_line(line, line_number, registry)
    if errors or not annotation:
        raise RuntimeError(f"Invalid annotation at line {line_number}: {line}")
    return annotation


def frontmatter_end_line(lines: list[str]) -> int:
    if not lines or lines[0].strip() != "---":
        return 0
    for index, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            return index
    return 0


def extract_records_from_file(path: Path, registry: ProjectRegistry) -> list[dict[str, Any]]:
    metadata = read_frontmatter(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    records: list[dict[str, Any]] = []
    index = frontmatter_end_line(lines)

    while index < len(lines):
        line = lines[index]
        if not is_annotation_line(line):
            index += 1
            continue

        annotations: list[dict[str, Any]] = []
        while index < len(lines):
            current = lines[index]
            if current.strip() == "":
                index += 1
                continue
            if not is_annotation_line(current):
                break
            annotations.append(parse_annotation(current, index + 1, registry))
            index += 1

        while index < len(lines) and lines[index].strip() == "":
            index += 1

        block_start_index = index
        block_lines: list[str] = []
        while index < len(lines) and not is_annotation_line(lines[index]):
            block_lines.append(lines[index])
            index += 1

        while block_lines and block_lines[-1].strip() == "":
            block_lines.pop()

        block_text = "\n".join(block_lines).strip()
        block_start_line = block_start_index + 1 if block_lines else block_start_index
        block_end_line = block_start_index + len(block_lines)

        for annotation in annotations:
            records.append({
                "project": annotation["project"],
                "uncertain": annotation.get("uncertain", False),
                "special": annotation.get("special", False),
                "tag": annotation["tag"],
                "note": annotation["note"],
                "source": metadata.get("source"),
                "source_id": metadata.get("source_id"),
                "source_file": ensure_relative(path),
                "occurred_at": metadata.get("occurred_at"),
                "block_start_line": block_start_line,
                "block_end_line": block_end_line,
                "block_text": block_text,
            })

    return records


def extract_all_records() -> list[dict[str, Any]]:
    registry = load_project_registry()
    records: list[dict[str, Any]] = []
    for path in iter_tagged_logs():
        records.extend(extract_records_from_file(path, registry))
    return records


def write_extracted_records(records: list[dict[str, Any]]) -> WriteResult:
    output_path = ROOT / "data" / "derived" / "tagged-notes.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n" for record in records)
    return write_text_if_changed(output_path, payload)


def extract(args: argparse.Namespace) -> int:
    validation_report, _path = validate_tagged_logs(write_report=False)
    if validation_report["status"] != "ok":
        print("Extraction skipped because tagged-log validation failed.", file=sys.stderr)
        print(f"- errors: {validation_report['error_count']}", file=sys.stderr)
        return 1

    records = extract_all_records()
    result = write_extracted_records(records)
    uncertain_count = sum(1 for record in records if record.get("uncertain"))
    print(f"Extracted tagged notes: {len(records)}")
    print(f"- uncertain: {uncertain_count}")
    print(f"- output: {ensure_relative(result.path)}")
    return 0


def compute_source_window(cursor: dict[str, Any], now: datetime) -> tuple[datetime, datetime, int]:
    overlap_hours = parse_int(str(cursor.get("lookback_overlap_hours", 48)))
    if overlap_hours <= 0:
        overlap_hours = 48
    last_fetch = parse_iso_datetime(cursor.get("last_successful_fetch_at"))
    start = (last_fetch - timedelta(hours=overlap_hours)) if last_fetch else now - timedelta(days=7)
    return start, now, overlap_hours


def compute_report_window(project: str, now: datetime) -> tuple[datetime, datetime, dict[str, Any]]:
    cursor = read_json_file(cursor_path(project, "report"), {})
    last_report = parse_iso_datetime(cursor.get("last_successful_report_at"))
    floor = now - timedelta(days=7)
    start = max(last_report, floor) if last_report else floor
    return start, now, cursor


def build_source_fetch_plan(project: str, now: datetime) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    for family in project_run_source_families():
        source = str(family["name"])
        source_cursor_path = cursor_path(project, source)
        default_overlap = parse_int(str(family.get("lookback_overlap_hours", 48))) or 48
        cursor = read_json_file(source_cursor_path, {
            "project": project,
            "source": source,
            "lookback_overlap_hours": default_overlap,
            "seen_keys": {},
        })
        start, end, overlap_hours = compute_source_window(cursor, now)
        reader_status = str(family.get("reader_status") or "not_implemented")
        reason = str(family.get("skip_reason") or "batch reader not implemented yet")
        if reader_status not in {"implemented", "single_fetch_only"}:
            status = "skipped"
        else:
            status = "skipped"
            reason = "batch reader not wired into run-project yet"
        plans.append({
            "source": source,
            "cursor_path": ensure_relative(source_cursor_path),
            "fetch_start": iso(start),
            "fetch_end": iso(end),
            "lookback_overlap_hours": overlap_hours,
            "status": status,
            "reason": reason,
            "reader_status": reader_status,
            "source_class": family.get("source_class"),
            "canonical_for": family.get("canonical_for", []),
            "cursor_advanced": False,
        })
    return plans


def evidence_in_window(record: dict[str, Any], start: datetime, end: datetime) -> bool:
    occurred_at = parse_iso_datetime(record.get("occurred_at"))
    if not occurred_at:
        return False
    return start <= occurred_at <= end


def filter_project_records(
    records: list[dict[str, Any]],
    project: str,
    start: datetime,
    end: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    project_records = [
        record for record in records
        if record.get("project") == project and evidence_in_window(record, start, end)
    ]
    confirmed = [record for record in project_records if not record.get("uncertain")]
    uncertain = [record for record in project_records if record.get("uncertain")]
    return confirmed, uncertain


def render_project_report(
    project: str,
    run_id: str,
    report_start: datetime,
    report_end: datetime,
    confirmed_records: list[dict[str, Any]],
    uncertain_records: list[dict[str, Any]],
    source_fetches: list[dict[str, Any]],
    validation_report: dict[str, Any],
    queue_payload: dict[str, Any],
) -> str:
    lines = [
        f"# State of Project: {project}",
        "",
        f"Run: `{run_id}`",
        f"Window: `{iso(report_start)}` to `{iso(report_end)}`",
        "",
        "## TL;DR",
        "",
    ]
    if confirmed_records:
        lines.append(f"- {len(confirmed_records)} confirmed evidence record(s) found in the report window.")
    else:
        lines.append("- No confirmed project evidence was found in the report window.")
    if uncertain_records:
        lines.append(f"- {len(uncertain_records)} uncertain evidence record(s) need review.")
    source_gaps = [source for source in source_fetches if source["status"] != "ok"]
    if source_gaps:
        lines.append(f"- {len(source_gaps)} source batch reader(s) were not run; see Source Coverage.")

    lines.extend(["", "## Confirmed Evidence", ""])
    if not confirmed_records:
        lines.append("_No confirmed evidence records._")
    for record in confirmed_records:
        lines.extend([
            f"- `{record.get('source')}` `{record.get('occurred_at')}`: {record.get('note')}",
            f"  Source: `{record.get('source_file')}:{record.get('block_start_line')}`",
        ])

    lines.extend(["", "## Uncertain / Review", ""])
    if not uncertain_records:
        lines.append("_No uncertain project records._")
    for record in uncertain_records:
        lines.extend([
            f"- `{record.get('source')}` `{record.get('occurred_at')}`: {record.get('note')}",
            f"  Source: `{record.get('source_file')}:{record.get('block_start_line')}`",
        ])

    lines.extend(["", "## Source Coverage", ""])
    for source in source_fetches:
        lines.append(
            f"- {source['source']}: {source['status']} "
            f"({source['fetch_start']} to {source['fetch_end']}) - {source['reason']}"
        )

    lines.extend([
        "",
        "## Pipeline Checks",
        "",
        f"- Derived tagging worklist (`queue` command): `{queue_payload['counts']}`",
        f"- Validation: `{validation_report['status']}` "
        f"({validation_report['error_count']} errors, {validation_report['warning_count']} warnings)",
    ])
    return "\n".join(lines).rstrip() + "\n"


def run_project(args: argparse.Namespace) -> int:
    project = args.project
    started_at = utc_now()
    now = started_at
    run_id = make_run_id(started_at)
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "timestamp": iso(started_at),
        "started_at": iso(started_at),
        "trigger_source": "manual_cli",
        "command": f"run-project {project}",
        "project": project,
        "status": "started",
        "mutations_performed": False,
        "external_delivery": False,
        "warnings": [],
        "errors": [],
    }

    try:
        registry = load_project_registry()
        if project not in registry.project_tags:
            raise RuntimeError(f"Unknown project tag: {project}")

        report_start, report_end, report_cursor = compute_report_window(project, now)
        source_fetches = build_source_fetch_plan(project, now)
        queue_payload = build_queue_payload()
        blocking_items = [
            item for item in queue_payload["items"]
            if item["status"] != "current"
        ]

        manifest["registry_hash"] = registry.hash
        manifest["source_families_hash"] = source_families_hash()
        manifest["windows"] = {
            "report_start": iso(report_start),
            "report_end": iso(report_end),
        }
        manifest["source_fetches"] = source_fetches
        manifest["source_status_counts"] = count_statuses(source_fetches)
        manifest["queue"] = {
            "total": queue_payload["total"],
            "counts": queue_payload["counts"],
            "blocking_items": blocking_items,
        }

        if blocking_items:
            manifest["status"] = "tagging_required"
            manifest["errors"].append("Tagging worklist has non-current items.")
            finalize_manifest(manifest, started_at)
            manifest_result = write_run_manifest(run_id, manifest)
            print(f"Project run requires tagging: {project}", file=sys.stderr)
            print(f"- blocking items: {len(blocking_items)}", file=sys.stderr)
            print(f"- manifest: {ensure_relative(manifest_result.path)}", file=sys.stderr)
            return 2

        validation_report, validation_path = validate_tagged_logs(write_report=True)
        manifest["validation"] = {
            "status": validation_report["status"],
            "report": ensure_relative(validation_path) if validation_path else None,
            "file_count": validation_report["file_count"],
            "error_count": validation_report["error_count"],
            "warning_count": validation_report["warning_count"],
            "uncertain_annotation_count": validation_report["uncertain_annotation_count"],
        }
        if validation_report["status"] != "ok":
            manifest["status"] = "validation_failed"
            manifest["errors"].append("Tagged-log validation failed.")
            finalize_manifest(manifest, started_at)
            manifest_result = write_run_manifest(run_id, manifest)
            print(f"Project run validation failed: {project}", file=sys.stderr)
            print(f"- manifest: {ensure_relative(manifest_result.path)}", file=sys.stderr)
            return 1

        records = extract_all_records()
        extraction_result = write_extracted_records(records)
        confirmed_records, uncertain_records = filter_project_records(
            records,
            project,
            report_start,
            report_end,
        )
        manifest["extraction"] = {
            "output": ensure_relative(extraction_result.path),
            "record_count": len(records),
            "project_confirmed_count": len(confirmed_records),
            "project_uncertain_count": len(uncertain_records),
        }

        report_output_path = report_path(project, run_id, report_end)
        report_text = render_project_report(
            project,
            run_id,
            report_start,
            report_end,
            confirmed_records,
            uncertain_records,
            source_fetches,
            validation_report,
            queue_payload,
        )
        report_result = write_text_if_changed(report_output_path, report_text)
        manifest["report"] = {
            "path": ensure_relative(report_result.path),
            "status": report_result.status,
            "confirmed_count": len(confirmed_records),
            "uncertain_count": len(uncertain_records),
        }

        has_source_gaps = any(source["status"] != "ok" for source in source_fetches)
        manifest["cursors"] = {
            "report": {},
            "sources": [
                {
                    "source": source["source"],
                    "path": source["cursor_path"],
                    "advanced": source["cursor_advanced"],
                    "reason": source["reason"],
                }
                for source in source_fetches
            ],
        }
        if has_source_gaps:
            manifest["cursors"]["report"] = {
                "path": ensure_relative(cursor_path(project, "report")),
                "advanced": False,
                "reason": "source batch readers had coverage gaps",
            }
            manifest["status"] = "ok_with_source_gaps"
            manifest["warnings"].append("One or more source batch readers were skipped.")
        else:
            report_cursor_payload = {
                "project": project,
                "last_successful_report_at": iso(report_end),
                "last_run_id": run_id,
                "previous_cursor": report_cursor,
            }
            cursor_result = write_json_if_changed(cursor_path(project, "report"), report_cursor_payload)
            manifest["cursors"]["report"] = {
                "path": ensure_relative(cursor_result.path),
                "advanced": True,
                "status": cursor_result.status,
                "advanced_to": iso(report_end),
            }
            manifest["status"] = "ok"

    except Exception as exc:  # noqa: BLE001 - CLI should manifest failures.
        manifest["status"] = "failed"
        manifest["errors"].append(str(exc))
        finalize_manifest(manifest, started_at)
        manifest_result = write_run_manifest(run_id, manifest)
        print(f"Project run failed: {project}", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        print(f"- manifest: {ensure_relative(manifest_result.path)}", file=sys.stderr)
        return 1

    finalize_manifest(manifest, started_at)
    manifest_result = write_run_manifest(run_id, manifest)
    print(f"Project run complete: {project}")
    print(f"- status: {manifest['status']}")
    print(f"- report: {manifest['report']['path']}")
    print(f"- manifest: {ensure_relative(manifest_result.path)}")
    return 0


def not_implemented(command_name: str) -> int:
    print(f"`{command_name}` is reserved for the next Project Intel phase.", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Project Intel deterministic CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fireflies = subparsers.add_parser("fireflies", help="Fireflies source reader commands")
    fireflies_sub = fireflies.add_subparsers(dest="fireflies_command", required=True)
    fireflies_fetch_parser = fireflies_sub.add_parser("fetch", help="Fetch one Fireflies transcript")
    fireflies_fetch_parser.add_argument("source_id", help="Fireflies transcript id")
    fireflies_fetch_parser.set_defaults(func=fireflies_fetch)

    run_fireflies = subparsers.add_parser("run-fireflies", help="Run the current Fireflies reader slice")
    run_fireflies.add_argument("source_id", help="Fireflies transcript id")
    run_fireflies.set_defaults(func=fireflies_fetch)

    run_project_parser = subparsers.add_parser("run-project", help="Run deterministic project pipeline")
    run_project_parser.add_argument("project", help="Canonical project tag")
    run_project_parser.set_defaults(func=run_project)

    queue_parser = subparsers.add_parser("queue", help="Show derived tagging queue")
    queue_parser.add_argument("--json", action="store_true", help="Print queue as JSON")
    queue_parser.add_argument("--all", action="store_true", help="Include current files in text output")
    queue_parser.set_defaults(func=queue)

    tag_parser = subparsers.add_parser("tag", help="Create/update tagged copy metadata")
    tag_parser.add_argument("path", help="Untouched Markdown file")
    tag_parser.set_defaults(func=tag)

    validate_parser = subparsers.add_parser("validate", help="Validate tagged logs")
    validate_parser.set_defaults(func=validate)

    extract_parser = subparsers.add_parser("extract", help="Extract tagged notes as JSONL")
    extract_parser.set_defaults(func=extract)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
