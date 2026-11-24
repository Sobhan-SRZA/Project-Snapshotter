"""Git-compatible .gitignore pattern engine."""

import os
import re
from typing import List, Optional


class GitIgnorePattern:
    __slots__ = ("original", "negation", "directory_only", "anchored", "regex", "valid")

    def __init__(self, line: str):
        self.original = line
        self.negation = False
        self.directory_only = False
        self.anchored = False
        self.regex: Optional[re.Pattern] = None
        self.valid = True
        self._compile(line)

    def _compile(self, line: str):
        p = line
        if not p or p.startswith("#"):
            self.valid = False
            return
        if p.startswith("!"):
            self.negation = True
            p = p[1:]
        elif p.startswith("\\!") or p.startswith("\\#"):
            p = p[1:]
        p = self._rstrip_unescaped_spaces(p)
        if not p:
            self.valid = False
            return
        if p.endswith("/"):
            self.directory_only = True
            p = p[:-1]
            if not p:
                self.valid = False
                return
        if p.startswith("/"):
            self.anchored = True
            p = p[1:]
        elif "/" in p:
            self.anchored = True
        body = self._translate(p)
        if not self.anchored:
            body = "(?:.*/)?" + body
        try:
            self.regex = re.compile("^" + body + "$")
        except re.error:
            self.valid = False

    @staticmethod
    def _rstrip_unescaped_spaces(p: str) -> str:
        while p.endswith(" "):
            j, bs = len(p) - 2, 0
            while j >= 0 and p[j] == "\\":
                bs += 1
                j -= 1
            if bs % 2 == 1:
                break
            p = p[:-1]
        return p

    @staticmethod
    def _translate(p: str) -> str:
        i, n, out = 0, len(p), []
        while i < n:
            c = p[i]
            if c == "*":
                if i + 1 < n and p[i + 1] == "*":
                    if i + 2 < n and p[i + 2] == "/":
                        out.append("(?:.*/)?")
                        i += 3
                    elif i + 2 == n:
                        out.append(".*")
                        i += 2
                    else:
                        out.append("[^/]*")
                        i += 2
                else:
                    out.append("[^/]*")
                    i += 1
            elif c == "?":
                out.append("[^/]")
                i += 1
            elif c == "[":
                j = i + 1
                if j < n and p[j] in ("!", "^"):
                    j += 1
                if j < n and p[j] == "]":
                    j += 1
                while j < n and p[j] != "]":
                    j += 1
                if j >= n:
                    out.append(re.escape(c))
                    i += 1
                else:
                    inner = p[i + 1 : j]
                    if inner.startswith("!"):
                        inner = "^" + inner[1:]
                    out.append("[" + inner + "]")
                    i = j + 1
            elif c == "\\":
                if i + 1 < n:
                    out.append(re.escape(p[i + 1]))
                    i += 2
                else:
                    out.append(re.escape(c))
                    i += 1
            else:
                out.append(re.escape(c))
                i += 1
        return "".join(out)

    def matches(self, rel_path: str, is_dir: bool) -> bool:
        if not self.valid or self.regex is None:
            return False
        if self.directory_only and not is_dir:
            return False
        return self.regex.match(rel_path) is not None


def parse_gitignore_file(path: str) -> List[GitIgnorePattern]:
    out = []
    if not os.path.isfile(path):
        return out
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.rstrip("\r\n")
                r = GitIgnorePattern(line)
                if r.valid:
                    out.append(r)
    except Exception:
        pass
    return out


class GitIgnoreMatcher:
    def __init__(self, rules: Optional[List[GitIgnorePattern]] = None):
        self.rules = list(rules) if rules else []

    def copy(self):
        return GitIgnoreMatcher(self.rules)

    def add(self, rules):
        self.rules.extend(rules)

    def is_ignored(self, rel_path: str, is_dir: bool) -> bool:
        ignored = False
        for rule in self.rules:
            if rule.matches(rel_path, is_dir):
                ignored = not rule.negation
        return ignored


def build_default_matcher() -> GitIgnoreMatcher:
    defaults = [
        ".git/",
        "node_modules/",
        "__pycache__/",
        "*.pyc",
        "*.tmp",
        "venv/",
        ".venv/",
        ".vscode/",
        ".idea/",
        "dist/",
        "build/",
        ".DS_Store",
    ]
    return GitIgnoreMatcher(
        [r for r in (GitIgnorePattern(l) for l in defaults) if r.valid]
    )
