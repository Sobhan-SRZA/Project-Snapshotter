"""Snapshot engine — walks directories and writes a text report."""

import os
from typing import Optional

from core.gitignore_engine import (
    GitIgnorePattern,
    parse_gitignore_file,
    build_default_matcher,
)


def create_snapshot(
    root_dir,
    include_gitignore,
    extra_patterns,
    output_file_path,
    log_func,
    cancel_event=None,
) -> bool:
    output_abs = os.path.abspath(output_file_path)
    base = build_default_matcher()
    manual = [r for r in (GitIgnorePattern(l) for l in extra_patterns) if r.valid]
    base.add(manual)
    if manual:
        log_func("log_manual_added", {"n": len(manual)}, "info")

    all_contents = []
    stats = {"processed": 0, "skipped": 0}
    log_func("log_start", {}, "info")

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
                continue

            if not is_dir and os.path.abspath(full) == output_abs:
                continue
            if current.is_ignored(rel, is_dir):
                stats["skipped"] += 1
                continue

            if is_dir:
                walk(full, rel, current)
            else:
                try:
                    with open(full, "r", encoding="utf-8") as f:
                        content = f.read()
                    all_contents.append(f"{rel}\n```\n{content}\n```\n\n")
                    stats["processed"] += 1
                    if stats["processed"] % 50 == 0:
                        log_func("log_progress", {"n": stats["processed"]}, "info")
                except UnicodeDecodeError:
                    stats["skipped"] += 1
                except (IOError, OSError) as e:
                    log_func("log_read_error", {"path": rel, "err": str(e)}, "error")
                    stats["skipped"] += 1

    try:
        walk(root_dir, "", base)
    except Exception as e:
        log_func("log_unexpected", {"err": str(e)}, "error")
        return False

    if cancel_event and cancel_event.is_set():
        log_func("log_cancelled", {}, "warn")
        return False

    try:
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write("".join(all_contents))
        log_func(
            "log_done",
            {"n": stats["processed"], "skipped": stats["skipped"]},
            "success",
        )
        log_func("log_output", {"path": output_file_path}, "success")
        return True
    except Exception as e:
        log_func("log_write_error", {"err": str(e)}, "error")
        return False
