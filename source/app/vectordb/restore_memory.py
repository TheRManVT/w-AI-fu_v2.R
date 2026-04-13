"""
Memory Database Restore Tool
==============================
Merges a backup vectordb database into a (possibly corrupted) current database.

Modes
-----
  Default mode:
    Starts from the current DB and adds back whatever chunks are missing from
    the backup. Preserves all healthy chunks already in the current file.
    Result: current chunks + missing backup chunks + new post-backup chunks.

  --full-restore mode:
    Starts from the backup (which has all original embeddings intact) and
    appends only the new post-backup chunks on top, re-embedding them.
    Use this when the current DB is corrupted and you want the maximum
    number of chunks restored (backup chunks + new chunks).

Requirements
------------
  pip install sentence-transformers   (optional but recommended)
  numpy                               (usually bundled with sentence-transformers)

Usage
-----
  # Default: merge missing backup chunks into current
  python restore_memory.py --backup database.txt.backup_1234 --current database.txt --output database.txt

  # Full restore: backup as base + new chunks on top (maximum chunks)
  python restore_memory.py --backup database.txt.backup_1234 --current database.txt --output database.txt --full-restore

  # Preview without writing anything
  python restore_memory.py --backup database.txt.backup_1234 --current database.txt --output database.txt --dry-run
  python restore_memory.py --backup database.txt.backup_1234 --current database.txt --output database.txt --full-restore --dry-run
"""

import argparse
import os
import pickle
import shutil
import sys
from datetime import datetime


# ── ANSI colours ─────────────────────────────────────────────────────────────
def _supports_colour() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

GREEN  = "\033[92m" if _supports_colour() else ""
YELLOW = "\033[93m" if _supports_colour() else ""
RED    = "\033[91m" if _supports_colour() else ""
CYAN   = "\033[96m" if _supports_colour() else ""
RESET  = "\033[0m"  if _supports_colour() else ""
BOLD   = "\033[1m"  if _supports_colour() else ""

def log(msg, colour=""):  print(f"  {colour}{msg}{RESET}")
def section(t):           print(f"\n{BOLD}{CYAN}[{t}]{RESET}")
def ok(msg):              log(f"✓ {msg}", GREEN)
def warn(msg):            log(f"⚠ {msg}", YELLOW)
def err(msg):             log(f"✗ {msg}", RED)


# ── Raw-byte scanner ──────────────────────────────────────────────────────────

def _scan_chunks(raw: bytes) -> list:
    """Return [(byte_offset, chunk_text)] for every chunk string found."""
    result = []
    i = 0
    while i < len(raw) - 2:
        if raw[i] == 0x8C:                          # SHORT_BINUNICODE
            slen = raw[i + 1]
            end = i + 2 + slen
            if end <= len(raw):
                try:
                    text = raw[i + 2:end].decode("utf-8")
                    if text.startswith("[") and "/20" in text and len(text) > 10:
                        result.append((i, text))
                except UnicodeDecodeError:
                    pass
            i += 1
        elif raw[i] == 0x8D:                        # BINUNICODE8
            if i + 9 >= len(raw):
                i += 1
                continue
            slen = int.from_bytes(raw[i + 1:i + 9], "little")
            end = i + 9 + slen
            if 0 < slen < 100_000 and end <= len(raw):
                try:
                    text = raw[i + 9:end].decode("utf-8")
                    if text.startswith("[") and "/20" in text and len(text) > 10:
                        result.append((i, text))
                except UnicodeDecodeError:
                    pass
            i += 1
        else:
            i += 1
    return result


def _scan_timestamps(raw: bytes) -> list:
    """Return [(byte_offset, unix_ms)] for every timestamp-like integer found."""
    result = []
    MIN_TS, MAX_TS = 1_600_000_000_000, 1_900_000_000_000
    i = 0
    while i < len(raw) - 2:
        if raw[i] == 0x8A:                          # LONG1
            nbytes = raw[i + 1]
            if 4 <= nbytes <= 7 and i + 2 + nbytes <= len(raw):
                val = int.from_bytes(raw[i + 2:i + 2 + nbytes], "little")
                if MIN_TS <= val <= MAX_TS:
                    result.append((i, val))
            i += 1
        else:
            i += 1
    return result


def _pair_chunks_timestamps(chunks, timestamps):
    """Pair each chunk with the nearest timestamp that follows it in the file."""
    paired = []
    ts_idx = 0
    for c_off, c_text in chunks:
        while ts_idx < len(timestamps) - 1 and timestamps[ts_idx][0] < c_off:
            ts_idx += 1
        ts = timestamps[ts_idx][1] if ts_idx < len(timestamps) else None
        paired.append((c_text, ts))
    return paired


# ── Pickle load ───────────────────────────────────────────────────────────────

def _load_db(path: str):
    """Load a vectordb pickle file. Returns inner dict or None on failure."""
    try:
        with open(path, "rb") as f:
            data = pickle.loads(f.read())
        if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
            db = data[0]
            if "memory" in db and "metadata" in db:
                return db
    except Exception:
        pass
    return None


# ── Embedding helpers ─────────────────────────────────────────────────────────

def _try_load_embedder(dim: int):
    """Load sentence-transformers model matching the embedding dimension, or None."""
    try:
        from sentence_transformers import SentenceTransformer
        model_name = "all-MiniLM-L6-v2" if dim == 384 else "all-mpnet-base-v2"
        return SentenceTransformer(model_name)
    except Exception:
        return None


def _embed(model, texts: list) -> list:
    vecs = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    return [v.tolist() for v in vecs]


def _zero_vec(dim: int) -> list:
    return [0.0] * dim


# ── Shared helpers ────────────────────────────────────────────────────────────

def _recover_new_chunks(current_path: str, backup_texts: set, emb_dim: int):
    """
    Scan a current DB file (healthy or corrupted) for chunks that are
    newer than the backup (i.e. not present in backup_texts).
    Returns (new_chunks_paired, embeddings_or_zeros).
    """
    current_db = _load_db(current_path)
    if current_db is not None:
        ok(f"Current DB loaded normally — {len(current_db['memory']):,} chunks")
        paired = [
            (e["chunk"], current_db["metadata"][e["metadata_index"]])
            for e in current_db["memory"]
            if e["chunk"] not in backup_texts
        ]
    else:
        warn("Current DB is corrupted / truncated — scanning raw bytes …")
        with open(current_path, "rb") as f:
            raw = f.read()
        chunks_pos = _scan_chunks(raw)
        ts_pos     = _scan_timestamps(raw)
        paired_all = _pair_chunks_timestamps(chunks_pos, ts_pos)
        ok(f"Recovered {len(chunks_pos):,} chunk texts via raw scan")
        paired = [(t, ts) for t, ts in paired_all if t not in backup_texts]

    if paired:
        warn(f"{len(paired):,} chunks are newer than the backup — will be preserved")
    return paired


def _embed_new_chunks(new_chunks_paired: list, emb_dim: int):
    """Re-embed new chunks, or return zero vectors if ST is unavailable."""
    if not new_chunks_paired:
        ok("No new post-backup chunks — nothing to embed.")
        return []

    embedder = _try_load_embedder(emb_dim)
    if embedder:
        ok(f"sentence-transformers loaded — embedding {len(new_chunks_paired):,} chunks …")
        embeddings = _embed(embedder, [t for t, _ in new_chunks_paired])
        ok("Done.")
    else:
        warn("sentence-transformers not available in this environment.")
        warn("New chunks will be stored with ZERO embeddings (not searchable).")
        warn("Fix: run this script inside your project's venv where")
        warn("     sentence-transformers is installed, then run again.")
        embeddings = [_zero_vec(emb_dim) for _ in new_chunks_paired]
    return embeddings


def _write_output(output_path, current_path, backup_path,
                  merged_memory, merged_metadata, dry_run,
                  new_chunks_paired, embeddings, emb_dim,
                  missing=None):
    """Handle dry-run preview or write the final file."""
    if dry_run:
        warn("DRY RUN — no files will be written.\n")
        if missing:
            print(f"  {BOLD}Backup chunks to restore (missing in current):{RESET}")
            for entry, ts in missing[:15]:
                dt = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
                print(f"    [{dt}]  {entry['chunk'][:72]}")
            if len(missing) > 15:
                print(f"    … and {len(missing) - 15} more")
            print()
        if new_chunks_paired:
            print(f"  {BOLD}New post-backup chunks to preserve:{RESET}")
            for text, ts in new_chunks_paired[:15]:
                dt = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d") if ts else "?"
                print(f"    [{dt}]  {text[:72]}")
            if len(new_chunks_paired) > 15:
                print(f"    … and {len(new_chunks_paired) - 15} more")
            print()
        print("  Re-run without --dry-run to apply changes.")
        return

    if os.path.abspath(output_path) == os.path.abspath(backup_path):
        err("Output path cannot be the same as the backup. Aborting.")
        sys.exit(1)

    if os.path.abspath(output_path) == os.path.abspath(current_path):
        stamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
        auto_bak = current_path + f".pre_restore_{stamp}.bak"
        shutil.copy2(current_path, auto_bak)
        ok(f"Auto-backup → {auto_bak}")

    with open(output_path, "wb") as f:
        pickle.dump([{"memory": merged_memory, "metadata": merged_metadata}], f, protocol=4)

    size_mb = os.path.getsize(output_path) / 1024 / 1024
    ok(f"Output: {output_path}  ({size_mb:.1f} MB)")
    ok(f"Total chunks written: {len(merged_memory):,}")

    if new_chunks_paired and embeddings and embeddings[0] == _zero_vec(emb_dim):
        print()
        warn("REMINDER: new chunks have zero embeddings — re-run inside your project")
        warn("          venv (with sentence-transformers) to make them searchable.")


# ── Default restore ───────────────────────────────────────────────────────────

def restore(backup_path: str, current_path: str, output_path: str, dry_run: bool = False):
    """
    Default mode: start from current DB, add missing backup chunks + new chunks.
    """
    print()
    print(f"{BOLD}{'═' * 64}{RESET}")
    print(f"{BOLD}  Memory Database Restore Tool  [default mode]{RESET}")
    print(f"{BOLD}{'═' * 64}{RESET}")

    section("1/5  Loading backup")
    backup_db = _load_db(backup_path)
    if backup_db is None:
        err(f"Cannot load backup: {backup_path}"); sys.exit(1)
    backup_memory   = backup_db["memory"]
    backup_metadata = backup_db["metadata"]
    backup_texts    = {e["chunk"] for e in backup_memory}
    emb_dim         = len(backup_memory[0]["embedding"]) if backup_memory else 384
    ts_min = datetime.fromtimestamp(min(backup_metadata) / 1000).strftime("%Y-%m-%d")
    ts_max = datetime.fromtimestamp(max(backup_metadata) / 1000).strftime("%Y-%m-%d")
    ok(f"{len(backup_memory):,} chunks  |  embedding dim = {emb_dim}  |  {ts_min} → {ts_max}")

    section("2/5  Loading current database")
    current_db = _load_db(current_path)
    new_chunks_paired = []

    if current_db is not None:
        current_memory   = current_db["memory"]
        current_metadata = current_db["metadata"]
        current_texts    = {e["chunk"] for e in current_memory}
        ok(f"Loaded normally — {len(current_memory):,} chunks")
    else:
        warn("File is corrupted / truncated — scanning raw bytes …")
        with open(current_path, "rb") as f:
            raw = f.read()
        chunks_pos = _scan_chunks(raw)
        ts_pos     = _scan_timestamps(raw)
        paired_all = _pair_chunks_timestamps(chunks_pos, ts_pos)
        current_texts    = {t for t, _ in paired_all}
        new_chunks_paired = [(t, ts) for t, ts in paired_all if t not in backup_texts]
        current_memory   = []
        current_metadata = []
        current_db       = {"memory": [], "metadata": []}
        ok(f"Recovered {len(chunks_pos):,} chunk texts via raw scan")
        if new_chunks_paired:
            warn(f"{len(new_chunks_paired):,} chunks are newer than the backup — will be preserved")

    section("3/5  Comparing")
    missing = [
        (entry, meta)
        for entry, meta in zip(backup_memory, backup_metadata)
        if entry["chunk"] not in current_texts
    ]
    log(f"Backup chunks:               {len(backup_memory):,}")
    log(f"Already in current:          {len(current_texts & backup_texts):,}")
    log(f"Missing — to restore:        {len(missing):,}", YELLOW if missing else GREEN)
    if new_chunks_paired:
        log(f"New post-backup chunks:      {len(new_chunks_paired):,}")

    if not missing and not new_chunks_paired:
        ok("Current DB is already complete — nothing to do.")
        return

    section("4/5  Re-embedding new chunks")
    embeddings = _embed_new_chunks(new_chunks_paired, emb_dim)

    section("5/5  Writing output")
    merged_memory   = list(current_memory)
    merged_metadata = list(current_metadata)
    next_idx = len(merged_metadata)

    for entry, meta in missing:
        e = dict(entry)
        e["metadata_index"] = next_idx
        e["text_index"]     = next_idx
        merged_memory.append(e)
        merged_metadata.append(meta)
        next_idx += 1

    fallback_ts = int(datetime.now().timestamp() * 1000)
    for (text, ts), emb in zip(new_chunks_paired, embeddings):
        merged_memory.append({
            "chunk": text, "embedding": emb,
            "metadata_index": next_idx, "text_index": next_idx,
        })
        merged_metadata.append(ts if ts is not None else fallback_ts)
        next_idx += 1

    _write_output(output_path, current_path, backup_path,
                  merged_memory, merged_metadata, dry_run,
                  new_chunks_paired, embeddings, emb_dim, missing)

    if not dry_run:
        n_missing = len(missing)
        n_new     = len(new_chunks_paired)
        print()
        print(f"{BOLD}{GREEN}{'═' * 64}")
        print(f"  Restore complete!  {n_missing:,} backup + {n_new:,} new chunks merged.")
        print(f"{'═' * 64}{RESET}")


# ── Full restore ──────────────────────────────────────────────────────────────

def full_restore(backup_path: str, current_path: str, output_path: str, dry_run: bool = False):
    """
    Full restore mode: use backup as the base (keeps all original embeddings),
    then append new post-backup chunks on top.
    Produces the maximum possible chunk count.
    """
    print()
    print(f"{BOLD}{'═' * 64}{RESET}")
    print(f"{BOLD}  Memory Database Restore Tool  [full-restore mode]{RESET}")
    print(f"{BOLD}{'═' * 64}{RESET}")

    section("1/4  Loading backup (will be used as base)")
    backup_db = _load_db(backup_path)
    if backup_db is None:
        err(f"Cannot load backup: {backup_path}"); sys.exit(1)
    backup_memory   = backup_db["memory"]
    backup_metadata = backup_db["metadata"]
    backup_texts    = {e["chunk"] for e in backup_memory}
    emb_dim         = len(backup_memory[0]["embedding"]) if backup_memory else 384
    ts_min = datetime.fromtimestamp(min(backup_metadata) / 1000).strftime("%Y-%m-%d")
    ts_max = datetime.fromtimestamp(max(backup_metadata) / 1000).strftime("%Y-%m-%d")
    ok(f"{len(backup_memory):,} chunks  |  embedding dim = {emb_dim}  |  {ts_min} → {ts_max}")

    section("2/4  Scanning current database for new chunks")
    new_chunks_paired = _recover_new_chunks(current_path, backup_texts, emb_dim)
    if not new_chunks_paired:
        ok("No new post-backup chunks found.")

    section("3/4  Re-embedding new chunks")
    embeddings = _embed_new_chunks(new_chunks_paired, emb_dim)

    section("4/4  Writing output")

    # Rebuild indices cleanly from backup
    merged_memory   = []
    merged_metadata = list(backup_metadata)   # backup metadata is already correct
    for idx, entry in enumerate(backup_memory):
        e = dict(entry)
        e["metadata_index"] = idx
        e["text_index"]     = idx
        merged_memory.append(e)

    next_idx    = len(merged_memory)
    fallback_ts = int(datetime.now().timestamp() * 1000)
    for (text, ts), emb in zip(new_chunks_paired, embeddings):
        merged_memory.append({
            "chunk": text, "embedding": emb,
            "metadata_index": next_idx, "text_index": next_idx,
        })
        merged_metadata.append(ts if ts is not None else fallback_ts)
        next_idx += 1

    _write_output(output_path, current_path, backup_path,
                  merged_memory, merged_metadata, dry_run,
                  new_chunks_paired, embeddings, emb_dim)

    if not dry_run:
        print()
        print(f"{BOLD}{GREEN}{'═' * 64}")
        print(f"  Full restore complete!")
        print(f"  {len(backup_memory):,} backup chunks + {len(new_chunks_paired):,} new chunks")
        print(f"  = {len(merged_memory):,} total chunks")
        print(f"{'═' * 64}{RESET}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Restore deleted vectordb memory chunks from a backup.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--backup",  required=True, metavar="FILE",
                   help="Backup database file (e.g. database.txt.backup_1234)")
    p.add_argument("--current", required=True, metavar="FILE",
                   help="Current database file, healthy or corrupted (e.g. database.txt)")
    p.add_argument("--output",  required=True, metavar="FILE",
                   help="Output path. Same as --current is safe (auto .bak is made).")
    p.add_argument("--full-restore", action="store_true",
                   help="Use backup as base + append new chunks. "
                        "Restores maximum chunks (recommended when current is corrupted).")
    p.add_argument("--dry-run", action="store_true",
                   help="Preview changes without writing any files.")
    args = p.parse_args()

    for label, path in [("--backup", args.backup), ("--current", args.current)]:
        if not os.path.isfile(path):
            err(f"{label} file not found: {path}"); sys.exit(1)

    if args.full_restore:
        full_restore(args.backup, args.current, args.output, args.dry_run)
    else:
        restore(args.backup, args.current, args.output, args.dry_run)


if __name__ == "__main__":
    main()
