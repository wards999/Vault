"""Entries shown in the toolbar are kept in the database (an item in the entry's CustomData), so every
device shows the same ones: saved and read back, undone, not copied by Duplicate, kept by KeePassXC (if
installed). Pins from Vault 1.5's settings move into the file once; a read-only database keeps them in
Settings. Temporary settings, test databases."""
import os, shutil, subprocess, sys, time
import helpers  # repo path; temporary folder, settings and test databases
from lxml import etree
from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
s = helpers.WORK
PW = "test-pw-123"
fails = []
def ok(label, cond, extra=""):
    print(("OK   " if cond else "FAIL ") + label + ("" if cond else f"  [{extra}]"), flush=True)
    if not cond: fails.append(label)
def wait(cond, timeout=10):
    end = time.time() + timeout
    while not cond() and time.time() < end: QTest.qWait(50)
    return cond()

app = QApplication(sys.argv)
import vault, store
from store import Database, Op, apply_op, inverse_op, duplicate_op, save_database, TOOLBAR_KEY

# ---- the store
path = s / "toolbar_store.kdbx"; shutil.copy(s / "dnd41.kdbx", path)
db = Database(path, PW, "")
entry = lambda title, d=None: next(e for e in (d or db).entries if e["title"] == title)
gh = entry("GitHub")
ok("not in the toolbar to start with", gh["toolbar"] == "")
on = Op("toolbar", gh["uuid"], fields={"on": "2026-11-08T10:00:00.000+00:00"}, title="GitHub")
undo = inverse_op(db.kp, on)
ok("applied", apply_op(db.kp, on) is None); db.build_snapshot()
ok("…read back", entry("GitHub")["toolbar"] == "2026-11-08T10:00:00.000+00:00")
el = store._find_entry(db.kp, gh["uuid"])._element
tags = [c.tag for c in el]
ok("…one CustomData item, before the History", tags.count("CustomData") == 1
   and ("History" not in tags or tags.index("CustomData") < tags.index("History")), tags)
apply_op(db.kp, on); db.build_snapshot()
ok("applied twice: still one item", len(el.find("CustomData").findall("Item")) == 1)
ok("…the title, username and tags untouched", entry("GitHub")["username"] == gh["username"]
   and entry("GitHub")["tags"] == gh["tags"])
dup = duplicate_op(db.kp, gh["uuid"]); apply_op(db.kp, dup); db.build_snapshot()
ok("Duplicate: the copy isn't in the toolbar", next(e for e in db.entries if e["uuid"] == dup.uuid)["toolbar"] == "")
db.digest = save_database(db.kp, path, db.digest)
again = Database(path, PW, "")
ok("saved: still in the toolbar after reopening", entry("GitHub", again)["toolbar"] == "2026-11-08T10:00:00.000+00:00")
apply_op(db.kp, undo); db.build_snapshot()
ok("undone: out of the toolbar", entry("GitHub")["toolbar"] == "")
ok("…and its CustomData gone (it had none)", el.find("CustomData") is None)

# ---- the window: pins go into the file
ini = s / "toolbar_db.ini"
vault.settings = QSettings(str(ini), QSettings.IniFormat)
vault.settings.clear()
vault.settings.setValue("minimise_on_copy", False)
path = s / "toolbar_db.kdbx"; shutil.copy(s / "dnd41.kdbx", path)
db = Database(path, PW, "")
titles = ["Wikipedia", "GitHub", "Netflix"]  # put in the toolbar in this order (Vault 1.5, in Settings)
uuids = [entry(t)["uuid"] for t in titles]
w = vault.MainWindow(); w.resize(1200, 700); w.show(); QTest.qWaitForWindowExposed(w)
v = w.vault
vault.settings.setValue(v._db_key("toolbar_entries", db), ",".join(uuids))
w.vault.load(db); w.saver.attach(db); w.locked = False
w._closing = True
v.move_local_pins()
chip_titles = lambda: [t for _u, t, _i, _b in v.chips.chips]
ok("Vault 1.5's pins: moved into the database, in order", wait(lambda: chip_titles() == titles), chip_titles())
ok("…and out of Settings", vault.settings.value(v._db_key("toolbar_entries", db)) is None)
ok("…saved", wait(lambda: not w.saver.pending, 15))
ok("…in the file", [entry(t, Database(path, PW, ""))["toolbar"] != "" for t in titles] == [True] * 3)
v.move_local_pins()  # (nothing left to move: no change)
QTest.qWait(200)
ok("moving again: nothing to do", not w.saver.pending and chip_titles() == titles)

v.set_in_toolbar(uuids[1], False)
ok("removed: gone from the chips", wait(lambda: chip_titles() == ["Wikipedia", "Netflix"]), chip_titles())
v.set_in_toolbar(uuids[1], True)
ok("put back: last", wait(lambda: chip_titles() == ["Wikipedia", "Netflix", "GitHub"]), chip_titles())
v.undo()
ok("Undo: out again", wait(lambda: chip_titles() == ["Wikipedia", "Netflix"]), chip_titles())
ok("saved", wait(lambda: not w.saver.pending, 15))
vault.settings.sync()
ok("Settings: no toolbar list", "toolbar_entries" not in ini.read_text(encoding="utf-8", errors="replace"))

# Another device's copy (here: the file reopened) shows the same chips
w.vault.load(Database(path, PW, ""), keep_state=True)
ok("reopened: the same chips", wait(lambda: chip_titles() == ["Wikipedia", "Netflix"]), chip_titles())

# A read-only database: kept in Settings
v.db.writable = False
v.set_in_toolbar(uuids[1], True)
ok("read-only: pinned in Settings", chip_titles() == ["GitHub"] and v._saved_uuids("toolbar_entries") == [uuids[1]],
   chip_titles())
v.db.writable = True

# KeePassXC keeps it (when it's installed): edit the entry there, then read it back
cli = next((c for c in (shutil.which("keepassxc-cli"), r"C:\Program Files\KeePassXC\keepassxc-cli.exe",
                        "/Applications/KeePassXC.app/Contents/MacOS/keepassxc-cli") if c and os.path.exists(c)), None)
if cli:
    wiki = entry("Wikipedia", Database(path, PW, ""))
    r = subprocess.run([cli, "edit", "-u", "edited-in-kxc", str(path), "/".join(wiki["path"] + ["Wikipedia"])],
                       input=f"{PW}\n",
                       capture_output=True, text=True, timeout=30)
    after = entry("Wikipedia", Database(path, PW, ""))
    ok("KeePassXC edit: still in the toolbar", after["username"] == "edited-in-kxc" and after["toolbar"] != "",
       (r.stdout + r.stderr)[-200:])
else:
    print("(KeePassXC not installed: its check skipped)", flush=True)

print(f"--- {'ALL PASSED' if not fails else str(len(fails)) + ' FAILED'}", flush=True)
sys.stdout.flush(); os._exit(1 if fails else 0)
