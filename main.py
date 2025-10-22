import os
import sys
import subprocess
import threading
import venv
import sqlite3
from functools import partial
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QListWidget, QTextEdit, QPushButton, QDialog,
    QStackedWidget, QSizePolicy, QMessageBox, QInputDialog, QMenu, QFileDialog
)

from PySide6.QtGui import QFont, QAction, QPixmap
from PySide6.QtCore import Qt, Signal


class Card(QFrame):
    clicked = Signal(str, str)

    def __init__(self, title, desc):
        super().__init__()
        self.title = title
        self.desc = desc
        self.setObjectName("card")
        self.setFixedSize(180, 110)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setFont(QFont("Courier New", 10, QFont.Bold))

        desc_label = QLabel(desc)
        desc_label.setWordWrap(True)
        desc_label.setFont(QFont("Courier New", 9))

        layout.addWidget(title_label)
        layout.addWidget(desc_label)

    def mousePressEvent(self, event):
        self.clicked.emit(self.title, self.desc)


class CardGroup(QFrame):
    def __init__(self, title, cards, on_card_clicked):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setFont(QFont("Courier New", 10, QFont.Bold))
        layout.addWidget(title_label)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(8)
        cards_layout.setContentsMargins(4, 0, 4, 0)
        cards_layout.setAlignment(Qt.AlignLeft)

        for c in cards:
            card = Card(*c)
            card.clicked.connect(on_card_clicked)
            cards_layout.addWidget(card)

        layout.addLayout(cards_layout)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed))

class CardPage(QWidget):
    def __init__(self, on_card_clicked, db_path="data.db"):
        super().__init__()
        self.db_path = db_path
        self.on_card_clicked = on_card_clicked

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.container = QWidget()
        scroll.setWidget(self.container)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll)

        self.content_layout = QVBoxLayout(self.container)
        self.content_layout.setSpacing(8)
        self.content_layout.setContentsMargins(20, 10, 20, 10)

        self.init_db()
        self.load_groups()

        self.setStyleSheet("""
            QLabel {
                color: #000000;
                font-size: 13px;
            }
            QInputDialog {
                background-color: white;
            }

            /* 🔘 Общий стиль всех кнопок */
            QPushButton {
                background-color: rgba(255, 255, 255, 0.4);
                color: #000000;
                border: 1px solid rgba(0, 0, 0, 0.15);
                border-radius: 8px;
                padding: 6px 10px;
                transition: all 0.25s ease;
            }

            /* 💨 Эффект при наведении */
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.08);
                border: 1px solid rgba(0, 0, 0, 0.25);
            }

            /* 🔲 Эффект при нажатии */
            QPushButton:pressed {
                background-color: rgba(0, 0, 0, 0.15);
                border: 1px solid rgba(0, 0, 0, 0.3);
            }

            /* Меню (QMenu) */
            QMenu {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 6px;
            }
            QMenu::item {
                color: #000000;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: rgba(0, 0, 0, 0.1);
            }

            /* Поля ввода в диалогах */
            QLineEdit {
                background-color: #ffffff;
                color: #000000;
                border: 1px solid #aaaaaa;
                border-radius: 6px;
                padding: 4px;
            }
            QInputDialog QLabel {
                color: #000000;
            }
        """)

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                title TEXT,
                description TEXT,
                FOREIGN KEY(group_id) REFERENCES groups(id)
            )
        """)
        conn.commit()
        conn.close()

    def load_groups(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM groups ORDER BY id")
        groups = cursor.fetchall()
        conn.close()

        for group_id, name in groups:
            group_widget = self.create_group_widget(group_id, name)
            self.content_layout.addWidget(group_widget)

        add_group_btn = QPushButton("+ Добавить группу")
        add_group_btn.setCursor(Qt.PointingHandCursor)
        add_group_btn.clicked.connect(self.add_group)
        self.content_layout.addWidget(add_group_btn)
        self.content_layout.addStretch()

    def create_group_widget(self, group_id, name):
        frame = QFrame()
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title_layout = QHBoxLayout()
        title_label = QLabel(name)
        title_label.setStyleSheet("font-weight: bold; font-size: 13px;")

        menu_button = QPushButton("⋮")
        menu_button.setFixedWidth(28)
        menu_button.setCursor(Qt.PointingHandCursor)
        menu_button.setStyleSheet("""
            QPushButton::menu-indicator {
                image: none;
                width: 0px;
            }
        """)

        menu = QMenu(menu_button)
        act_add_card = QAction("➕ Добавить карточку", menu)
        act_rename = QAction("✏️ Переименовать группу", menu)
        act_delete = QAction("🗑️ Удалить группу", menu)

        act_add_card.triggered.connect(partial(self.add_card, group_id))
        act_rename.triggered.connect(partial(self.rename_group, group_id, name))
        act_delete.triggered.connect(partial(self.delete_group, group_id))

        menu.addAction(act_add_card)
        menu.addAction(act_rename)
        menu.addAction(act_delete)

        menu_button.setMenu(menu)

        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(menu_button)
        layout.addLayout(title_layout)

        cards_layout = QHBoxLayout()
        cards_layout.setAlignment(Qt.AlignLeft)
        cards_layout.setSpacing(8)
        cards_layout.setContentsMargins(4, 0, 4, 0)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, description FROM cards WHERE group_id=? ORDER BY id", (group_id,))
        cards = cursor.fetchall()
        conn.close()

        for card_id, title, desc in cards:
            btn = QPushButton()
            btn.setFixedSize(180, 110)
            btn.setText(title)
            btn.setToolTip(desc or "")
            btn.clicked.connect(partial(self.on_card_clicked, title, desc or ""))

            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(partial(self.card_context_menu, card_id, btn))
            cards_layout.addWidget(btn)

        layout.addLayout(cards_layout)
        return frame

    def card_context_menu(self, card_id, button, pos):
        menu = QMenu(button)
        act_rename = QAction("✏️ Переименовать", menu)
        act_delete = QAction("🗑️ Удалить", menu)
        act_rename.triggered.connect(partial(self.rename_card, card_id))
        act_delete.triggered.connect(partial(self.delete_card, card_id))
        menu.exec(button.mapToGlobal(pos))

    def add_group(self):
        name, ok = QInputDialog.getText(self, "Новая группа", "Введите название группы:")
        if ok:
            name = (name or "").strip()
            if not name:
                return
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("INSERT INTO groups (name) VALUES (?)", (name,))
                conn.commit()
                conn.close()
            except sqlite3.IntegrityError:
                QMessageBox.warning(self, "Ошибка", "Группа с таким именем уже существует.")
            self.load_groups()

    def rename_group(self, group_id, old_name):
        name, ok = QInputDialog.getText(self, "Переименовать группу", "Новое имя:", text=old_name)
        if ok:
            name = (name or "").strip()
            if not name:
                return
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("UPDATE groups SET name=? WHERE id=?", (name, group_id))
                conn.commit()
                conn.close()
            except sqlite3.IntegrityError:
                QMessageBox.warning(self, "Ошибка", "Группа с таким именем уже существует.")
            self.load_groups()

    def delete_group(self, group_id):
        reply = QMessageBox.question(self, "Удалить", "Удалить эту группу и все её карточки?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cards WHERE group_id=?", (group_id,))
            cursor.execute("DELETE FROM groups WHERE id=?", (group_id,))
            conn.commit()
            conn.close()
            self.load_groups()

    def add_card(self, group_id):
        title, ok = QInputDialog.getText(self, "Новая карточка", "Название скрипта:")
        if not ok:
            return
        title = (title or "").strip()
        if not title:
            return
        desc, ok2 = QInputDialog.getText(self, "Описание", "Краткое описание:")
        if not ok2:
            desc = ""
        desc = (desc or "").strip()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO cards (group_id, title, description) VALUES (?, ?, ?)",
                       (group_id, title, desc))
        conn.commit()
        conn.close()
        self.load_groups()

    def rename_card(self, card_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT title FROM cards WHERE id=?", (card_id,))
        row = cursor.fetchone()
        conn.close()
        old = row[0] if row else ""
        name, ok = QInputDialog.getText(self, "Переименовать карточку", "Новое имя:", text=old)
        if ok:
            name = (name or "").strip()
            if not name:
                return
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE cards SET title=? WHERE id=?", (name, card_id))
            conn.commit()
            conn.close()
            self.load_groups()

    def delete_card(self, card_id):
        reply = QMessageBox.question(self, "Удалить", "Удалить эту карточку?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cards WHERE id=?", (card_id,))
            conn.commit()
            conn.close()
            self.load_groups()

class EditorPage(QWidget):
    back_clicked = Signal()

    def __init__(self, db_path="data.db"):
        super().__init__()
        self.db_path = db_path
        self.current_title = None
        self.process = None

        self.init_db()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)

        self.back_button = QPushButton("← Назад")
        self.run_button = QPushButton("▶ Run")
        self.stop_button = QPushButton("■ Stop")
        self.save_button = QPushButton("💾 Save")

        for btn in [self.back_button, self.run_button, self.stop_button, self.save_button]:
            btn.setFixedHeight(32)
            btn.setStyleSheet("color: green;")
            btn.setCursor(Qt.PointingHandCursor)
            buttons_layout.addWidget(btn)

        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        self.editor = QTextEdit()
        self.editor.setFont(QFont("Courier New", 14))
        self.editor.setPlaceholderText("Введите код Python...")
        self.editor.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #dcdcdc;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                selection-background-color: #264f78;
                selection-color: #ffffff;
            }
        """)
        layout.addWidget(self.editor, stretch=3)

        self.output = QTextEdit()
        self.output.setFont(QFont("Courier New", 10))
        self.output.setReadOnly(True)
        self.output.setStyleSheet("""
            QTextEdit {
                background-color: #252526;
                color: #cccccc;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.output, stretch=1)

        self.back_button.clicked.connect(self.back_clicked.emit)
        self.save_button.clicked.connect(self.save_to_db)
        self.run_button.clicked.connect(self.run_code)
        self.stop_button.clicked.connect(self.stop_code)

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                title TEXT PRIMARY KEY,
                content TEXT
            )
        """)
        conn.commit()
        conn.close()

    def save_to_db(self):
        if not self.current_title:
            QMessageBox.warning(self, "Ошибка", "Неизвестен заголовок документа!")
            return

        text = self.editor.toPlainText().strip()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO documents (title, content)
            VALUES (?, ?)
            ON CONFLICT(title) DO UPDATE SET content=excluded.content
        """, (self.current_title, text))
        conn.commit()
        conn.close()

        QMessageBox.information(self, "Сохранено", f"Документ '{self.current_title}' успешно сохранён!")

    def set_content(self, title, desc):
        self.current_title = title
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT content FROM documents WHERE title=?", (title,))
        row = cursor.fetchone()
        conn.close()

        if row:
            self.editor.setPlainText(row[0])
        else:
            self.editor.setPlainText(f"# {title}\n\n{desc}")

        self.output.clear()

    def ensure_venv(self):
        venv_dir = os.path.join("venvs", self.current_title)
        python_exe = os.path.join(venv_dir, "Scripts", "python.exe") if sys.platform.startswith("win") else os.path.join(venv_dir, "bin", "python")

        if not os.path.exists(python_exe):
            os.makedirs("venvs", exist_ok=True)
            self.output.append(f"Создаётся виртуальное окружение для '{self.current_title}'...\n")
            venv.EnvBuilder(with_pip=True).create(venv_dir)
            self.output.append("✅ Виртуальное окружение создано.\n")

        return python_exe

    def run_code(self):
        if not self.current_title:
            QMessageBox.warning(self, "Ошибка", "Неизвестен заголовок документа!")
            return

        script_path = f"{self.current_title}.py"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(self.editor.toPlainText())

        python_exe = self.ensure_venv()

        self.output.clear()
        self.output.append(f"▶ Запуск {script_path}...\n")

        def run_thread():
            self.process = subprocess.Popen(
                [python_exe, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            for line in self.process.stdout:
                self.append_output(line)
            for line in self.process.stderr:
                self.append_output(line, is_error=True)
            self.process.wait()
            self.append_output(f"\n=== Процесс завершён (код {self.process.returncode}) ===\n")
            self.process = None

        threading.Thread(target=run_thread, daemon=True).start()

    def stop_code(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.append_output("\n⛔ Процесс остановлен пользователем.\n")
            self.process = None
        else:
            self.append_output("\n⚠ Нет активного процесса.\n")

    def append_output(self, text, is_error=False):
        def append():
            color = "#ff5555" if is_error else "#cccccc"
            self.output.setTextColor(Qt.red if is_error else Qt.white)
            self.output.moveCursor(self.output.textCursor().End)
            self.output.insertPlainText(text)
            self.output.moveCursor(self.output.textCursor().End)
        self.output.parent().window().app.processEvents() if hasattr(self.output.parent().window(), 'app') else None
        self.output.ensureCursorVisible()
        self.output.append(text)



class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ancile")
        self.resize(1000, 600)

        self._bg_label = QLabel(self)
        self._bg_label.setScaledContents(True)
        self._bg_label.setVisible(False)
        self._bg_pixmap = None

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        from main import CardPage, EditorPage, SettingsWindow
        self.stack = QStackedWidget()
        self.card_page = CardPage(self.open_editor)
        self.editor_page = EditorPage()
        self.stack.addWidget(self.card_page)
        self.stack.addWidget(self.editor_page)

        self.editor_page.back_clicked.connect(self.go_back)
        main_layout.addWidget(self.stack, stretch=1)

        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(180)
        self.sidebar.setStyleSheet("background-color: #2d2f38;")

        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # меню
        self.menu = QListWidget()
        self.menu.addItems(["Главная", "Проекты", "Настройки"])
        self.menu.setStyleSheet("""
            QListWidget {
                background: transparent;
                color: white;
                border: none;
                font-size: 14px;
            }
            QListWidget::item:selected {
                background-color: #3f4452;
            }
        """)
        self.menu.currentRowChanged.connect(self.on_sidebar_changed)

        row_count = self.menu.count()
        if row_count > 0:
            row_h = self.menu.sizeHintForRow(0)
            frame = self.menu.frameWidth() * 2
            total_h = row_h * row_count + frame
            self.menu.setFixedHeight(total_h)

        sidebar_layout.addWidget(self.menu)

        sidebar_layout.addStretch(1)

        self.logo_label = QLabel()
        pix = QPixmap("logo.png")
        pix = pix.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.logo_label.setPixmap(pix)
        self.logo_label.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(self.logo_label, 0, Qt.AlignHCenter)

        sidebar_layout.addStretch(1)

        self.stack.setStyleSheet("background: transparent;")
        main_layout.addWidget(self.sidebar)

        self.setStyleSheet("""
            #card {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #dcdde1;
            }
            QLabel {
                color: #2f3640;
            }
            QPushButton {
                background-color: #dcdde1;
                border: none;
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #bfc2c7;
            }
        """)

        if os.path.exists("background.txt"):
            with open("background.txt", "r", encoding="utf-8") as f:
                path = f.read().strip()
                if path and os.path.exists(path):
                    self.set_background_image(path)

    def on_sidebar_changed(self, index):
        if index == 2:
            from main import SettingsWindow
            dlg = SettingsWindow(self)
            dlg.background_selected.connect(self.set_background_image)
            dlg.exec()

    def set_background_image(self, image_path):
        if not image_path or not os.path.exists(image_path):
            self._bg_label.setVisible(False)
            return

        pix = QPixmap(image_path)
        if pix.isNull():
            print("⚠️ Не удалось загрузить изображение:", image_path)
            return

        self._bg_pixmap = pix
        self._bg_label.setPixmap(self._bg_pixmap)
        self._bg_label.setVisible(True)
        self._bg_label.lower()
        self._update_bg_geometry()

        with open("background.txt", "w", encoding="utf-8") as f:
            f.write(image_path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_bg_geometry()

    def _update_bg_geometry(self):
        if not self._bg_pixmap:
            return
        self._bg_label.setGeometry(0, 0, self.width(), self.height())
        scaled = self._bg_pixmap.scaled(
            self._bg_label.size(),
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation
        )
        self._bg_label.setPixmap(scaled)
        self._bg_label.lower()

    def open_editor(self, title, desc):
        self.editor_page.set_content(title, desc)
        self.stack.setCurrentWidget(self.editor_page)

    def go_back(self):
        self.stack.setCurrentWidget(self.card_page)

class SettingsWindow(QDialog):
    background_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.resize(400, 200)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.info_label = QLabel("Выберите изображение для фона:")
        self.info_label.setStyleSheet("color: black; font-size: 14px;")
        layout.addWidget(self.info_label)

        self.select_button = QPushButton("📁 Выбрать изображение")
        self.select_button.clicked.connect(self.select_background)
        layout.addWidget(self.select_button)

        layout.addStretch()

        self.setStyleSheet("""
            QDialog {
                background-color: #f5f6fa;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.4);
                border: 1px solid rgba(0, 0, 0, 0.15);
                border-radius: 8px;
                padding: 8px 14px;
                transition: all 0.25s ease;
                color: #000000;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.08);
            }
        """)

    def select_background(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите фоновое изображение", "", "Изображения (*.png *.jpg *.jpeg *.bmp)"
        )
        if path:
            self.background_selected.emit(path)
            self.accept()

if __name__ == "__main__":
    app = QApplication([])
    win = MainWindow()
    win.show()
    app.exec()
