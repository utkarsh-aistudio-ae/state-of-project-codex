#!/usr/bin/env python3
"""Thin Project Intel orchestrator.

First supported slice:

    Fireflies transcript -> untouched Markdown

Tagging is performed by Codex through the project-tagger skill. The script owns
deterministic state: paths, hashes, queue status, manifests, and later
validation/extraction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIREFLIES_SOURCE = "Fireflies"
UTC = timezone.utc
ANNOTATION_RE = re.compile(r"^\[([?]?[A-Za-z0-9-]+)\] \{([^}]*)\}$")
POSSIBLE_ANNOTATION_RE = re.compile(r"^\[[^\]]+\]\s*\{.*\}$")


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


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def read_frontmatter(path: Path) -> dict[str, str]:
    metadata: dict[str, str] = {}
    if not path.exists():
        return metadata
    try:
        with path.open("r", encoding="utf-8") as handle:
            first = handle.readline()
            if first.strip() != "---":
                return metadata
            for line in handle:
                if line.strip() == "---":
                    return metadata
                match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)\s*$", line.rstrip("\n"))
                if match:
                    key, raw_value = match.groups()
                    value = raw_value.strip()
                    if value.startswith('"') and value.endswith('"'):
                        try:
                            value = json.loads(value)
                        except json.JSONDecodeError:
                            value = value.strip('"')
                    metadata[key] = str(value)
    except OSError:
        return {}
    return metadata


def read_frontmatter_hash(path: Path) -> str | None:
    metadata = read_frontmatter(path)
    content_hash = metadata.get("content_hash")
    if content_hash and re.match(r"^sha256:[0-9a-f]{64}$", content_hash):
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


def load_project_registry() -> ProjectRegistry:
    registry_path = ROOT / "data" / "registry" / "project-tags.yaml"
    if not registry_path.exists():
        raise RuntimeError(f"Missing registry: {ensure_relative(registry_path)}")

    canonical_tags: set[str] = set()
    project_tags: set[str] = set()
    special_tags: set[str] = set()
    exact_untagged = "[untagged] {Personal/admin context, not relevant to any AiStudio projects}"

    current_tag: str | None = None
    for line in registry_path.read_text(encoding="utf-8").splitlines():
        tag_match = re.match(r"^\s+- tag:\s*([A-Za-z0-9-]+)\s*$", line)
        if tag_match:
            current_tag = tag_match.group(1)
            canonical_tags.add(current_tag)
            continue

        kind_match = re.match(r"^\s+kind:\s*([A-Za-z0-9-]+)\s*$", line)
        if kind_match and current_tag:
            kind = kind_match.group(1)
            if kind == "project":
                project_tags.add(current_tag)
            elif kind == "special":
                special_tags.add(current_tag)
            continue

        exact_match = re.match(r'^\s+exact_annotation:\s*"(.+)"\s*$', line)
        if exact_match and current_tag == "untagged":
            exact_untagged = exact_match.group(1)

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


def validation_report_path(run_id: str) -> Path:
    return ROOT / "logs" / "validation" / f"{run_id}.json"


def fireflies_fetch(args: argparse.Namespace) -> int:
    source_id = args.source_id
    command = [str(ROOT / "bin" / "fireflies-team"), "transcript", source_id, "--full"]
    run_id = iso(utc_now()).replace(":", "").replace("-", "")
    run_id = run_id.replace("T", "T").replace("Z", "Z")
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "timestamp": iso(utc_now()),
        "source": FIREFLIES_SOURCE,
        "source_id": source_id,
        "command": " ".join(["bin/fireflies-team", "transcript", source_id, "--full"]),
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
        manifest_result = write_run_manifest(run_id, manifest)
        print(f"Fireflies fetch failed. Manifest: {ensure_relative(manifest_result.path)}", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1

    manifest["status"] = "ok"
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

    if not tagged_metadata.get("source_content_hash") or not tagged_metadata.get("registry_hash"):
        item["status"] = "stale_metadata"
        item["reason"] = "tagged file missing tagger metadata"
    elif tagged_metadata.get("source_content_hash") != source_hash:
        item["status"] = "stale_source"
        item["reason"] = "untouched source content hash changed"
    elif current_registry_hash and tagged_metadata.get("registry_hash") != current_registry_hash:
        item["status"] = "stale_registry"
        item["reason"] = "project registry changed since tagging"
    elif tagged_metadata.get("tag_status") in {"needs_review", "failed"}:
        item["status"] = tagged_metadata.get("tag_status")
        item["reason"] = "tagger marked file for attention"
    elif item["uncertain_annotation_count"] > 0:
        item["status"] = "needs_review"
        item["reason"] = "uncertain annotations need review"
    else:
        item["status"] = "current"
        item["reason"] = "tagged file metadata matches source and registry"
    return item


def queue(args: argparse.Namespace) -> int:
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

    run_id = iso(utc_now()).replace(":", "").replace("-", "")
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


def extract(args: argparse.Namespace) -> int:
    validation_report, _path = validate_tagged_logs(write_report=False)
    if validation_report["status"] != "ok":
        print("Extraction skipped because tagged-log validation failed.", file=sys.stderr)
        print(f"- errors: {validation_report['error_count']}", file=sys.stderr)
        return 1

    registry = load_project_registry()
    records: list[dict[str, Any]] = []
    for path in iter_tagged_logs():
        records.extend(extract_records_from_file(path, registry))

    output_path = ROOT / "data" / "derived" / "tagged-notes.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n" for record in records)
    write_text_if_changed(output_path, payload)

    uncertain_count = sum(1 for record in records if record.get("uncertain"))
    print(f"Extracted tagged notes: {len(records)}")
    print(f"- uncertain: {uncertain_count}")
    print(f"- output: {ensure_relative(output_path)}")
    return 0


def not_implemented(command_name: str) -> int:
    print(f"`{command_name}` is reserved for the next Project Intel phase.", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Project Intel thin orchestrator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fireflies = subparsers.add_parser("fireflies", help="Fireflies source reader commands")
    fireflies_sub = fireflies.add_subparsers(dest="fireflies_command", required=True)
    fireflies_fetch_parser = fireflies_sub.add_parser("fetch", help="Fetch one Fireflies transcript")
    fireflies_fetch_parser.add_argument("source_id", help="Fireflies transcript id")
    fireflies_fetch_parser.set_defaults(func=fireflies_fetch)

    run_fireflies = subparsers.add_parser("run-fireflies", help="Run the current Fireflies reader slice")
    run_fireflies.add_argument("source_id", help="Fireflies transcript id")
    run_fireflies.set_defaults(func=fireflies_fetch)

    queue_parser = subparsers.add_parser("queue", help="Show derived tagging queue")
    queue_parser.add_argument("--json", action="store_true", help="Print queue as JSON")
    queue_parser.add_argument("--all", action="store_true", help="Include current files in text output")
    queue_parser.set_defaults(func=queue)

    tag = subparsers.add_parser("tag", help="Reserved for project tagger")
    tag.add_argument("path", nargs="?", help="Untouched Markdown file")
    tag.set_defaults(func=lambda _args: not_implemented("tag"))

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
