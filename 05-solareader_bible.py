#!/usr/bin/env python3
# SolaReader.py - e-Sword style Bible reader with PyQt6
# Supports multiple SQLite translations, search, bookmarks and more

import sys
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QSpinBox, QTextBrowser, QLabel, QPushButton,
    QFileDialog, QTabWidget, QToolBar, QStatusBar, QMenuBar,
    QMenu, QMessageBox, QLineEdit, QInputDialog
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QAction, QFont, QDesktopServices

# ─── CONFIGURATION ─────────────────────────────────────────────────────────────
CONFIG_DIR = Path.home() / ".config" / "solareader"
CONFIG_FILE = CONFIG_DIR / "config.json"
BOOKMARKS_FILE = CONFIG_DIR / "bookmarks.json"

# Bible book names
BOOK_NAMES = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
    "Joshua", "Judges", "Ruth", "1 Samuel", "2 Samuel",
    "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra",
    "Nehemiah", "Esther", "Job", "Psalms", "Proverbs",
    "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah", "Lamentations",
    "Ezekiel", "Daniel", "Hosea", "Joel", "Amos",
    "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk",
    "Zephaniah", "Haggai", "Zechariah", "Malachi",
    "Matthew", "Mark", "Luke", "John", "Acts",
    "Romans", "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians",
    "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians",
    "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews",
    "James", "1 Peter", "2 Peter", "1 John", "2 John",
    "3 John", "Jude", "Revelation"
]

# Mapping from index to actual book_number (adjust according to your database)
BOOK_NUMBERS = [
    10, 11, 12, 13, 14, 15, 16, 17, 18, 19,
    20, 21, 22, 23, 24, 25, 26, 27, 28, 29,
    30, 31, 32, 33, 34, 35, 36, 37, 38, 39,
    40, 41, 42, 43, 44, 45, 46, 47, 48,
    49, 50, 51, 52, 53, 54, 55, 56, 57, 58,
    59, 60, 61, 62, 63, 64, 65, 66, 67, 68,
    69, 70, 71, 72, 73, 74, 75
]

# ─── MAIN CLASS ────────────────────────────────────────────────────────────────
class SolaReaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SolaReader - Bible Reader")
        self.resize(1000, 700)
        
        # Default path relative to script
        script_dir = Path(__file__).parent
        default_db = script_dir / "data" / "KJV+.SQLite3"
        self.current_translation = str(default_db)
        
        self.current_book_idx = 0
        self.current_chapter = 1
        self.current_verse = 1
        self.db_path = None
        self.conn = None

        self.load_config()
        self.init_ui()
        self.open_database()
        self.update_display()

    def init_ui(self):
        # Menu
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        tools_menu = menu_bar.addMenu("Tools")
        bookmarks_menu = menu_bar.addMenu("Bookmarks")

        # Actions
        open_action = QAction("Open Translation", self)
        open_action.triggered.connect(self.open_translation)
        file_menu.addAction(open_action)

        search_action = QAction("Search Bible", self)
        search_action.triggered.connect(self.on_search)
        tools_menu.addAction(search_action)

        add_bookmark_action = QAction("Add Bookmark", self)
        add_bookmark_action.triggered.connect(self.on_add_bookmark)
        bookmarks_menu.addAction(add_bookmark_action)

        # Toolbar (navigation)
        self.toolbar = QToolBar("Navigation")
        self.addToolBar(self.toolbar)

        self.book_combo = QComboBox()
        self.book_combo.addItems(BOOK_NAMES)
        self.book_combo.setCurrentIndex(self.current_book_idx)
        self.book_combo.currentIndexChanged.connect(self.on_navigate)

        self.chapter_spin = QSpinBox()
        self.chapter_spin.setRange(1, 150)
        self.chapter_spin.setValue(self.current_chapter)
        self.chapter_spin.valueChanged.connect(self.on_navigate)

        self.verse_spin = QSpinBox()
        self.verse_spin.setRange(1, 176)
        self.verse_spin.setValue(self.current_verse)
        self.verse_spin.valueChanged.connect(self.on_navigate)

        self.toolbar.addWidget(QLabel("Book:"))
        self.toolbar.addWidget(self.book_combo)
        self.toolbar.addWidget(QLabel("Chapter:"))
        self.toolbar.addWidget(self.chapter_spin)
        self.toolbar.addWidget(QLabel("Verse:"))
        self.toolbar.addWidget(self.verse_spin)

        # Tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Bible
        self.bible_view = QTextBrowser()
        self.bible_view.setOpenExternalLinks(False)
        self.bible_view.anchorClicked.connect(self.on_verse_click)
        self.tabs.addTab(self.bible_view, "Bible")

        # Bookmarks
        self.bookmarks_view = QTextBrowser()
        self.tabs.addTab(self.bookmarks_view, "Bookmarks")
        self.load_bookmarks()

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def open_database(self):
        path = Path(self.current_translation)
        if not path.exists():
            # If default path doesn't exist, look in data folder
            script_dir = Path(__file__).parent
            default_db = script_dir / "data" / "KJV+.SQLite3"
            
            if default_db.exists():
                self.current_translation = str(default_db)
                path = default_db
            else:
                # If not found in data either, open dialog
                path, _ = QFileDialog.getOpenFileName(
                    self, "Select translation", "", "SQLite Files (*.sqlite *.db *.sqlite3)"
                )
                if not path:
                    self.status_bar.showMessage("❌ No database selected")
                    return
                self.current_translation = path
                path = Path(path)
        
        try:
            if self.conn:
                self.conn.close()
            self.db_path = path
            # Verify file exists and is accessible
            if not self.db_path.exists():
                raise FileNotFoundError(f"File not found: {self.db_path}")
            
            self.conn = __import__("sqlite3").connect(str(self.db_path))
            self.status_bar.showMessage(f"✅ {self.db_path.name}")
        except Exception as e:
            self.status_bar.showMessage(f"❌ Error: {e}")
            self.conn = None

    def open_translation(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open translation", "", "SQLite Files (*.sqlite *.db *.sqlite3)"
        )
        if path:
            self.current_translation = path
            self.open_database()
            self.update_display()

    def update_display(self):
        self.load_bible_text()
        self.update_status()

    def load_bible_text(self):
        if not self.conn:
            return

        book_number = BOOK_NUMBERS[self.current_book_idx]
        chapter = self.current_chapter

        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT verse, text FROM verses
                WHERE book_number = ? AND chapter = ?
                ORDER BY verse
            """, (book_number, chapter))

            rows = cursor.fetchall()
            if not rows:
                self.bible_view.setHtml("<p>No verses found.</p>")
                return

            book_name = BOOK_NAMES[self.current_book_idx]
            html = f"""
            <div style="font-family: 'Times New Roman', serif; font-size:16px; line-height:1.8; padding:15px;">
                <h3>{book_name} {chapter}</h3>
                <hr>
            """

            for verse, text in rows:
                is_current = verse == self.current_verse
                bg = "background-color:#ffeb3b;" if is_current else ""
                url = f"sword://{self.db_path.name}/{book_name} {chapter}:{verse}"
                html += f"""
                <a href="{url}" style="text-decoration:none; color:black;">
                    <span style="font-weight:bold; margin-right:6px; {bg}">{verse}</span>
                </a>
                {text} <br>
                """

            html += "</div>"
            self.bible_view.setHtml(html)

            max_verse = max(v for v, _ in rows)
            self.verse_spin.setMaximum(max_verse)

        except Exception as e:
            self.bible_view.setHtml(f"<p style='color:red;'>Error: {e}</p>")

    def on_navigate(self):
        # Detect if book changed
        new_book_idx = self.book_combo.currentIndex()
        if new_book_idx != self.current_book_idx:
            self.current_chapter = 1
            self.current_verse = 1

        self.current_book_idx = new_book_idx
        self.current_chapter = self.chapter_spin.value()
        self.current_verse = self.verse_spin.value()

        self.update_display()

    def on_verse_click(self, url):
        url_str = url.toString()
        if url_str.startswith("sword://"):
            try:
                _, _, ref = url_str.split("/", 2)
                parts = ref.split(" ")
                book_name = parts[0]
                chapter_verse = parts[1].split(":")
                chapter = int(chapter_verse[0])
                verse = int(chapter_verse[1])

                self.current_book_idx = BOOK_NAMES.index(book_name)
                self.current_chapter = chapter
                self.current_verse = verse

                self.book_combo.setCurrentIndex(self.current_book_idx)
                self.chapter_spin.setValue(chapter)
                self.verse_spin.setValue(verse)
                self.update_display()
            except Exception as e:
                print(f"Error processing link: {e}")

    def on_search(self):
        term, ok = QInputDialog.getText(self, "Search", "Search term:")
        if ok and term.strip():
            self.search_in_bible(term.strip())

    def search_in_bible(self, query):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT book_number, chapter, verse, text FROM verses
                WHERE text LIKE ?
            """, (f"%{query}%",))

            results = []
            for bnum, ch, vs, text in cursor.fetchall():
                try:
                    book_idx = BOOK_NUMBERS.index(bnum)
                    book_name = BOOK_NAMES[book_idx]
                    ref = f"{book_name} {ch}:{vs}"
                    results.append(f'<a href="sword://{self.db_path.name}/{ref}"><b>{ref}</b></a>: {text}')
                except ValueError:
                    continue

            if results:
                html = "<h4>Search Results:</h4><hr>" + "<br><br>".join(results)
            else:
                html = "<p>No results found.</p>"
            self.bible_view.setHtml(html)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Search failed: {e}")

    def on_add_bookmark(self):
        ref = f"{BOOK_NAMES[self.current_book_idx]} {self.current_chapter}:{self.current_verse}"
        label, ok = QInputDialog.getText(self, "Bookmark", "Name:", text=ref)
        if ok and label:
            self.save_bookmark(label, ref)

    def save_bookmark(self, label, ref):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            if BOOKMARKS_FILE.exists():
                with open(BOOKMARKS_FILE, "r", encoding="utf-8") as f:
                    bookmarks = json.load(f)
            else:
                bookmarks = []
            bookmarks.append({"label": label, "ref": ref})
            with open(BOOKMARKS_FILE, "w", encoding="utf-8") as f:
                json.dump(bookmarks, f, indent=2, ensure_ascii=False)
            self.load_bookmarks()
            QMessageBox.information(self, "Success", f"Bookmark '{label}' saved.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save: {e}")

    def load_bookmarks(self):
        try:
            if not BOOKMARKS_FILE.exists():
                self.bookmarks_view.setHtml("<p>No bookmarks.</p>")
                return
            with open(BOOKMARKS_FILE, "r", encoding="utf-8") as f:
                bookmarks = json.load(f)
            html = "<h4>Bookmarks</h4><hr>"
            for b in bookmarks:
                html += f'<p><a href="sword://{self.db_path.name}/{b["ref"]}">{b["label"]}</a></p>'
            self.bookmarks_view.setHtml(html)
        except Exception as e:
            self.bookmarks_view.setHtml(f"<p>Error: {e}</p>")

    def update_status(self):
        ref = f"{BOOK_NAMES[self.current_book_idx]} {self.current_chapter}:{self.current_verse}"
        self.status_bar.showMessage(ref)

    def closeEvent(self, event):
        self.save_config()
        if self.conn:
            self.conn.close()
        event.accept()

    def load_config(self):
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                # If saved configuration exists, use it
                saved_translation = config.get("translation")
                if saved_translation and Path(saved_translation).exists():
                    self.current_translation = saved_translation
                else:
                    # If saved path doesn't exist, use default
                    script_dir = Path(__file__).parent
                    default_db = script_dir / "data" / "KJV+.SQLite3"
                    self.current_translation = str(default_db)
                
                self.current_book_idx = int(config.get("book", 0))
                self.current_chapter = int(config.get("chapter", 1))
                self.current_verse = int(config.get("verse", 1))
                win = config.get("window", {})
                self.resize(win.get("width", 1000), win.get("height", 700))
                self.move(win.get("x", 100), win.get("y", 100))
            else:
                # If no configuration, use defaults
                script_dir = Path(__file__).parent
                default_db = script_dir / "data" / "KJV+.SQLite3"
                self.current_translation = str(default_db)
                self.current_book_idx = 0
                self.current_chapter = 1
                self.current_verse = 1
        except Exception as e:
            print(f"Error loading configuration: {e}")
            # Default values in case of error
            script_dir = Path(__file__).parent
            default_db = script_dir / "data" / "KJV+.SQLite3"
            self.current_translation = str(default_db)
            self.current_book_idx = 0
            self.current_chapter = 1
            self.current_verse = 1

    def save_config(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config = {
            "translation": str(self.current_translation),
            "book": self.current_book_idx,
            "chapter": self.current_chapter,
            "verse": self.current_verse,
            "window": {
                "x": self.x(), "y": self.y(),
                "width": self.width(), "height": self.height()
            }
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)


# ─── EXECUTION ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SolaReaderApp()
    window.show()
    sys.exit(app.exec())