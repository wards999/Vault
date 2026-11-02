"""Clicking a folder while search results show clears the search (Settings → Clear search when a folder
is clicked, on by default), also when it's the folder still highlighted; off, the results stay.
Real mouse clicks on the folder tree, temporary settings, test database, no processes."""
import os, shutil, sys
import helpers  # repo path; temporary folder, settings and test databases
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
s = helpers.WORK
fails = []
def ok(label, cond, extra=""):
    print(("OK   " if cond else "FAIL ") + label + ("" if cond else f"  [{extra}]"), flush=True)
    if not cond: fails.append(label)

app = QApplication(sys.argv)
import vault, store
vault.settings = QSettings(str(s / "search_folder.ini"), QSettings.IniFormat)
vault.settings.clear()
path = s / "search_folder.kdbx"; shutil.copy(s / "dnd41.kdbx", path)
db = store.Database(path, "test-pw-123", "")
w = vault.MainWindow(); w.resize(1100, 650); w.show(); QTest.qWaitForWindowExposed(w)
w.vault.load(db); w.saver.attach(db); w.locked = False
w._closing = True
v = w.vault

def click_folder(name):
    f = next(f for f in v.db.folders if f["name"] == name)
    item = v.tree._item_for(f["id"])
    v.tree.scrollToItem(item); QTest.qWait(50)
    QTest.mouseClick(v.tree.viewport(), Qt.LeftButton, Qt.NoModifier, v.tree.visualItemRect(item).center())
    QTest.qWait(100)

def search(text):
    v.search.setText(text); QTest.qWait(300)  # past the typing pause

click_folder("Work")
search("e")
ok("search shows results", v.list_title.text() == "Search results", v.list_title.text())
click_folder("Cards")
ok("default: clicking another folder clears the search", v.search.text() == "" and v.list_title.text() == "Cards",
   (v.search.text(), v.list_title.text()))
search("e")
click_folder("Cards")
ok("default: clicking the highlighted folder clears it too", v.search.text() == "" and v.list_title.text() == "Cards",
   (v.search.text(), v.list_title.text()))

vault.settings.setValue("clear_search_on_folder", False)
search("e")
click_folder("Work")
ok("off: the search and its results stay", v.search.text() == "e" and v.list_title.text() == "Search results",
   (v.search.text(), v.list_title.text()))
click_folder("Work")
ok("off: clicking the highlighted folder keeps them too", v.search.text() == "e", v.search.text())
v.search.clear(); QTest.qWait(300)
ok("off: clearing the search then shows the folder clicked", v.list_title.text() == "Work", v.list_title.text())

print(f"--- {'ALL PASSED' if not fails else str(len(fails)) + ' FAILED'}", flush=True)
sys.stdout.flush(); os._exit(1 if fails else 0)
