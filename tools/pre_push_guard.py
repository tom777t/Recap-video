# -*- coding: utf-8 -*-
"""
pre_push_guard.py - chay TRUOC khi commit/push. Hai moi nguy, mot cong.

1. KHOA / BI MAT. Mot API key tung bi day len repo nay (2026-08). Key do da bi
   thu hoi, nhung cai sai that su la: khong co gi DO truoc khi day. Guard nay
   quet moi file sap vao commit.

2. KICH THUOC. Repo co project chua source.mp4 va hang nghin frame. Mot lan
   `git add -A` vo y la mot file 2GB nam vinh vien trong lich su git - khong
   xoa duoc bang mot commit sau.

Guard KHONG tu sua gi. No bao, va tra ve exit != 0 de nguoi quyet dinh.

Dung:
    python tools/pre_push_guard.py
    python tools/pre_push_guard.py --max-mb 5
"""
from __future__ import annotations
import argparse, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Moi mau deu phai co mot NEO cu the. Mot regex kieu "chuoi dai ngau nhien" se
# keu tren moi hash git va thanh tieng on, roi bi tat - mot gate chet.
SECRET_PATTERNS = [
    (r"AIza[0-9A-Za-z_\-]{30,}", "Google API key"),
    (r"\bAQ\.[A-Za-z0-9_\-]{20,}", "Google OAuth / gcloud token"),
    (r"\bsk-[A-Za-z0-9]{20,}", "OpenAI-style secret key"),
    (r"\bsk-ant-[A-Za-z0-9\-_]{20,}", "Anthropic API key"),
    (r"\bghp_[A-Za-z0-9]{30,}", "GitHub personal access token"),
    (r"\bgho_[A-Za-z0-9]{30,}", "GitHub OAuth token"),
    (r"\bAKIA[0-9A-Z]{16}\b", "AWS access key id"),
    (r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----", "private key"),
    (r"(?i)\b(?:api[_-]?key|secret|password|passwd|token)\s*[:=]\s*"
     r"['\"][^'\"\s]{16,}['\"]", "hardcoded credential"),
]

TEXT_EXT = {".py", ".ps1", ".md", ".json", ".txt", ".yml", ".yaml", ".toml",
            ".cfg", ".ini", ".env", ".sh", ".bat", ".jsonc", ".gitignore"}
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules"}


def git(*a):
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout


def candidate_files():
    """Dung chinh git de biet file nao SE vao commit - ke ca file chua track,
    va da tru .gitignore. Khong tu di bo thu muc, vi nhu the la doan."""
    out = set()
    for line in git("status", "--porcelain", "-uall").splitlines():
        if not line.strip():
            continue
        p = line[3:].strip().strip('"')
        if " -> " in p:                       # rename
            p = p.split(" -> ")[-1]
        out.add(p)
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-mb", type=float, default=5.0)
    a = ap.parse_args()
    limit = a.max_mb * 1024 * 1024

    files = candidate_files()
    big, secrets, total, unreadable = [], [], 0, []

    for rel in files:
        fp = ROOT / rel
        if not fp.is_file():
            continue
        if any(part in SKIP_DIRS for part in fp.parts):
            continue
        try:
            sz = fp.stat().st_size
        except OSError:
            continue
        total += sz
        if sz > limit:
            big.append((rel, sz))
        if fp.suffix.lower() in TEXT_EXT or fp.name == ".gitignore":
            try:
                txt = fp.read_text(encoding="utf-8", errors="strict")
            except (UnicodeDecodeError, OSError):
                unreadable.append(rel)
                continue
            for pat, what in SECRET_PATTERNS:
                for m in re.finditer(pat, txt):
                    ln = txt[:m.start()].count("\n") + 1
                    frag = m.group(0)
                    frag = frag[:12] + "..." if len(frag) > 15 else frag
                    secrets.append((rel, ln, what, frag))

    print(f"files that would enter the commit: {len(files)}")
    print(f"total size: {total/1024/1024:.1f} MB")

    bad = False
    if secrets:
        bad = True
        print(f"\nSECRETS: {len(secrets)} match(es) - DO NOT COMMIT")
        for rel, ln, what, frag in secrets[:20]:
            print(f"  {rel}:{ln}  {what}  [{frag}]")
    else:
        print("secrets: none found")

    if big:
        bad = True
        print(f"\nOVERSIZE (> {a.max_mb:.0f} MB): {len(big)} file(s)")
        for rel, sz in sorted(big, key=lambda x: -x[1])[:20]:
            print(f"  {sz/1024/1024:8.1f} MB  {rel}")
        print("  -> add to .gitignore, or commit deliberately after saying why.")
    else:
        print(f"oversize: none over {a.max_mb:.0f} MB")

    if unreadable:
        # D-GREEN: mot file khong doc duoc la mot file CHUA DUOC QUET, va phai
        # duoc goi ten - khong duoc lang le tinh la sach.
        print(f"\nNOT SCANNED ({len(unreadable)} file(s) - not valid UTF-8):")
        for rel in unreadable[:10]:
            print(f"  {rel}")

    print("\nGUARD: " + ("FAIL - fix the above first" if bad else "clean"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
