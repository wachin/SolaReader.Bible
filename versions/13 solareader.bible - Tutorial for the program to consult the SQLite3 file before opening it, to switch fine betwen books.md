

The problem is that the program is saving book indexes specific to each module, but when you switch modules, those indexes may become invalid. The best solution is for the program to directly query the SQLite module configuration to obtain the correct book structure.

Here's the corrected code that implements this solution:

```python
#!/usr/bin/env python3
# SolaReader.py - e-Sword style Bible reader with PyQt6
# Supports multiple SQLite translations, search, bookmarks and more

import sys
import json
import re
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QSpinBox, QTextBrowser, QLabel, QPushButton,
    QFileDialog, QTabWidget, QToolBar, QStatusBar, QMenuBar,
    QMenu, QMessageBox, QLineEdit, QInputDialog
)
from PyQt6.QtCore import Qt, QUrl, QTranslator, QLocale
from PyQt6.QtGui import QAction, QFont, QDesktopServices

# ─── CONFIGURATION ─────────────────────────────────────────────────────────────
CONFIG_DIR = Path.home() / ".config" / "solareader"
CONFIG_FILE = CONFIG_DIR / "config.json"
BOOKMARKS_FILE = CONFIG_DIR / "bookmarks.json"
TRANSLATIONS_DIR = Path(__file__).parent / "translations"

# Default book names (fallback)
DEFAULT_BOOK_NAMES = [
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

# Available languages for UI
AVAILABLE_LANGUAGES = {
    "en": "English",
    "es": "Español", 
    "fr": "Français",
    "de": "Deutsch",
    "pt": "Português",
    "it": "Italiano",
    "ru": "Русский",
    "zh": "中文",
    "ja": "日本語",
    "ko": "한국어"
}

# ─── MAIN CLASS ────────────────────────────────────────────────────────────────
class SolaReaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SolaReader - Bible Reader")
        self.resize(1000, 700)
        
        # Translation system
        self.translator = QTranslator()
        self.current_language = "en"
        
        # Default path - try multiple locations
        self.default_db_paths = [
            Path("/data/KJV+.SQLite3"),  # Absolute path
            Path(__file__).parent / "data" / "KJV+.SQLite3",  # Relative path
        ]
        self.current_translation = str(self.default_db_paths[0])
        
        # Dynamic book data (loaded from module)
        self.book_names = []
        self.book_numbers = []
        self.book_number_to_index = {}
        self.verse_book_numbers = []  # Store actual book numbers from verses table
        self.books_to_verses_map = {}  # Mapping from books table book numbers to verses table book numbers
        self.module_description = "Bible Reader"
        self.current_book_idx = 0
        self.current_chapter = 1
        self.current_verse = 1
        self.db_path = None
        self.conn = None
        self.initialized = False  # Flag to track if initialization is complete
        
        # Navigation history
        self.navigation_history = []
        self.current_history_index = -1

        self.load_config()
        self.load_translation()
        self.init_ui()
        self.open_database()
        if self.conn:
            self.load_books()
            self.update_book_combo()
        
        # Only update display after everything is initialized
        self.initialized = True
        self.update_display()
        
        # Add initial position to history
        self.add_to_history()

    def load_translation(self):
        """Load translation file for current language"""
        if self.current_language == "en":
            return  # English is the default
            
        translation_file = TRANSLATIONS_DIR / f"solareader_{self.current_language}.qm"
        if translation_file.exists():
            if self.translator.load(str(translation_file)):
                QApplication.instance().installTranslator(self.translator)
                print(f"Loaded translation: {self.current_language}")
            else:
                print(f"Failed to load translation: {self.current_language}")
        else:
            print(f"Translation file not found: {translation_file}")

    def init_ui(self):
        # Menu
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu(self.tr("File"))
        tools_menu = menu_bar.addMenu(self.tr("Tools"))
        bookmarks_menu = menu_bar.addMenu(self.tr("Bookmarks"))
        language_menu = menu_bar.addMenu(self.tr("Language"))

        # File Actions
        open_action = QAction(self.tr("Open Translation"), self)
        open_action.triggered.connect(self.open_translation)
        file_menu.addAction(open_action)
        
        exit_action = QAction(self.tr("Exit"), self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Tools Actions
        search_action = QAction(self.tr("Search Bible"), self)
        search_action.triggered.connect(self.on_search)
        tools_menu.addAction(search_action)

        # Bookmark Actions
        add_bookmark_action = QAction(self.tr("Add Bookmark"), self)
        add_bookmark_action.triggered.connect(self.on_add_bookmark)
        bookmarks_menu.addAction(add_bookmark_action)
        
        clear_bookmarks_action = QAction(self.tr("Clear All Bookmarks"), self)
        clear_bookmarks_action.triggered.connect(self.clear_all_bookmarks)
        bookmarks_menu.addAction(clear_bookmarks_action)

        # Language Actions
        for lang_code, lang_name in AVAILABLE_LANGUAGES.items():
            lang_action = QAction(lang_name, self)
            lang_action.triggered.connect(lambda checked, code=lang_code: self.change_language(code))
            language_menu.addAction(lang_action)

        # Toolbar (navigation)
        self.toolbar = QToolBar(self.tr("Navigation"))
        self.addToolBar(self.toolbar)

        # Back button with Unicode emoji
        self.back_button = QPushButton("⬅️")
        self.back_button.setToolTip(self.tr("Go back"))
        self.back_button.setEnabled(False)
        self.back_button.clicked.connect(self.go_back)
        self.toolbar.addWidget(self.back_button)
        
        self.toolbar.addSeparator()

        self.book_combo = QComboBox()
        self.book_combo.addItems(DEFAULT_BOOK_NAMES)  # Use default initially
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

        self.toolbar.addWidget(QLabel(self.tr("Book:")))
        self.toolbar.addWidget(self.book_combo)
        self.toolbar.addWidget(QLabel(self.tr("Chapter:")))
        self.toolbar.addWidget(self.chapter_spin)
        self.toolbar.addWidget(QLabel(self.tr("Verse:")))
        self.toolbar.addWidget(self.verse_spin)

        # Tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Bible
        self.bible_view = QTextBrowser()
        self.bible_view.setOpenExternalLinks(False)
        self.bible_view.anchorClicked.connect(self.on_verse_click)
        self.tabs.addTab(self.bible_view, self.tr("Bible"))

        # Bookmarks
        self.bookmarks_view = QTextBrowser()
        self.bookmarks_view.anchorClicked.connect(self.on_verse_click)
        self.tabs.addTab(self.bookmarks_view, self.tr("Bookmarks"))
        self.load_bookmarks()

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def change_language(self, language_code):
        """Change application language"""
        if language_code == self.current_language:
            return
            
        self.current_language = language_code
        
        # Remove old translator
        QApplication.instance().removeTranslator(self.translator)
        
        # Load new translation
        self.load_translation()
        
        # Recreate UI to apply new translations
        self.recreate_ui()
        
        # Save language preference
        self.save_config()
        
        # Show confirmation message
        QMessageBox.information(
            self, 
            self.tr("Language Changed"), 
            self.tr("Language has been changed to {0}. Some changes may require restart.").format(
                AVAILABLE_LANGUAGES.get(language_code, language_code)
            )
        )

    def recreate_ui(self):
        """Recreate UI elements to apply new translations"""
        # Clear existing UI
        self.menuBar().clear()
        self.removeToolBar(self.toolbar)
        
        # Recreate UI
        self.init_ui()
        self.update_display()

    def open_database(self):
        # Check if the current translation path exists
        path = Path(self.current_translation)
        if not path.exists():
            print(f"Current translation not found: {path}")
            
            # Try all default paths
            for default_path in self.default_db_paths:
                print(f"Trying default database: {default_path}")
                if default_path.exists():
                    self.current_translation = str(default_path)
                    path = default_path
                    print(f"Using default database: {path}")
                    break
            else:
                # If none of the defaults exist, open file dialog
                print("Default databases not found, opening file dialog")
                path, _ = QFileDialog.getOpenFileName(
                    self, self.tr("Select translation"), "", "SQLite Files (*.sqlite *.db *.sqlite3)"
                )
                if not path:
                    self.status_bar.showMessage(self.tr("❌ No database selected"))
                    return
                self.current_translation = path
                path = Path(path)
                print(f"User selected database: {path}")
        
        try:
            if self.conn:
                self.conn.close()
            self.db_path = path
            print(f"Opening database: {self.db_path}")
            
            # Verify file exists and is accessible
            if not self.db_path.exists():
                raise FileNotFoundError(f"File not found: {self.db_path}")
            
            self.conn = __import__("sqlite3").connect(str(self.db_path))
            
            # Register REGEXP function for exact word matching
            def regexp(expr, item):
                if item is None:
                    return False
                return re.search(expr, item, re.IGNORECASE) is not None
            
            self.conn.create_function("REGEXP", 2, regexp)
            
            self.status_bar.showMessage(f"✅ {self.db_path.name}")
            
            # Load module configuration after successful connection
            self.load_module_config()
        except Exception as e:
            self.status_bar.showMessage(self.tr("❌ Error: {0}").format(str(e)))
            print(f"Database error: {e}")
            self.conn = None

    def open_translation(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Open translation"), "", "SQLite Files (*.sqlite *.db *.sqlite3)"
        )
        if path:
            # Reset all book-related data
            self.book_names = []
            self.book_numbers = []
            self.book_number_to_index = {}
            self.verse_book_numbers = []
            self.books_to_verses_map = {}
            
            self.current_translation = path
            self.open_database()
            
            if self.conn:
                self.load_books()
                self.update_book_combo()
                
                # Load module-specific configuration
                self.load_module_config_from_file()
                
                # Validate and adjust current position
                self.validate_current_position()
                
                self.update_display()
            
            # Reset navigation history when opening new translation
            self.navigation_history = []
            self.current_history_index = -1
            self.add_to_history()
            
            # Save configuration for the new translation
            self.save_config()

    def update_display(self):
        # Only update if initialization is complete
        if not self.initialized:
            return
            
        self.load_bible_text()
        self.update_status()

    def load_books(self):
        """Load book list from the module's BOOKS table and verses table"""
        # Reset book data
        self.book_names = []
        self.book_numbers = []
        self.book_number_to_index = {}
        self.verse_book_numbers = []
        self.books_to_verses_map = {}
        
        if not self.conn:
            # Use default books if no connection
            self.book_names = DEFAULT_BOOK_NAMES.copy()
            self.book_numbers = list(range(1, len(DEFAULT_BOOK_NAMES) + 1))
            self.verse_book_numbers = self.book_numbers.copy()
            self.book_number_to_index = {num: i for i, num in enumerate(self.book_numbers)}
            print("Using default book list (no connection)")
            return

        try:
            cursor = self.conn.cursor()
            
            # First, get all book numbers from the verses table
            cursor.execute("SELECT DISTINCT book_number FROM verses ORDER BY book_number")
            self.verse_book_numbers = [row[0] for row in cursor.fetchall()]
            print(f"Found {len(self.verse_book_numbers)} book numbers in verses table: {self.verse_book_numbers}")
            
            # Try to get books from BOOKS table first
            try:
                cursor.execute("SELECT book_number, short_name, long_name FROM books ORDER BY book_number")
                books = cursor.fetchall()
                print("Loaded books from 'books' table")
            except Exception as e:
                print(f"Error querying 'books' table: {e}")
                # If BOOKS table doesn't exist, try books_all table
                try:
                    cursor.execute("SELECT book_number, short_name, long_name FROM books_all WHERE is_present = 1 ORDER BY book_number")
                    books = cursor.fetchall()
                    print("Loaded books from 'books_all' table")
                except Exception as e2:
                    print(f"Error querying 'books_all' table: {e2}")
                    # If neither table exists, create books from verses table
                    books = []
                    for i, book_num in enumerate(self.verse_book_numbers):
                        # Use default name if available
                        if i < len(DEFAULT_BOOK_NAMES):
                            book_name = DEFAULT_BOOK_NAMES[i]
                        else:
                            book_name = f"Book {book_num}"
                        books.append((book_num, book_name[:3], book_name))
                    print("Created books from verses table")

            if books:
                # Create book mapping
                self.book_numbers = [book[0] for book in books]
                self.book_names = [book[2] if book[2] else book[1] for book in books]  # Use long_name or short_name
                
                # Create mapping from book_number to index
                self.book_number_to_index = {}
                for i, book_num in enumerate(self.book_numbers):
                    self.book_number_to_index[book_num] = i
                
                # Create mapping from books table book numbers to verses table book numbers
                # This handles cases where the book numbers in the books table don't match the verses table
                self.books_to_verses_map = {}
                for i, book_num in enumerate(self.book_numbers):
                    if i < len(self.verse_book_numbers):
                        self.books_to_verses_map[book_num] = self.verse_book_numbers[i]
                    else:
                        # If we run out of verse book numbers, use the book number as is
                        self.books_to_verses_map[book_num] = book_num
                
                print(f"Loaded {len(self.book_names)} books from module")
                print("Book numbers and names:")
                for i, (num, name) in enumerate(zip(self.book_numbers, self.book_names)):
                    verse_num = self.books_to_verses_map.get(num, num)
                    print(f"  {i}: {num} -> {verse_num} - {name}")
            else:
                # Fallback to default if no books found
                self.book_names = DEFAULT_BOOK_NAMES.copy()
                self.book_numbers = list(range(1, len(DEFAULT_BOOK_NAMES) + 1))
                self.verse_book_numbers = self.book_numbers.copy()
                self.book_number_to_index = {num: i for i, num in enumerate(self.book_numbers)}
                self.books_to_verses_map = {num: num for num in self.book_numbers}
                print("Using default book list (no books found in module)")
            
        except Exception as e:
            print(f"Error loading books: {e}")
            # Fallback to default books
            self.book_names = DEFAULT_BOOK_NAMES.copy()
            self.book_numbers = list(range(1, len(DEFAULT_BOOK_NAMES) + 1))
            self.verse_book_numbers = self.book_numbers.copy()
            self.book_number_to_index = {num: i for i, num in enumerate(self.book_numbers)}
            self.books_to_verses_map = {num: num for num in self.book_numbers}
            print("Using default book list due to error")

    def load_module_config(self):
        """Load module-specific configuration from INFO table"""
        if not self.conn:
            return
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT name, value FROM info")
            config = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Apply configuration
            self.module_description = config.get("description", "Bible Module")
            module_language = config.get("language", "en")
            
            # Update window title
            self.setWindowTitle(f"SolaReader - {self.module_description}")
            
        except Exception as e:
            print(f"Error loading module config: {e}")
            # Table might not exist in older formats

    def load_module_config_from_file(self):
        """Load module-specific configuration from config file"""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                
                modules_config = config.get("modules", {})
                module_config = modules_config.get(self.current_translation, {})
                
                # Try to find the book by name in the loaded books
                saved_book_name = module_config.get("book_name", "")
                if saved_book_name and saved_book_name in self.book_names:
                    self.current_book_idx = self.book_names.index(saved_book_name)
                else:
                    # Fallback to first book if saved book not found
                    self.current_book_idx = 0
                
                self.current_chapter = module_config.get("chapter", 1)
                self.current_verse = module_config.get("verse", 1)
                
                # Apply window settings
                window_config = module_config.get("window", {})
                if window_config:
                    self.resize(window_config.get("width", 1000), window_config.get("height", 700))
                    self.move(window_config.get("x", 100), window_config.get("y", 100))
        except Exception as e:
            print(f"Error loading module config from file: {e}")

    def validate_current_position(self):
        """Validate that current position is valid for the loaded module"""
        # Validate book index
        if self.current_book_idx >= len(self.book_names):
            self.current_book_idx = 0
        
        # Validate chapter
        if self.current_book_idx < len(self.book_numbers):
            book_number = self.book_numbers[self.current_book_idx]
            verse_book_number = self.books_to_verses_map.get(book_number, book_number)
            
            try:
                cursor = self.conn.cursor()
                cursor.execute("SELECT MAX(chapter) FROM verses WHERE book_number = ?", (verse_book_number,))
                max_chapter = cursor.fetchone()[0] or 1
                
                if self.current_chapter > max_chapter:
                    self.current_chapter = 1
                
                # Validate verse
                cursor.execute("SELECT MAX(verse) FROM verses WHERE book_number = ? AND chapter = ?", 
                             (verse_book_number, self.current_chapter))
                max_verse = cursor.fetchone()[0] or 1
                
                if self.current_verse > max_verse:
                    self.current_verse = 1
            except:
                self.current_chapter = 1
                self.current_verse = 1

    def update_book_combo(self):
        """Update the book combo box with loaded books"""
        if hasattr(self, 'book_combo') and self.book_names:
            # Save current selection
            current_text = self.book_combo.currentText()
            
            # Clear and repopulate
            self.book_combo.clear()
            self.book_combo.addItems(self.book_names)
            
            # Restore selection if possible
            if current_text in self.book_names:
                self.book_combo.setCurrentText(current_text)
            else:
                # Reset to valid index
                if self.current_book_idx >= len(self.book_names):
                    self.current_book_idx = 0
                self.book_combo.setCurrentIndex(self.current_book_idx)

    def load_bible_text(self):
        if not self.conn or not self.book_numbers:
            self.bible_view.setHtml(f"<p>{self.tr('No database loaded.')}</p>")
            return

        # Get the actual book number from our loaded mapping
        if self.current_book_idx >= len(self.book_numbers):
            self.current_book_idx = 0
            
        book_number = self.book_numbers[self.current_book_idx]
        chapter = self.current_chapter
        
        # Get the corresponding verse book number
        verse_book_number = self.books_to_verses_map.get(book_number, book_number)
        
        print(f"Loading text for book {book_number} (verse book: {verse_book_number}), chapter {chapter}")

        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT verse, text FROM verses
                WHERE book_number = ? AND chapter = ?
                ORDER BY verse
            """, (verse_book_number, chapter))

            rows = cursor.fetchall()
            if not rows:
                self.bible_view.setHtml(f"<p>{self.tr('No verses found.')}</p>")
                return

            book_name = self.book_names[self.current_book_idx] if self.current_book_idx < len(self.book_names) else f"Book {book_number}"
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
            self.bible_view.setHtml(f"<p style='color:red;'>{self.tr('Error: {0}').format(str(e))}</p>")
            print(f"Error loading Bible text: {e}")

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
        self.add_to_history()
        # Save configuration when navigating
        self.save_config()

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

                if book_name in self.book_names:
                    self.current_book_idx = self.book_names.index(book_name)
                self.current_chapter = chapter
                self.current_verse = verse

                self.book_combo.setCurrentIndex(self.current_book_idx)
                self.chapter_spin.setValue(chapter)
                self.verse_spin.setValue(verse)
                self.update_display()
                self.add_to_history()
                # Save configuration when navigating
                self.save_config()
            except Exception as e:
                print(f"Error processing link: {e}")

    def on_search(self):
        term, ok = QInputDialog.getText(self, self.tr("Search"), self.tr("Search term:"))
        if ok and term.strip():
            self.search_in_bible(term.strip())

    def highlight_search_term(self, text, term):
        """Highlight exact word matches in text"""
        # Use regex to find whole word matches (case-insensitive)
        pattern = r'\b' + re.escape(term) + r'\b'
        highlighted_text = re.sub(
            pattern,
            r'<span style="background-color: yellow; font-weight: bold;">\g<0></span>',
            text,
            flags=re.IGNORECASE
        )
        return highlighted_text

    def search_in_bible(self, query):
        try:
            cursor = self.conn.cursor()
            
            # Use REGEXP to find exact word matches
            pattern = r'\b' + re.escape(query) + r'\b'
            cursor.execute("""
                SELECT book_number, chapter, verse, text FROM verses
                WHERE text REGEXP ?
            """, (pattern,))

            results = []
            for bnum, ch, vs, text in cursor.fetchall():
                try:
                    # Find book index using our mapping
                    # We need to map from verse book number back to books table book number
                    books_book_num = None
                    for books_num, verse_num in self.books_to_verses_map.items():
                        if verse_num == bnum:
                            books_book_num = books_num
                            break
                    
                    if books_book_num and books_book_num in self.book_number_to_index:
                        book_idx = self.book_number_to_index[books_book_num]
                        book_name = self.book_names[book_idx]
                        ref = f"{book_name} {ch}:{vs}"
                        
                        # Highlight the exact search term in the text
                        highlighted_text = self.highlight_search_term(text, query)
                        
                        results.append(f'<a href="sword://{self.db_path.name}/{ref}"><b>{ref}</b></a>: {highlighted_text}')
                except (ValueError, IndexError):
                    continue

            if results:
                html = f"<h4>{self.tr('Search Results for')} \"{query}\":</h4><hr>" + "<br><br>".join(results)
            else:
                html = f"<p>{self.tr('No results found for')} \"{query}\".</p>"
            self.bible_view.setHtml(html)
        except Exception as e:
            QMessageBox.critical(self, self.tr("Error"), self.tr("Search failed: {0}").format(str(e)))

    def add_to_history(self):
        """Add current position to navigation history"""
        current_pos = (self.current_book_idx, self.current_chapter, self.current_verse)
        
        # If we're not at the end of the history, remove future entries
        if self.current_history_index < len(self.navigation_history) - 1:
            self.navigation_history = self.navigation_history[:self.current_history_index + 1]
        
        # Add current position to history
        self.navigation_history.append(current_pos)
        self.current_history_index = len(self.navigation_history) - 1
        
        # Update back button state
        self.back_button.setEnabled(len(self.navigation_history) > 1)

    def go_back(self):
        """Navigate back in history"""
        if self.current_history_index > 0:
            self.current_history_index -= 1
            book_idx, chapter, verse = self.navigation_history[self.current_history_index]
            
            # Update UI
            self.current_book_idx = book_idx
            self.current_chapter = chapter
            self.current_verse = verse
            
            self.book_combo.setCurrentIndex(book_idx)
            self.chapter_spin.setValue(chapter)
            self.verse_spin.setValue(verse)
            
            self.update_display()
            
            # Update back button state
            self.back_button.setEnabled(self.current_history_index > 0)

    def on_add_bookmark(self):
        if self.current_book_idx < len(self.book_names):
            book_name = self.book_names[self.current_book_idx]
        else:
            book_name = f"Book {self.current_book_idx + 1}"
            
        ref = f"{book_name} {self.current_chapter}:{self.current_verse}"
        label, ok = QInputDialog.getText(self, self.tr("Bookmark"), self.tr("Name:"), text=ref)
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
            QMessageBox.information(self, self.tr("Success"), self.tr("Bookmark '{0}' saved.").format(label))
        except Exception as e:
            QMessageBox.critical(self, self.tr("Error"), self.tr("Could not save: {0}").format(str(e)))

    def clear_all_bookmarks(self):
        """Clear all bookmarks after confirmation"""
        reply = QMessageBox.question(
            self, 
            self.tr("Clear Bookmarks"), 
            self.tr("Are you sure you want to delete all bookmarks?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if BOOKMARKS_FILE.exists():
                    BOOKMARKS_FILE.unlink()
                self.load_bookmarks()
                QMessageBox.information(self, self.tr("Success"), self.tr("All bookmarks cleared."))
            except Exception as e:
                QMessageBox.critical(self, self.tr("Error"), self.tr("Could not clear bookmarks: {0}").format(str(e))

    def load_bookmarks(self):
        try:
            if not BOOKMARKS_FILE.exists():
                self.bookmarks_view.setHtml(f"<p>{self.tr('No bookmarks.')}</p>")
                return
            with open(BOOKMARKS_FILE, "r", encoding="utf-8") as f:
                bookmarks = json.load(f)
            html = f"<h4>{self.tr('Bookmarks')}</h4><hr>"
            for b in bookmarks:
                html += f'<p><a href="sword://{self.db_path.name}/{b["ref"]}">{b["label"]}</a></p>'
            self.bookmarks_view.setHtml(html)
        except Exception as e:
            self.bookmarks_view.setHtml(f"<p>{self.tr('Error: {0}').format(str(e))}</p>")

    def update_status(self):
        if self.current_book_idx < len(self.book_names):
            book_name = self.book_names[self.current_book_idx]
        else:
            book_name = f"Book {self.current_book_idx + 1}"
            
        ref = f"{book_name} {self.current_chapter}:{self.current_verse}"
        self.status_bar.showMessage(ref)

    def closeEvent(self, event):
        self.save_config()
        if self.conn:
            self.conn.close()
        event.accept()

    def load_config(self):
        try:
            # Create config directory if it doesn't exist
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            
            # Default configuration
            config = {
                "language": "en",
                "current_translation": str(self.default_db_paths[0]),
                "modules": {}
            }
            
            # Load existing configuration if it exists
            if CONFIG_FILE.exists():
                try:
                    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                        existing_config = json.load(f)
                    
                    # Check if it's the old format and migrate if necessary
                    if "modules" not in existing_config:
                        # Migrate old format to new format
                        old_translation = existing_config.get("translation", str(self.default_db_paths[0]))
                        config["current_translation"] = old_translation
                        
                        # Create module config from old settings
                        module_config = {
                            "book_name": "Genesis",  # Default book name
                            "chapter": existing_config.get("chapter", 1),
                            "verse": existing_config.get("verse", 1),
                            "window": existing_config.get("window", {
                                "x": 100, "y": 100, "width": 1000, "height": 700
                            })
                        }
                        config["modules"][old_translation] = module_config
                        
                        # Save the migrated configuration
                        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                            json.dump(config, f, indent=2)
                    else:
                        # Already in new format, use as is
                        config = existing_config
                except Exception as e:
                    print(f"Error loading configuration: {e}")
            
            # Apply configuration
            self.current_language = config.get("language", "en")
            self.current_translation = config.get("current_translation", str(self.default_db_paths[0]))
            
            # Check if the current translation exists
            if not Path(self.current_translation).exists():
                # Try default paths
                for default_path in self.default_db_paths:
                    if default_path.exists():
                        self.current_translation = str(default_path)
                        break
            
        except Exception as e:
            print(f"Error loading configuration: {e}")
            # Use defaults
            self.current_language = "en"
            self.current_translation = str(self.default_db_paths[0])
            self.current_book_idx = 0
            self.current_chapter = 1
            self.current_verse = 1

    def save_config(self):
        try:
            # Create config directory if it doesn't exist
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            
            # Load existing configuration if it exists
            config = {}
            if CONFIG_FILE.exists():
                try:
                    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                        config = json.load(f)
                except:
                    config = {}
            
            # Update global settings
            config["language"] = self.current_language
            config["current_translation"] = self.current_translation
            
            # Ensure modules section exists
            if "modules" not in config:
                config["modules"] = {}
            
            # Get current book name
            if self.current_book_idx < len(self.book_names):
                current_book_name = self.book_names[self.current_book_idx]
            else:
                current_book_name = "Genesis"
            
            # Update module-specific settings
            module_config = {
                "book_name": current_book_name,
                "chapter": self.current_chapter,
                "verse": self.current_verse,
                "window": {
                    "x": self.x(), "y": self.y(),
                    "width": self.width(), "height": self.height()
                }
            }
            
            config["modules"][self.current_translation] = module_config
            
            # Save configuration
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
                
        except Exception as e:
            print(f"Error saving configuration: {e}")


# ─── EXECUTION ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SolaReaderApp()
    window.show()
    sys.exit(app.exec())
```

## Key Changes:

### 1. Saved by Book Name instead of Table of Contents

Instead of saving the book's table of contents (which varies between modules), we now save the book's name:

```python
# En save_config():
current_book_name = self.book_names[self.current_book_idx] if self.current_book_idx < len(self.book_names) else "Genesis"

module_config = {
    "book_name": current_book_name,
    "chapter": self.current_chapter,
    "verse": self.current_verse,
    "window": {
        "x": self.x(), "y": self.y(),
        "width": self.width(), "height": self.height()
    }
}
```

### 2. Load by Book Name

When loading the configuration, we search for the book by name instead of using an index:

```python
# En load_module_config_from_file():
saved_book_name = module_config.get("book_name", "")
if saved_book_name and saved_book_name in self.book_names:
    self.current_book_idx = self.book_names.index(saved_book_name)
else:
    # Fallback to first book if saved book not found
    self.current_book_idx = 0
```

### 3. Current Position Validation

A method has been added to validate that the current position (book, chapter, verse) is valid for the loaded module:

```python
def validate_current_position(self):
    """Validate that current position is valid for the loaded module"""
    # Validate book index
    if self.current_book_idx >= len(self.book_names):
        self.current_book_idx = 0
    
    # Validate chapter and verse
    if self.current_book_idx < len(self.book_numbers):
        book_number = self.book_numbers[self.current_book_idx]
        verse_book_number = self.books_to_verses_map.get(book_number, book_number)
        
        # Look up the maximum chapter and verse for the current book
        # and adjust if necessary
```

### 4. Complete Reset When Changing Modules

When a new module is opened, the book-related data is completely reset:

```python
def open_translation(self):
    # Reset all book-related data
    self.book_names = []
    self.book_numbers = []
    self.book_number_to_index = {}
    self.verse_book_numbers = []
    self.books_to_verses_map = {}
    
    # ... rest of the code ...
```

### 5. Automatic Configuration Migration

The system now automatically migrates the old (index-based) configuration to the new (name-based) format:

```python
# En load_config():
if "modules" not in existing_config:
    # Migrate old format to new format
    module_config = {
        "book_name": "Genesis",  # Default book name
        "chapter": existing_config.get("chapter", 1),
        "verse": existing_config.get("verse", 1),
        "window": existing_config.get("window", {...})
    }
```

## How It Works:

1. **When opening a module**: The program directly queries the `books` or `books_all` tables of the SQLite module to obtain the correct structure of the books.

2. **When saving configuration**: The book name is saved instead of the index, making the configuration independent of the module structure.

3. **When loading configuration**: The book is searched by name in the list of loaded books in the current module.

4. **Automatic validation**: If the saved book does not exist in the current module, the first book is used as a fallback.

5. **Limits query**: The program directly queries the module to find the maximum chapter and verse size for each book, ensuring that navigation is always valid.

With these changes, the program can now handle multiple Bible modules without conflicts, as each module is queried directly to obtain its structure, and the configuration is saved independently for each.
