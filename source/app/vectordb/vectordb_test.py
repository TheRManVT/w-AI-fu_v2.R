from vectordb import Memory
from websockets.sync.client import connect
 
import json
import sys
import os
import shutil
import time
import glob
 
 
# ── Backup settings ───────────────────────────────────────────
MAX_BACKUPS = 5      # How many rolling backups to keep
BACKUP_INTERVAL = 1  # Make a backup every N DUMP calls (1 = every DUMP)
# ─────────────────────────────────────────────────────────────
 
_dump_counter  = 0
_pending_store = False   # True while a STORE is being processed
 
 
def make_backup(path: str):
    """Save a timestamped copy of the database and trim old ones."""
    if not os.path.exists(path):
        return
    backup_dir  = os.path.dirname(path) or "."
    backup_name = os.path.basename(path) + f".backup_{int(time.time())}"
    backup_path = os.path.join(backup_dir, backup_name)
    shutil.copy2(path, backup_path)
    print(f"[backup] Saved → {backup_name}", file=sys.stderr)
 
    # Remove oldest backups beyond MAX_BACKUPS
    # Use backup_dir + glob pattern separately to avoid Windows path issues
    pattern = os.path.join(backup_dir, os.path.basename(path) + ".backup_*")
    backups = sorted(glob.glob(pattern))
    for old in backups[:-MAX_BACKUPS]:
        try:
            os.remove(old)
            print(f"[backup] Removed old backup: {os.path.basename(old)}", file=sys.stderr)
        except Exception:
            pass
 
 
def safe_load_memory(path: str, options: dict) -> Memory:
    """
    Load the memory database safely.
    If the file is corrupted, rename it as a .corrupted backup before
    falling back to a fresh database — so data is never silently lost.
    """
    try:
        return Memory(memory_file=path, chunking_strategy=options)
    except Exception as e:
        print(f"[warning] Failed to load database: {e}", file=sys.stderr)
 
        if os.path.exists(path):
            corrupted_path = path + f".corrupted_{int(time.time())}.bak"
            shutil.copy2(path, corrupted_path)
            print(f"[warning] Corrupted file preserved at: {corrupted_path}", file=sys.stderr)
            print(f"[warning] Starting fresh database. Run restore_memory.py to recover.", file=sys.stderr)
 
        memory = Memory()
        memory.memory_file = path
        memory.save("empty", memory_file=path)
        return Memory(memory_file=path, chunking_strategy=options)
 
 
def get_list_from_query(query_results: list[dict]) -> list[str]:
    result: list[dict] = []
    for item in query_results:
        item["distance"] = float(item["distance"])
        result.append(item)
    return result
 
 
def handle_msg(data: str, ws, memory: Memory, path: str):
    global _dump_counter, _pending_store
 
    split_data: list[str] = data.split(" ")
    prefix: str = split_data[0]
    payload: str = " ".join(split_data[1:])
    result = ""
 
    match prefix:
        case "STORE":
            _pending_store = True
            timestamp = int(split_data[1])
            content = " ".join(split_data[2:])
            memory.save(content, timestamp)
            _pending_store = False
 
        case "QUERY":
            payload_json = json.loads(payload)
            id    = payload_json["id"]
            text  = payload_json["text"].strip()
            items = payload_json["items"]
            query_result = []
            try:
                query_result = get_list_from_query(memory.search(text, top_n=items, unique=True))
            except Exception as e:
                print(e, file=sys.stderr)
                query_result = []
            result_json = json.dumps({"results": query_result})
            result = id + " " + result_json
            ws.send(result)
 
        case "CLEAR":
            memory.clear()
 
        case "DUMP":
            # Wait for any in-progress STORE to fully complete before saving
            wait_ms = 0
            while _pending_store and wait_ms < 2000:
                time.sleep(0.01)
                wait_ms += 10
 
            if _pending_store:
                print("[warning] DUMP timed out waiting for STORE — saving anyway.", file=sys.stderr)
 
            memory.dump()
            sys.stdout.flush()
            # Rolling backup every BACKUP_INTERVAL dumps
            _dump_counter += 1
            if BACKUP_INTERVAL == 0 or _dump_counter % BACKUP_INTERVAL == 0:
                make_backup(path)
 
        case "BACKUP":
            # Save to disk and create a backup without any console output
            wait_ms = 0
            while _pending_store and wait_ms < 2000:
                time.sleep(0.01)
                wait_ms += 10
 
            memory.dump()
            make_backup(path)
 
        case _:
            return
 
 
def main():
    path = os.getcwd() + "\\database.txt"
    options = {'mode': 'sliding_window', 'window_size': 80, 'overlap': 16}

    memory = safe_load_memory(path, options)

    while True:
        try:
            with connect("ws://localhost:9251") as ws:
                while True:
                    msg: str = ws.recv()
                    handle_msg(msg, ws, memory, path)
        except Exception as e:
            print(e, file=sys.stderr)
            continue


if __name__ == "__main__":
    main()