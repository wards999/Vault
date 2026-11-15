"""Locking while Vault is loading a change made on another device: it still locks once the load is done
(it used to wait for a save that never came, and stayed unlocked). An edit made during the load is saved
first. Temporary settings, test database, no processes."""
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
vault.settings = QSettings(str(s / "lock_reload.ini"), QSettings.IniFormat)
vault.settings.clear()
store.backup_dir = lambda: s / "lock_reload_backups"
path = s / "lock_reload.kdbx"; shutil.copy(s / "dnd41.kdbx", path)
w = vault.MainWindow(); w.resize(1200, 700); w.show(); QTest.qWaitForWindowExposed(w)
w._show_unlock = lambda: None  # (no unlock dialog: the test only checks that it locked)


def unlock():
    db = Database(path, PW, "")
    w.vault.load(db); w.saver.attach(db); w.locked = False
    return db


def change_elsewhere(title):
    other = Database(path, PW, "")
    e = next(x for x in other.entries if x["title"] == title)
    apply_op(other.kp, Op("favourite", e["uuid"], fields={"on": not e["favourite"]}))
    save_database(other.kp, path, other.digest)


# Locked while loading a change from elsewhere
unlock()
change_elsewhere("GitHub")
w.saver.check_external()  # (the check every few seconds)
ok("set-up: loading the change", w.saver.busy)
w.lock()
ok("locked once it's loaded", wait(lambda: w.locked, 8))
ok("…the database closed", w.saver.db is None and not w.vault.model.entries)

# The same, with an edit made while it loads: saved, then locked
unlock()
change_elsewhere("Netflix")
w.saver.check_external()
wiki = next(e for e in w.saver.db.entries if e["title"] == "Wikipedia")
w.saver.submit(Op("favourite", wiki["uuid"], fields={"on": True}, title="Wikipedia"))  # (waits for the load)
w.lock()
ok("edit during the load: locked", wait(lambda: w.locked, 10))
again = Database(path, PW, "")
ok("…after saving the edit and keeping the other change",
   next(e for e in again.entries if e["title"] == "Wikipedia")["favourite"]
   and next(e for e in again.entries if e["title"] == "Netflix")["favourite"])

print(f"--- {'ALL PASSED' if not fails else str(len(fails)) + ' FAILED'}", flush=True)
sys.stdout.flush(); os._exit(1 if fails else 0)
