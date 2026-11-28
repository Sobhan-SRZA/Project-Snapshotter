"""Snapshot engine — walks directories and writes a structured text report."""

import os
from typing import Optional

from core.gitignore_engine import (
    GitIgnorePattern,
    parse_gitignore_file,
    build_default_matcher,
)


def _format_bytes(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.2f} MB"


def create_snapshot(
    root_dir,
    include_gitignore,
    extra_patterns,
    output_file_path,
    log_func,
    cancel_event=None,
    on_stats=None,
) -> bool:
    output_abs = os.path.abspath(output_file_path)
    base = build_default_matcher()
    manual = [r for r in (GitIgnorePattern(l) for l in extra_patterns) if r.valid]
    base.add(manual)
    if manual:
        log_func("log_manual_added", {"n": len(manual)}, "info")

    all_contents = []
    stats = {"processed": 0, "skipped": 0, "bytes": 0}
    log_func("log_start", {}, "info")

    def notify_stats():
        if callable(on_stats):
            on_stats(dict(stats))

    def walk(dir_path, rel_dir, matcher):
        if cancel_event and cancel_event.is_set():
            return
        current = matcher
        if include_gitignore:
            gi = os.path.join(dir_path, ".gitignore")
            if os.path.isfile(gi):
                rules = parse_gitignore_file(gi)
                if rules:
                    current = matcher.copy()
                    current.add(rules)
                    rel_gi = f"{rel_dir}/.gitignore" if rel_dir else ".gitignore"
                    log_func("log_gitignore", {"n": len(rules), "path": rel_gi}, "info")

        try:
            entries = sorted(os.scandir(dir_path), key=lambda e: e.name)
        except (PermissionError, OSError):
            log_func("log_access_error", {"path": dir_path}, "warn")
            return

        for entry in entries:
            if cancel_event and cancel_event.is_set():
                return
            name, full = entry.name, entry.path
            rel = f"{rel_dir}/{name}" if rel_dir else name
            try:
                is_dir = entry.is_dir()
            except OSError:
                stats["skipped"] += 1
                notify_stats()
                continue

            if not is_dir and os.path.abspath(full) == output_abs:
                continue
            if current.is_ignored(rel, is_dir):
                stats["skipped"] += 1
                notify_stats()
                continue

            if is_dir:
                walk(full, rel, current)
            else:
                try:
                    with open(full, "r", encoding="utf-8") as f:
                        content = f.read()
                    chunk = f"{rel}\n```\n{content}\n```\n\n"
                    all_contents.append(chunk)
                    stats["processed"] += 1
                    stats["bytes"] += len(chunk.encode("utf-8"))
                    notify_stats()
                    if stats["processed"] % 50 == 0:
                        log_func("log_progress", {"n": stats["processed"]}, "info")
                except UnicodeDecodeError:
                    stats["skipped"] += 1
                    notify_stats()
                except (IOError, OSError) as e:
                    log_func("log_read_error", {"path": rel, "err": str(e)}, "error")
                    stats["skipped"] += 1
                    notify_stats()

    try:
        walk(root_dir, "", base)
    except Exception as e:
        log_func("log_unexpected", {"err": str(e)}, "error")
        return False

    if cancel_event and cancel_event.is_set():
        log_func("log_cancelled", {}, "warn")
        return False

    try:
        out_dir = os.path.dirname(output_abs)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        final_text = "".join(all_contents)
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write(final_text)
        size_str = _format_bytes(len(final_text.encode("utf-8")))
        log_func(
            "log_done",
            {
                "n": stats["processed"],
                "skipped": stats["skipped"],
                "size": size_str,
            },
            "success",
        )
        log_func("log_output", {"path": output_file_path}, "success")
        return True
    except Exception as e:
        log_func("log_write_error", {"err": str(e)}, "error")
        return False
