"""Recently used entries under the empty search box (copying puts an entry first; Up/Down/Enter or a click
shows it; Clear forgets them) and entries shown in the toolbar as chips. Only entry ids are saved in
Settings. Temporary settings, test database, no processes."""
import os, shutil, sys, time
import helpers  # repo path; temporary folder, settings and test databases
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
s = helpers.WORK
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
ini = s / "recent_chips.ini"
vault.settings = QSettings(str(ini), QSettings.IniFormat)
vault.settings.clear()
vault.settings.setValue("minimise_on_copy", False)
path = s / "recent_chips.kdbx"; shutil.copy(s / "dnd41.kdbx", path)
db = store.Database(path, "test-pw-123", "")
w = vault.MainWindow(); w.resize(1200, 700); w.show(); QTest.qWaitForWindowExposed(w)
w.vault.load(db); w.saver.attach(db); w.locked = False
w._closing = True
w.activateWindow(); QTest.qWait(100)
v = w.vault

def select(title):
    row = next(i for i, e in enumerate(v.model.entries) if e["title"] == title)
    v.table.selectRow(row); QTest.qWait(50)

# ---- recently used
v.search.setFocus(); QTest.qWait(100)
ok("nothing used yet: no list under the search box", not v.recent.isVisible())
v.table.setFocus()
for title in ("Netflix", "Wikipedia", "GitHub"):
    select(title); v.copy_password()
select("Netflix"); v.copy_username()  # used again: first, and only once
ok("most recent first, no repeats", [e["title"] for e in v._entries_for(v._saved_uuids("recent_entries"))]
   == ["Netflix", "GitHub", "Wikipedia"], v._saved_uuids("recent_entries"))
vault.settings.sync()
text = ini.read_text(encoding="utf-8", errors="replace")
ok("Settings hold ids, not titles", "Netflix" not in text and "GitHub" not in text)

v.search.setFocus(); QTest.qWait(100)
ok("empty search box with the cursor: the list shows", wait(lambda: v.recent.isVisible(), 3))
ok("…under the search box", v.recent.geometry().top() >= v.search.mapTo(w, v.search.rect().bottomLeft()).y())
QTest.keyClick(v.search, Qt.Key_Down); QTest.keyClick(v.search, Qt.Key_Down)
ok("Down, Down: the second highlighted", v.recent.list.currentRow() == 1, v.recent.list.currentRow())
QTest.keyClick(v.search, Qt.Key_Return); QTest.qWait(200)
ok("Enter: shows that entry", (v.current_entry() or {}).get("title") == "GitHub" and not v.recent.isVisible(),
   (v.current_entry() or {}).get("title"))
ok("…with the list focused", w.focusWidget() is v.table, w.focusWidget())

v.search.setFocus(); QTest.qWait(100)
QTest.keyClicks(v.search, "wiki"); QTest.qWait(100)
ok("typing hides it", not v.recent.isVisible())
v.search.clear(); QTest.qWait(100)
ok("emptied again: back", v.recent.isVisible())
QTest.keyClick(v.search, Qt.Key_Escape); QTest.qWait(50)
ok("Esc hides it", not v.recent.isVisible())
v.table.setFocus(); v.search.setFocus(); QTest.qWait(100)
item = v.recent.list.item(2)
QTest.mouseClick(v.recent.list.viewport(), Qt.LeftButton, Qt.NoModifier, v.recent.list.visualItemRect(item).center())
QTest.qWait(200)
ok("click: shows it", (v.current_entry() or {}).get("title") == "Wikipedia", (v.current_entry() or {}).get("title"))
v.search.setFocus(); QTest.qWait(100)
v.recent.clear_btn.click(); QTest.qWait(100)
ok("Clear: forgotten and hidden", v._saved_uuids("recent_entries") == [] and not v.recent.isVisible())
v.table.setFocus(); v.search.setFocus(); QTest.qWait(100)
ok("…and stays hidden", not v.recent.isVisible())

# ---- entries in the toolbar (any entry: not tied to Favourites)
ok("no chips to start with", not v.chips.isVisible())
select("GitHub")
gh = v.current_entry()
ok("not a favourite", not gh["favourite"])
v.set_in_toolbar(gh["uuid"], True); QTest.qWait(100)
ok("its chip shows anyway", v.chips.isVisible() and [t for _u, t, _i, _b in v.chips.chips] == ["GitHub"])
v.tree.setCurrentItem(v.tree._item_for(next(f["id"] for f in v.db.folders if f["name"] == "Work"))); QTest.qWait(100)
v.chips.chips[0][3].click(); QTest.qWait(200)
ok("clicking it shows the entry (from another folder)", (v.current_entry() or {}).get("title") == "GitHub")
ok("…in its own folder, not All items", v.folder == gh["folder_id"] and v.folder is not None
   and v.tree.currentItem().data(0, Qt.UserRole) == gh["folder_id"], (v.folder, gh["folder"]))
v.toggle_favourite(gh)
wait(lambda: next(e for e in w.saver.db.entries if e["title"] == "GitHub")["favourite"]); QTest.qWait(300)
v.toggle_favourite(next(e for e in v.db.entries if e["title"] == "GitHub"))
wait(lambda: not next(e for e in w.saver.db.entries if e["title"] == "GitHub")["favourite"]); QTest.qWait(300)
ok("starring and unstarring leave it", v.chips.isVisible() and len(v.chips.chips) == 1)
v.chips.copy.emit(gh["uuid"], "username"); QTest.qWait(150)  # (its right-click menu)
ok("chip menu, Copy username: copied", QApplication.clipboard().text() == gh["username"])
v.chips.copy.emit(gh["uuid"], "password"); QTest.qWait(150)
ok("…Copy password: copied, and the entry shown", QApplication.clipboard().text() == gh["password"]
   and (v.current_entry() or {}).get("uuid") == gh["uuid"])
ok("…the menu offers what it has", v.chips.fields[gh["uuid"]] == [f for f in ("username", "password", "totp") if gh[f]])
v.chips.removed.emit(gh["uuid"]); QTest.qWait(100)
ok("Remove from toolbar: gone", not v.chips.isVisible())

# The pin on each card (before the star): shows or hides its chip
viewport = v.table.viewport()
def pin():
    row = next(i for i, x in enumerate(v.model.entries) if x["uuid"] == gh["uuid"])
    x = v.model.entries[row]
    return next(r for f, _i, _t, r in v.delegate.actions(x, v.delegate.row_rect(v.table.visualRect(
        v.model.index(row, 0)))) if f == "toolbar")
ok("the pin's tooltip: Show in toolbar", v._button_at(pin().center())[2] == "Show in toolbar")
QTest.mouseClick(viewport, Qt.LeftButton, Qt.NoModifier, pin().center()); QTest.qWait(150)
ok("pin clicked: its chip shows", v.chips.isVisible() and [u for u, *_r in v.chips.chips] == [gh["uuid"]])
ok("…the pin says so", v._button_at(pin().center())[2] == "Remove from toolbar" and gh["uuid"] in v.delegate.pinned)
QTest.qWait(QApplication.styleHints().mouseDoubleClickInterval() + 100)
QTest.mouseClick(viewport, Qt.LeftButton, Qt.NoModifier, pin().center()); QTest.qWait(150)
ok("clicked again: gone", not v.chips.isVisible() and not v.delegate.pinned)

# Many chips in a narrow window: the rest behind "+N"
for e in v.db.entries:
    if not e["in_bin"]:
        v.set_in_toolbar(e["uuid"], True)
QTest.qWait(100)
total = len(v.chips.chips)
v.chips.setMaximumWidth(230); QTest.qWait(100)  # (narrower than the window can go)
shown = sum(b.isVisible() for *_r, b in v.chips.chips)
v.chips.grab().save(str(s / "chips-narrow.png"))
ok("narrow: some chips, then +N for the rest", v.chips.more.isVisible() and shown + len(v.chips.hidden) == total
   and v.chips.more.text() == f"+{len(v.chips.hidden)}", (shown, total, v.chips.more.text()))
v.chips.setMaximumWidth(16777215); QTest.qWait(200)
ok("wide again: all of them", not v.chips.more.isVisible() and all(b.isVisible() for *_r, b in v.chips.chips))
v.chips.grab().save(str(s / "chips.png"))

print(f"--- {'ALL PASSED' if not fails else str(len(fails)) + ' FAILED'}", flush=True)
sys.stdout.flush(); os._exit(1 if fails else 0)
