"""Backups: a backups folder that can't be written doesn't stop saving (Vault says so, once); two
databases with the same name keep their own backups. Temporary settings and test databases."""
import os, shutil, sys, time
import helpers  # repo path; temporary folder, settings and test databases
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
from store import Database, Op, apply_op, save_database

# ---- the store
blocked = s / "not-a-folder"; blocked.write_text("x")  # a backups folder that can't be made
path = s / "backups_store.kdbx"; shutil.copy(s / "dnd41.kdbx", path)
db = Database(path, PW, "")
apply_op(db.kp, Op("favourite", db.entries[0]["uuid"], fields={"on": True}))
try:
    db.digest = save_database(db.kp, path, db.digest, backup=True, backup_directory=blocked / "backups")
    saved = True
except OSError as exc:
    saved = exc
ok("backups folder can't be written: saved anyway", saved is True, saved)
ok("…the change is in the file", Database(path, PW, "").entries[0]["favourite"])
ok("…and why there's no backup is kept", isinstance(store.backup_error, OSError), store.backup_error)
save_database(db.kp, path, db.digest)
ok("next save without a backup due: no error left", store.backup_error is None)

# Two databases called Passwords.kdbx in different folders keep their own 10 backups
folder = s / "same_name_backups"
shutil.rmtree(folder, ignore_errors=True)
one, two = s / "drive" / "Passwords.kdbx", s / "usb" / "Passwords.kdbx"
for f in (one, two):
    f.parent.mkdir(exist_ok=True)
    f.write_bytes(b"x")
for i in range(12):
    store.make_backup(one, b"one %d" % i, folder, keep=10)
    store.make_backup(two, b"two %d" % i, folder, keep=10)  # (same second: names overwrite, so ≤ 10)
names = sorted(p.name for p in folder.iterdir())
mine = [n for n in names if n.split()[1] == names[0].split()[1]]
ok("same name, different folders: each keeps its own", 0 < len(mine) < len(names) and len(names) <= 20, names)
ok("…their contents not mixed up", all((folder / n).read_bytes().startswith(b"one") for n in mine)
   or all((folder / n).read_bytes().startswith(b"two") for n in mine))

# ---- the window: saving goes on, and Vault says (once) that there's no backup
vault.settings = QSettings(str(s / "backups.ini"), QSettings.IniFormat)
vault.settings.clear()
store.backup_dir = lambda: blocked / "backups"
path = s / "backups_window.kdbx"; shutil.copy(s / "dnd41.kdbx", path)
w = vault.MainWindow(); w.resize(1200, 700); w.show(); QTest.qWaitForWindowExposed(w)
db = Database(path, PW, ""); w.vault.load(db); w.saver.attach(db); w.locked = False
w._closing = True
warnings = lambda: [b for b in w.findChildren(vault.InfoBar) if b.title == "Saved, but without a backup"]
e = w.saver.db.entries[1]
w.saver.submit(Op("favourite", e["uuid"], fields={"on": True}, title=e["title"]))
ok("an edit: saved", wait(lambda: not w.saver.pending, 15) and not w.saver.failed)
ok("…in the file", next(x for x in Database(path, PW, "").entries if x["uuid"] == e["uuid"])["favourite"])
ok("…and Vault says there's no backup", wait(lambda: len(warnings()) == 1, 3), len(warnings()))
w.saver.last_backup = 0  # (a backup due again)
w.saver.submit(Op("favourite", e["uuid"], fields={"on": False}, title=e["title"]))
wait(lambda: not w.saver.pending, 15); QTest.qWait(200)
ok("…only once", len(warnings()) == 1, len(warnings()))

print(f"--- {'ALL PASSED' if not fails else str(len(fails)) + ' FAILED'}", flush=True)
sys.stdout.flush(); os._exit(1 if fails else 0)
