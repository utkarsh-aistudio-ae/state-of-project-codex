#!/usr/bin/env python3
"""Thin Project Intel orchestrator.

First supported slice:

    Fireflies transcript -> untouched Markdown -> tagged Markdown copy

Later subcommands will add tagging, validation, and extraction. This script is
deliberately conservative about writes: untouched logs are not rewritten unless
the source content hash changes, and existing tagged copies are preserved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIREFLIES_SOURCE = "Fireflies"
UTC = timezone.utc


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
    tagged_path: Path
    content_hash: str
    markdown: str
    source_ref: str


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


def read_frontmatter_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            first = handle.readline()
            if first.strip() != "---":
                return None
            for line in handle:
                if line.strip() == "---":
                    return None
                match = re.match(r'^content_hash:\s*"?(sha256:[0-9a-f]{64})"?\s*$', line.strip())
                if match:
                    return match.group(1)
    except OSError:
        return None
    return None


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


def copy_tagged_from_untouched(untouched_path: Path, tagged_path: Path) -> WriteResult:
    tagged_path.parent.mkdir(parents=True, exist_ok=True)
    if tagged_path.exists():
        return WriteResult(tagged_path, "unchanged", "existing tagged copy preserved")
    shutil.copyfile(untouched_path, tagged_path)
    return WriteResult(tagged_path, "written", "created from untouched log")


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
    untouched_path, tagged_path = path_for_fireflies(transcript, occurred_at)
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
        f"tagged_copy: {yaml_quote(os.path.relpath(tagged_path, untouched_path.parent))}",
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
        tagged_path=tagged_path,
        content_hash=content_hash,
        markdown=markdown,
        source_ref=source_ref,
    )


def write_run_manifest(run_id: str, manifest: dict[str, Any]) -> WriteResult:
    manifest_path = ROOT / "logs" / "runs" / run_id / "manifest.json"
    payload = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    return write_text_if_changed(manifest_path, payload)


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
        tagged_result = copy_tagged_from_untouched(rendered.untouched_path, rendered.tagged_path)
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
            {
                "role": "tagged",
                "path": ensure_relative(tagged_result.path),
                "status": tagged_result.status,
                "reason": tagged_result.reason,
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

    tag = subparsers.add_parser("tag", help="Reserved for project tagger")
    tag.add_argument("path", nargs="?", help="Tagged Markdown file")
    tag.set_defaults(func=lambda _args: not_implemented("tag"))

    validate = subparsers.add_parser("validate", help="Reserved for tagged-log validator")
    validate.set_defaults(func=lambda _args: not_implemented("validate"))

    extract = subparsers.add_parser("extract", help="Reserved for tagged-note extractor")
    extract.set_defaults(func=lambda _args: not_implemented("extract"))

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
