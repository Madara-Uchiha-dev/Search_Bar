import sys
import os
import subprocess
import webbrowser
import urllib.parse
import winreg
import json
import threading
import re
import time
from pathlib import Path
from datetime import datetime
import base64

from PyQt5.QtCore import Qt, QSize, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import (
    QIcon, QPainter, QLinearGradient, QColor, QPen, QBrush,
    QKeySequence, QPixmap, QFont
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLineEdit, QHBoxLayout, QVBoxLayout, QWidget,
    QSystemTrayIcon, QMenu, QAction, QShortcut, QMessageBox, QLabel,
    QDialog, QPushButton, QListWidget, QFileDialog, QDialogButtonBox,
    QSizePolicy, QSpacerItem, QProgressBar
)

# ---------- Browser Database ----------
BROWSER_DATABASE = {
    "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "firefox.exe": "Mozilla Firefox",
    "opera.exe": "Opera",
    "opera_gx.exe": "Opera GX",
    "brave.exe": "Brave",
    "vivaldi.exe": "Vivaldi",
    "safari.exe": "Safari (Windows legacy)",
    "iexplore.exe": "Internet Explorer",
    "chromium.exe": "Chromium",
    "maxthon.exe": "Maxthon",
    "torch.exe": "Torch Browser",
    "slimjet.exe": "SlimJet",
    "avant.exe": "Avant Browser",
    "epic.exe": "Epic Privacy Browser",
    "srwareiron.exe": "SRWare Iron",
    "comodo_dragon.exe": "Comodo Dragon",
    "kinza.exe": "Kinza Browser",
    "orbitum.exe": "Orbitum",
    "falkon.exe": "Falkon",
    "midori.exe": "Midori",
    "waterfox.exe": "Waterfox",
    "palemoon.exe": "Pale Moon",
    "seamonkey.exe": "SeaMonkey",
    "netsurf.exe": "NetSurf",
    "yandex.exe": "Yandex Browser",
    "qqbrowser.exe": "QQ Browser",
    "ucbrowser.exe": "UC Browser",
    "baidubrowser.exe": "Baidu Browser",
    "sogoubrowser.exe": "Sogou Browser",
    "colibri.exe": "Colibri",
    "otterbrowser.exe": "Otter Browser",
    "dillo.exe": "Dillo",
    "dooble.exe": "Dooble Browser",
    "kmeleon.exe": "K-Meleon",
    "lunascape.exe": "Lunascape",
    "avast_secure_browser.exe": "Avast Secure Browser",
    "avg_secure_browser.exe": "AVG Secure Browser",
    "torchlightbrowser.exe": "Torchlight Browser",
    "duckduckgo.exe": "DuckDuckGo"
}


# ---------- Browser Loader Thread ----------
class BrowserLoader(QObject):
    browsers_loaded = pyqtSignal(dict)
    progress_update = pyqtSignal(int)

    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    def load_browsers(self):
        browsers = self.parent.get_available_browsers()
        self.browsers_loaded.emit(browsers)


# ---------- Settings Dialog for Browser Selection ----------
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Browser Settings")
        self.setModal(True)
        self.setFixedSize(500, 450)  # Increased height to accommodate progress bar

        # Apply dark theme to match the search bar
        self.setStyleSheet("""
            QDialog {
                background-color: #333;
                color: white;
            }
            QLabel {
                color: white;
            }
            QListWidget {
                background-color: #444;
                color: white;
                border: 1px solid #555;
                border-radius: 5px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #555;
            }
            QListWidget::item:selected {
                background-color: #555;
            }
            QPushButton {
                background-color: #555;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #666;
            }
            QPushButton:pressed {
                background-color: #444;
            }
            QDialogButtonBox {
                button-layout: 0;
            }
            QDialogButtonBox QPushButton {
                min-width: 80px;
            }
            QProgressBar {
                border: 1px solid #555;
                border-radius: 5px;
                text-align: center;
                background-color: #444;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 5px;
            }
        """)

        layout = QVBoxLayout()

        # Title
        title = QLabel("Select Preferred Browser")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)

        # Instructions
        instructions = QLabel(
            "Choose your preferred browser for search results. The browser will be used to open search queries.")
        instructions.setWordWrap(True)
        instructions.setStyleSheet("margin: 5px 10px; color: #CCC;")
        layout.addWidget(instructions)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Browser list
        self.browser_list = QListWidget()
        self.browser_list.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.browser_list)

        # Loading indicator
        self.loading_label = QLabel("Detecting browsers...")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setStyleSheet("color: #AAA; font-style: italic;")
        self.browser_list.hide()  # Hide list initially
        layout.addWidget(self.loading_label)

        # Buttons
        button_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("Refresh Browsers")
        self.refresh_btn.clicked.connect(self.refresh_browsers)
        self.refresh_btn.setVisible(False)
        button_layout.addWidget(self.refresh_btn)

        self.add_custom_btn = QPushButton("Add Browser Folder")
        self.add_custom_btn.clicked.connect(self.add_custom_browser)
        button_layout.addWidget(self.add_custom_btn)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        button_layout.addWidget(self.button_box)

        layout.addLayout(button_layout)
        self.setLayout(layout)

        # Load browsers from cache first
        self.load_cached_browsers()

        # Then load browsers in a separate thread to update the cache
        self.browser_loader = BrowserLoader(self.parent)
        self.browser_loader.browsers_loaded.connect(self.update_browser_list)
        self.browser_loader.progress_update.connect(self.update_progress)

        self.load_thread = threading.Thread(target=self.load_browsers_threaded)
        self.load_thread.daemon = True
        self.load_thread.start()

    def load_cached_browsers(self):
        """Load browsers from cache for immediate display"""
        if hasattr(self.parent, 'available_browsers') and self.parent.available_browsers:
            self.update_browser_list(self.parent.available_browsers)
            self.loading_label.hide()
            self.browser_list.show()

    def load_browsers_threaded(self):
        """Load browsers in a separate thread to prevent UI freeze"""
        self.browser_loader.load_browsers()

    def update_progress(self, value):
        """Update progress bar value"""
        self.progress_bar.setValue(value)

    def update_browser_list(self, browsers):
        """Update the browser list (called from thread)"""
        # Hide loading indicator and show browser list
        self.loading_label.hide()
        self.progress_bar.setVisible(False)
        self.browser_list.show()
        self.refresh_btn.setVisible(True)

        self.browser_list.clear()

        # Add detected browsers
        for name, path in browsers.items():
            # Only add browsers that are accessible
            if self.is_browser_accessible(path):
                self.browser_list.addItem(f"{name} - {path}")
                self.browser_list.item(self.browser_list.count() - 1).setData(Qt.UserRole, path)

        # Add current custom browser if exists and is accessible
        if (hasattr(self.parent, 'settings') and
                'custom_browser' in self.parent.settings and
                self.is_browser_accessible(self.parent.settings['custom_browser'])):
            custom_path = self.parent.settings['custom_browser']
            custom_name = os.path.basename(os.path.dirname(custom_path)).title()
            self.browser_list.addItem(f"{custom_name} (Custom) - {custom_path}")
            self.browser_list.item(self.browser_list.count() - 1).setData(Qt.UserRole, custom_path)

        # Select the current browser if set and accessible
        current_browser = self.parent.settings.get('preferred_browser', '')
        if current_browser and self.is_browser_accessible(current_browser):
            for i in range(self.browser_list.count()):
                if self.browser_list.item(i).data(Qt.UserRole) == current_browser:
                    self.browser_list.setCurrentRow(i)
                    break

    def refresh_browsers(self):
        """Refresh the browser list"""
        self.browser_list.clear()
        self.browser_list.hide()
        self.loading_label.setText("Detecting browsers...")
        self.loading_label.show()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.refresh_btn.setVisible(False)

        # Reload browsers in a separate thread
        self.load_thread = threading.Thread(target=self.load_browsers_threaded)
        self.load_thread.daemon = True
        self.load_thread.start()

    def is_browser_accessible(self, path):
        """Check if a browser executable is accessible"""
        try:
            return os.path.exists(path) and os.access(path, os.X_OK)
        except:
            return False

    def add_custom_browser(self):
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select Browser Installation Folder",
            "C:\\"
        )

        if folder_path:
            # Look for browser executables in the selected folder
            browser_exe = self.find_browser_executable(folder_path)
            if browser_exe and self.is_browser_accessible(browser_exe):
                # Add to list
                browser_name = os.path.basename(os.path.dirname(browser_exe)).title()
                self.browser_list.addItem(f"{browser_name} (Custom) - {browser_exe}")
                self.browser_list.item(self.browser_list.count() - 1).setData(Qt.UserRole, browser_exe)
                self.browser_list.setCurrentRow(self.browser_list.count() - 1)
            else:
                QMessageBox.warning(self, "Browser Not Found",
                                    f"No browser executable found in:\n{folder_path}")

    def find_browser_executable(self, folder_path):
        """Find browser executable in the given folder"""
        # Check for Edge in the standard location first
        edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        if os.path.exists(edge_path):
            return edge_path

        # Check for other browsers
        for exe_name in BROWSER_DATABASE.keys():
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if file.lower() == exe_name:
                        return os.path.join(root, file)
        return None

    def get_selected_browser(self):
        if self.browser_list.currentItem():
            return self.browser_list.currentItem().data(Qt.UserRole)
        return None


# ---------- Small helper: clickable icon ----------
class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()


# ---------- Background with gradient + rounded border ----------
class GradientWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Horizontal gradient
        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0.0, QColor(36, 33, 33))  # #242121
        gradient.setColorAt(1.0, QColor(119, 116, 116))  # #777474

        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(213, 207, 207), 2))  # #D5CFCF, 2pt
        painter.drawRoundedRect(1, 1, self.width() - 2, self.height() - 2, 25, 25)


# ---------- Options Button with icon ----------
class OptionsButton(ClickableLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(30, 30)
        self.setStyleSheet("""
            QLabel {
                background: transparent;
                border-radius: 15px;
            }
            QLabel:hover {
                background: rgba(255, 255, 255, 0.3);
            }
        """)
        self.setAlignment(Qt.AlignCenter)

        # Create option icon programmatically
        self.create_option_icon()

    def create_option_icon(self):
        """Create option icon programmatically if file is missing"""
        # Try to load from file first
        icon_path = self.resource_path("option.png")
        if os.path.exists(icon_path):
            pm = QPixmap(icon_path).scaled(
                20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.setPixmap(pm)
        else:
            # Create a simple three-dot icon programmatically
            pixmap = QPixmap(20, 20)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(Qt.white, 2))

            # Draw three dots
            dot_radius = 2
            center_y = pixmap.height() // 2
            painter.drawEllipse(4, center_y, dot_radius, dot_radius)
            painter.drawEllipse(10, center_y, dot_radius, dot_radius)
            painter.drawEllipse(16, center_y, dot_radius, dot_radius)

            painter.end()
            self.setPixmap(pixmap)

    def resource_path(self, relative_path):
        """Get absolute path to resource, works for dev and for PyInstaller"""
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)


# ---------- Search field with left icon and options button ----------
class SearchBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Search input field
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search the web or enter a URL...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: white;
                font-size: 18px;
                padding-left: 38px;
                padding-right: 12px;
            }
        """)

        # Search icon
        self.icon_size = 22
        self.icon_label = ClickableLabel(self.search_input)
        self.icon_label.setFixedSize(QSize(self.icon_size + 2, self.icon_size + 2))

        # Create search icon
        self.create_search_icon()

        # Options button (with icon)
        self.options_btn = OptionsButton()

        layout.addWidget(self.search_input)
        layout.addWidget(self.options_btn)

        # Connect signals
        self.search_input.returnPressed.connect(self._on_return_pressed)
        self.icon_label.clicked.connect(self._on_icon_clicked)

    def create_search_icon(self):
        """Create search icon programmatically if file is missing"""
        # Try to load from file first
        icon_path = self.resource_path("search.png")
        if os.path.exists(icon_path):
            pm = QPixmap(icon_path).scaled(
                self.icon_size, self.icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.icon_label.setPixmap(pm)
        else:
            # Create a simple search icon programmatically
            pixmap = QPixmap(self.icon_size, self.icon_size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(Qt.white, 2))

            # Draw a magnifying glass
            center = self.icon_size // 2
            radius = center - 4
            painter.drawEllipse(4, 4, radius, radius)
            painter.drawLine(center, center, self.icon_size - 2, self.icon_size - 2)

            painter.end()
            self.icon_label.setPixmap(pixmap)

    def resource_path(self, relative_path):
        """Get absolute path to resource, works for dev and for PyInstaller"""
        try:
            # PyInstander creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

    def resizeEvent(self, event):
        """Keep icon vertically centered."""
        y = (self.search_input.height() - self.icon_label.height()) // 2
        self.icon_label.move(10, max(0, y))
        super().resizeEvent(event)

    def _on_return_pressed(self):
        win = self.window()
        if hasattr(win, "perform_search"):
            win.perform_search()

    def _on_icon_clicked(self):
        win = self.window()
        if hasattr(win, "perform_search"):
            win.perform_search()

    def text(self):
        return self.search_input.text().strip()

    def clear(self):
        self.search_input.clear()


# ---------- Main window ----------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.is_visible = False
        self.settings_file = os.path.join(os.path.expanduser("~"), ".desktop_search_settings.json")
        self.browser_cache_file = os.path.join(os.path.expanduser("~"), ".desktop_search_browser_cache.json")
        self.settings = self.load_settings()
        self.available_browsers = self.load_browser_cache()  # Load from cache

        self.initUI()
        self.setupTrayIcon()
        self.setupShortcuts()

        # Auto-detect browser on first run if not set
        if not self.settings.get('preferred_browser') and self.available_browsers:
            self.auto_select_browser()

        # Pre-load browsers in background thread to update cache
        self.preload_browsers()

    def auto_select_browser(self):
        """Automatically select a browser on first run"""
        # Priority order for browser selection
        browser_priority = [
            "Microsoft Edge",
            "Google Chrome",
            "Mozilla Firefox",
            "Opera",
            "Brave",
            "Vivaldi"
        ]

        # Try to find browsers in priority order
        for browser_name in browser_priority:
            for available_name, path in self.available_browsers.items():
                if browser_name.lower() in available_name.lower():
                    self.settings['preferred_browser'] = path
                    self.save_settings()
                    print(f"Auto-selected browser: {available_name}")
                    return

        # If no priority browser found, just use the first available
        if self.available_browsers:
            first_browser = next(iter(self.available_browsers.items()))
            self.settings['preferred_browser'] = first_browser[1]
            self.save_settings()
            print(f"Auto-selected browser: {first_browser[0]}")

    # Pre-load browsers to improve performance
    def preload_browsers(self):
        def load_browsers():
            browsers = self.get_available_browsers()
            self.available_browsers = browsers
            self.save_browser_cache(browsers)

        thread = threading.Thread(target=load_browsers)
        thread.daemon = True
        thread.start()

    # ----- Settings management -----
    def load_settings(self):
        default_settings = {
            'preferred_browser': '',  # Empty means use system default
            'custom_browser': ''  # Path to custom browser if added
        }

        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    return {**default_settings, **json.load(f)}
        except Exception as e:
            print(f"Error loading settings: {e}")

        return default_settings

    def save_settings(self):
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    # ----- Browser cache management -----
    def load_browser_cache(self):
        """Load browser cache from file"""
        try:
            if os.path.exists(self.browser_cache_file):
                with open(self.browser_cache_file, 'r') as f:
                    cache_data = json.load(f)

                    # Check if cache is recent (less than 7 days old)
                    cache_time = datetime.fromisoformat(cache_data.get('timestamp', '2000-01-01'))
                    if (datetime.now() - cache_time).days < 7:
                        return cache_data.get('browsers', {})
        except Exception as e:
            print(f"Error loading browser cache: {e}")

        return {}

    def save_browser_cache(self, browsers):
        """Save browser cache to file"""
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'browsers': browsers
            }
            with open(self.browser_cache_file, 'w') as f:
                json.dump(cache_data, f, indent=4)
        except Exception as e:
            print(f"Error saving browser cache: {e}")

    # ----- UI setup -----
    def initUI(self):
        self.setWindowTitle("Desktop Search")
        self.setFixedSize(500, 53)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnBottomHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Central layout
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)

        # Gradient container
        container = GradientWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(15, 0, 5, 0)  # Reduced right margin to accommodate options button

        # Search bar with options button
        self.search_bar = SearchBar()
        self.search_bar.options_btn.clicked.connect(self.show_options_menu)

        h.addWidget(self.search_bar)
        root.addWidget(container)

        self.centerWindow()

    def centerWindow(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = screen.height() - 100
        self.move(x, y)

    # ----- Options menu -----
    def show_options_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #333;
                color: white;
                border: 1px solid #555;
                border-radius: 5px;
            }
            QMenu::item {
                padding: 5px 20px 5px 10px;
            }
            QMenu::item:selected {
                background-color: #555;
            }
        """)

        # Get current browser name for display
        current_browser = "System Default"
        if self.settings.get('preferred_browser'):
            browser_path = self.settings['preferred_browser']
            current_browser = os.path.basename(os.path.dirname(browser_path)).title()

        # Browser settings action
        browser_action = QAction(f"Browser: {current_browser}", self)
        browser_action.triggered.connect(self.show_settings)
        menu.addAction(browser_action)

        # Separator
        menu.addSeparator()

        # Exit action
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.quit_app)
        menu.addAction(exit_action)

        # Show menu below options button
        pos = self.search_bar.options_btn.mapToGlobal(self.search_bar.options_btn.rect().bottomLeft())
        menu.exec_(pos)

    # ----- Tray icon -----
    def setupTrayIcon(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("System tray not available")
            return

        self.tray_icon = QSystemTrayIcon(self)

        icon_path = self.resource_path("search.png")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            # Create a simple tray icon programmatically
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(Qt.white, 2))

            # Draw a simple search icon
            painter.drawEllipse(2, 2, 8, 8)
            painter.drawLine(10, 10, 14, 14)

            painter.end()
            self.tray_icon.setIcon(QIcon(pixmap))

        show_action = QAction("Show Search", self)
        settings_action = QAction("Browser Settings", self)
        quit_action = QAction("Exit", self)

        show_action.triggered.connect(self.toggle_search)
        settings_action.triggered.connect(self.show_settings)
        quit_action.triggered.connect(self.quit_app)

        menu = QMenu()
        menu.addAction(show_action)
        menu.addAction(settings_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self.trayIconActivated)
        self.tray_icon.show()

    def resource_path(self, relative_path):
        """Get absolute path to resource, works for dev and for PyInstaller"""
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

    # ----- Shortcuts -----
    def setupShortcuts(self):
        # Changed from Ctrl+Space+H to Ctrl+Shift+H
        QShortcut(QKeySequence("Ctrl+Shift+H"), self, activated=self.toggle_search)
        QShortcut(QKeySequence("Escape"), self, activated=self.hide_search)

    # ----- Tray interactions -----
    def trayIconActivated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.toggle_search()

    # ----- Show/Hide -----
    def toggle_search(self):
        self.hide_search() if self.is_visible else self.show_search()

    def show_search(self):
        self.show()
        self.activateWindow()
        self.search_bar.search_input.setFocus()
        self.is_visible = True

    def hide_search(self):
        self.search_bar.clear()
        self.hide()
        self.is_visible = False

    def quit_app(self):
        if hasattr(self, "tray_icon"):
            self.tray_icon.hide()
        QApplication.quit()

    # ----- Browser detection -----
    def get_available_browsers(self):
        """Find all installed browsers on Windows"""
        browsers = {}

        # Check for Microsoft Edge first (common default browser)
        edge_paths = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        ]

        for edge_path in edge_paths:
            if os.path.exists(edge_path) and os.access(edge_path, os.X_OK):
                browsers["Microsoft Edge"] = edge_path
                break

        # Common browser registry paths
        registry_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Clients\StartMenuInternet"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Clients\StartMenuInternet"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        ]

        # Check registry for browsers
        for root_key, path in registry_paths:
            try:
                with winreg.OpenKey(root_key, path) as key:
                    i = 0
                    while True:
                        try:
                            browser_name = winreg.EnumKey(key, i)
                            browser_key_path = f"{path}\\{browser_name}\\shell\\open\\command"

                            try:
                                with winreg.OpenKey(root_key, browser_key_path) as browser_key:
                                    browser_cmd, _ = winreg.QueryValueEx(browser_key, "")
                                    # Extract the executable path from the command
                                    exe_path = browser_cmd.split('"')[1] if '"' in browser_cmd else browser_cmd.split()[
                                        0]
                                    if os.path.exists(exe_path) and os.access(exe_path, os.X_OK):
                                        browsers[browser_name] = exe_path
                            except:
                                pass

                            i += 1
                        except WindowsError:
                            break
            except:
                pass

        # Check common browser locations
        program_dirs = [
            os.environ.get("ProgramFiles", "C:\\Program Files"),
            os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
            os.path.expanduser("~\\AppData\\Local"),
            os.path.expanduser("~\\AppData\\Roaming"),
        ]

        for program_dir in program_dirs:
            if not os.path.exists(program_dir):
                continue

            for root, dirs, files in os.walk(program_dir):
                for file in files:
                    if file.lower() in BROWSER_DATABASE:
                        exe_path = os.path.join(root, file)
                        if os.path.exists(exe_path) and os.access(exe_path, os.X_OK):
                            browser_name = BROWSER_DATABASE[file.lower()]
                            # Don't override Edge if already found
                            if browser_name not in browsers or browser_name != "Microsoft Edge":
                                browsers[browser_name] = exe_path

        return browsers

    # ----- Settings dialog -----
    def show_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            selected_browser = dialog.get_selected_browser()
            if selected_browser:
                self.settings['preferred_browser'] = selected_browser
                self.save_settings()
                QMessageBox.information(self, "Settings Saved",
                                        f"Preferred browser set to:\n{selected_browser}")

    # ----- Search behavior (using logic from provided code) -----
    def perform_search(self):
        query = self.search_bar.text().strip()
        if not query:
            return

        if self.is_url(query):
            self.open_url(query)
        else:
            self.web_search(query)

        # Always clear after action
        self.search_bar.clear()

    def is_url(self, text: str) -> bool:
        """Heuristic URL/domain detection with minimal false positives."""
        t = text.strip().lower()

        # Has a scheme?
        if t.startswith(("http://", "https://", "ftp://", "file://")):
            return True

        # Spaces => not a URL
        if " " in t:
            return False

        # www. prefix like www.example.com
        if t.startswith("www.") and "." in t[4:]:
            return True

        # Bare domain with common TLDs
        domain_exts = (
            ".com", ".org", ".net", ".io", ".co", ".edu", ".gov",
            ".info", ".biz", ".in", ".uk", ".us", ".xyz", ".app", ".dev", ".shop"
        )
        if "." in t:
            # quick check for something like example.com or sub.example.in
            parts = t.split(".")
            if all(parts) and any(t.endswith(ext) for ext in domain_exts):
                return True

        return False

    def open_url(self, url: str):
        """Open URL; add http:// for bare domains."""
        if not url.startswith(("http://", "https://", "ftp://", "file://")):
            url = "http://" + url

        # Use preferred browser if set and accessible
        if (self.settings.get('preferred_browser') and
                os.path.exists(self.settings['preferred_browser']) and
                os.access(self.settings['preferred_browser'], os.X_OK)):
            try:
                subprocess.Popen([self.settings['preferred_browser'], url])
                return
            except Exception as e:
                print(f"Error opening URL with preferred browser: {e}")

        # Fallback to system default
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"Error opening URL: {e}")
            QMessageBox.warning(self, "Error", f"Could not open URL: {e}")

    def web_search(self, query: str):
        """Open DuckDuckGo search using preferred browser or system default"""
        search_url = f"https://duckduckgo.com/?q={urllib.parse.quote_plus(query)}"

        # Use preferred browser if set and accessible
        if (self.settings.get('preferred_browser') and
                os.path.exists(self.settings['preferred_browser']) and
                os.access(self.settings['preferred_browser'], os.X_OK)):
            try:
                subprocess.Popen([self.settings['preferred_browser'], search_url])
                return
            except Exception as e:
                print(f"Error opening search with preferred browser: {e}")

        # Fallback to system browser
        try:
            webbrowser.open(search_url)
        except Exception as e:
            print(f"Error opening search: {e}")
            QMessageBox.warning(self, "Error", f"Could not perform search: {e}")

    # ----- Drag to move -----
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_origin = event.globalPos()
            self._win_origin = self.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and hasattr(self, "_drag_origin"):
            delta = event.globalPos() - self._drag_origin
            self.move(self._win_origin + delta)


# ---------- Entry ----------
if __name__ == "__main__":
    # HiDPI friendly
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    win = MainWindow()
    # Start hidden; toggle with Ctrl+Shift+H
    win.hide_search()

    print("Desktop Search started. Press Ctrl+Shift+H to toggle.")
    sys.exit(app.exec_())