import re
import sys
import json
import requests
import datetime
from datetime import timezone
import logging
import webbrowser
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLineEdit, QTextEdit, QListWidget, QLabel, 
                             QInputDialog, QMessageBox, QDialog, QDialogButtonBox, QFormLayout,
                             QComboBox, QListWidgetItem, QTreeWidget, QTreeWidgetItem, QSplitter)
from PyQt5.QtCore import Qt, QRegExp, QTimer
from PyQt5.QtGui import QColor, QTextCharFormat, QFont, QSyntaxHighlighter, QPalette, QTextCursor

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))
        keyword_format.setFontWeight(QFont.Bold)

        keyword_patterns = ["\\bdef\\b", "\\bclass\\b", "\\bif\\b", "\\belse\\b", "\\belif\\b",
                            "\\bfor\\b", "\\bwhile\\b", "\\btry\\b", "\\bexcept\\b", "\\bfinally\\b",
                            "\\breturn\\b", "\\bimport\\b", "\\bfrom\\b", "\\bas\\b", "\\bpass\\b"]

        self.highlightingRules = [(QRegExp(pattern), keyword_format)
                                  for pattern in keyword_patterns]

        class_format = QTextCharFormat()
        class_format.setFontWeight(QFont.Bold)
        class_format.setForeground(QColor("#4EC9B0"))
        self.highlightingRules.append((QRegExp("\\bQ[A-Za-z]+\\b"),
                                       class_format))

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))
        self.highlightingRules.append((QRegExp("\".*\""), string_format))
        self.highlightingRules.append((QRegExp("'.*'"), string_format))

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6A9955"))
        self.highlightingRules.append((QRegExp("#[^\n]*"), comment_format))

    def highlightBlock(self, text):
        for pattern, format in self.highlightingRules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)

class PlainTextEdit(QTextEdit):
    def insertFromMimeData(self, source):
        if source.hasText():
            self.insertPlainText(source.text())
        else:
            super().insertFromMimeData(source)

class PlainLineEdit(QLineEdit):
    def insertFromMimeData(self, source):
        if source.hasText():
            self.insert(source.text())
        else:
            super().insertFromMimeData(source)

class Settings:
    def __init__(self):
        self.oauth_token = ""
        self.iam_token = ""
        self.iam_token_expires = datetime.datetime.now(timezone.utc)
        self.system_prompt = "Ты должен писать только код. И ничего больше. \nТы используешь PyTest, Python в написании кода.\nА так же используешь Chrome в качестве основного браузера. \nВ конце ничего так же не требуется писать."
    
    def save(self):
        with open('settings.json', 'w') as f:
            json.dump({
                'oauth_token': self.oauth_token,
                'iam_token': self.iam_token,
                'iam_token_expires': self.iam_token_expires.isoformat(),
                'system_prompt': self.system_prompt
            }, f)
    
    def load(self):
        try:
            with open('settings.json', 'r') as f:
                data = json.load(f)
                self.oauth_token = data.get('oauth_token', "")
                self.iam_token = data.get('iam_token', "")
                self.iam_token_expires = datetime.datetime.fromisoformat(data.get('iam_token_expires', datetime.datetime.now(timezone.utc).isoformat()))
                self.system_prompt = data.get('system_prompt', self.system_prompt)
        except FileNotFoundError:
            pass

    def get_iam_token(self):
        if datetime.datetime.now(timezone.utc) >= self.iam_token_expires:
            self.refresh_iam_token()
        return self.iam_token

    def refresh_iam_token(self):
        url = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
        payload = {"yandexPassportOauthToken": self.oauth_token}
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            logging.info(f"Received data: {data}")
            self.iam_token = data['iamToken']
            if isinstance(data['expiresAt'], str):
                expires_at = datetime.datetime.fromisoformat(data['expiresAt'].replace('Z', '+00:00'))
            else:
                expires_at = datetime.datetime.fromtimestamp(data['expiresAt'], tz=timezone.utc)
            self.iam_token_expires = expires_at
            self.save()
        except Exception as e:
            logging.error(f"Error refreshing IAM token: {str(e)}")
            raise

class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Настройки")
        self.layout = QFormLayout(self)

        self.oauth_token_input = QLineEdit(self.settings.oauth_token)
        self.system_prompt_input = QTextEdit(self.settings.system_prompt)
        self.get_oauth_button = QPushButton("Получить OAuth токен")
        self.get_oauth_button.clicked.connect(self.open_oauth_page)

        self.layout.addRow("OAuth Token:", self.oauth_token_input)
        self.layout.addRow(self.get_oauth_button)
        self.layout.addRow("System Prompt:", self.system_prompt_input)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)
        self.layout.addRow(self.buttons)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    def accept(self):
        self.settings.oauth_token = self.oauth_token_input.text()
        self.settings.system_prompt = self.system_prompt_input.toPlainText()
        self.settings.save()
        super().accept()

    def open_oauth_page(self):
        webbrowser.open("https://yandex.cloud/ru/docs/iam/operations/iam-token/create#:~:text=%D1%8D%D1%82%D0%BE%D0%B3%D0%BE%20%D0%BF%D0%B5%D1%80%D0%B5%D0%B9%D0%B4%D0%B8%D1%82%D0%B5%20%D0%BF%D0%BE-,%D1%81%D1%81%D1%8B%D0%BB%D0%BA%D0%B5,-%2C%20%D0%BD%D0%B0%D0%B6%D0%BC%D0%B8%D1%82%D0%B5%20%D0%A0%D0%B0%D0%B7%D1%80%D0%B5%D1%88%D0%B8%D1%82%D1%8C%20%D0%B8")

class Action:
    def __init__(self, name, description, code, category=None, generated_code=None):
        self.name = name
        self.description = description
        self.code = code
        self.category = category if category is not None else "Без категории"
        self.generated_code = generated_code if generated_code is not None else ""

class ActionDialog(QDialog):
    def __init__(self, parent=None, action=None, categories=[], settings=None):
        super().__init__(parent)
        self.setWindowTitle("Действие")
        self.layout = QFormLayout(self)
        self.categories = categories
        self.settings = settings

        self.name_input = PlainLineEdit(self)
        self.description_input = PlainTextEdit(self)
        self.code_input = PlainTextEdit(self)
        self.generated_code_input = PlainTextEdit(self)
        
        self.highlighter = PythonHighlighter(self.code_input.document())
        self.generated_highlighter = PythonHighlighter(self.generated_code_input.document())

        self.category_combo = QComboBox(self)
        self.category_combo.addItems(self.categories)
        self.category_combo.setEditable(True)

        self.layout.addRow("Название:", self.name_input)
        self.layout.addRow("Описание:", self.description_input)
        self.layout.addRow("Код:", self.code_input)
        self.layout.addRow("Сгенерированный код:", self.generated_code_input)
        self.layout.addRow("Категория:", self.category_combo)

        self.generate_button = QPushButton("🤖 Сгенерировать код")
        self.generate_button.clicked.connect(self.generate_code)
        self.layout.addRow(self.generate_button)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self)
        self.layout.addRow(self.buttons)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        if action:
            self.name_input.setText(action.name)
            self.description_input.setPlainText(action.description)
            self.code_input.setPlainText(action.code)
            self.generated_code_input.setPlainText(action.generated_code)
            self.category_combo.setCurrentText(action.category)

    def get_action_data(self):
        return {
            'name': self.name_input.text(),
            'description': self.description_input.toPlainText(),
            'code': self.code_input.toPlainText(),
            'generated_code': self.generated_code_input.toPlainText(),
            'category': self.category_combo.currentText()
        }

    def generate_code(self):
        user_code = self.code_input.toPlainText()
        system_prompt = self.settings.system_prompt
        prompt = f"""{system_prompt}

        {user_code}

        Верни только готовый код без дополнительного текста."""

        payload = {
            "messages": [
                {"text": prompt, "role": "user"}
            ],
            "completionOptions": {
                "stream": False,
                "maxTokens": 1500,
                "temperature": 0.1
            },
            "modelUri": "gpt://b1gkl7o40oq65tfl3s3j/yandexgpt"
        }

        try:
            headers = {
                "Authorization": f"Bearer {self.settings.get_iam_token()}",
                "Content-Type": "application/json"
            }
            
            logging.info(f"Request payload: {payload}")
            logging.info(f"Request headers: {headers}")

            response = requests.post("https://llm.api.cloud.yandex.net/foundationModels/v1/completion", 
                                     json=payload, headers=headers)
            
            logging.info(f"API Response: {response.text}")
            
            response.raise_for_status()
            data = response.json()
            generated_code = data['result']['alternatives'][0]['message']['text']
            
            # Очистка и форматирование кода
            generated_code = self.clean_and_format_code(generated_code)
            
            self.generated_code_input.setPlainText(generated_code)
        except requests.RequestException as e:
            logging.error(f"API Error Response: {response.text if response else 'No response'}")
            QMessageBox.warning(self, "Ошибка API", f"Не удалось получить ответ от API: {str(e)}")
        except (KeyError, IndexError) as e:
            QMessageBox.warning(self, "Ошибка данных", f"Не удалось извлечь сгенерированный код из ответа API: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Непредвиденная ошибка", f"Произошла непредвиденная ошибка: {str(e)}")

    def clean_and_format_code(self, code):
        # Удаление маркеров кода и лишних пробелов
        code = code.strip('`').strip()
        
        # Удаление ```python в начале и ``` в конце, если они есть
        code = re.sub(r'^```python\n', '', code)
        code = re.sub(r'\n```$', '', code)
        
        # Удаление пустых строк в начале и конце
        code = code.strip()
        
        # Замена множественных пустых строк на одну
        code = re.sub(r'\n{3,}', '\n\n', code)
        
        # Исправление отступов
        lines = code.split('\n')
        formatted_lines = []
        indent_level = 0
        for line in lines:
            stripped_line = line.strip()
            if stripped_line.startswith(('def ', 'class ', 'if ', 'elif ', 'else:', 'for ', 'while ', 'try:', 'except:', 'finally:')):
                formatted_lines.append(f"{'    ' * indent_level}{stripped_line}")
                if not stripped_line.endswith(':'):
                    continue
                if not stripped_line.startswith(('else:', 'elif ', 'except:', 'finally:')):
                    indent_level += 1
            elif stripped_line.startswith(('return ', 'break', 'continue', 'pass')):
                indent_level = max(0, indent_level - 1)
                formatted_lines.append(f"{'    ' * indent_level}{stripped_line}")
            elif stripped_line.startswith(')'):
                indent_level = max(0, indent_level - 1)
                formatted_lines.append(f"{'    ' * indent_level}{stripped_line}")
            else:
                formatted_lines.append(f"{'    ' * indent_level}{stripped_line}")

        return '\n'.join(formatted_lines)
class AutoTestLibrary(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Библиотека автотестера")
        self.setGeometry(100, 100, 1200, 700)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QHBoxLayout(self.central_widget)

        self.actions = []
        self.current_action = None
        self.categories = []
        self.settings = Settings()
        self.settings.load()

        self.init_ui()
        self.load_actions()
        self.apply_styles()

        # Запускаем таймер для обновления IAM токена каждый час
        self.token_refresh_timer = QTimer(self)
        self.token_refresh_timer.timeout.connect(self.refresh_iam_token)
        self.token_refresh_timer.start(3600000)  # 1 час в миллисекундах

    def init_ui(self):
        splitter = QSplitter(Qt.Horizontal)
        self.layout.addWidget(splitter)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.search_input = PlainLineEdit()
        self.search_input.setPlaceholderText("🔍 Поиск действий...")
        self.search_input.textChanged.connect(self.search_actions)
        left_layout.addWidget(self.search_input)

        self.category_tree = QTreeWidget()
        self.category_tree.setHeaderLabel("Категории")
        self.category_tree.setAnimated(True)
        self.category_tree.setHeaderHidden(True)
        left_layout.addWidget(self.category_tree)

        self.action_list = QListWidget()
        left_layout.addWidget(self.action_list)

        self.clean_categories_button = QPushButton("🧹 Удалить неиспользуемые категории")
        self.clean_categories_button.clicked.connect(self.clean_unused_categories)
        left_layout.addWidget(self.clean_categories_button)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.action_details = PlainTextEdit()
        self.action_details.setReadOnly(True)
        right_layout.addWidget(self.action_details)

        self.details_highlighter = PythonHighlighter(self.action_details.document())

        button_layout = QHBoxLayout()
        self.copy_button = QPushButton("📋 Копировать код")
        self.add_button = QPushButton("➕ Добавить")
        self.edit_button = QPushButton("✏️ Редактировать")
        self.delete_button = QPushButton("❌ Удалить")
        self.settings_button = QPushButton("⚙️ Настройки")
        
        for button in [self.copy_button, self.add_button, self.edit_button, self.delete_button, self.settings_button]:
            button.setMinimumHeight(40)
            button_layout.addWidget(button)

        right_layout.addLayout(button_layout)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        self.category_tree.itemClicked.connect(self.filter_by_category)
        self.copy_button.clicked.connect(self.copy_code)
        self.add_button.clicked.connect(self.add_action)
        self.edit_button.clicked.connect(self.edit_action)
        self.delete_button.clicked.connect(self.delete_action)
        self.settings_button.clicked.connect(self.open_settings)
        self.action_list.itemClicked.connect(self.show_action_details)

    def apply_styles(self):
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ButtonText, Qt.white)
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.HighlightedText, Qt.black)
        QApplication.setPalette(dark_palette)

        style = """
        QWidget {
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 14px;
            background-color: #353535;
            color: white;
        }
        QPushButton {
            background-color: #2a82da;
            color: white;
            border: none;
            padding: 5px 15px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #3a92ea;
        }
        QLineEdit, QTextEdit, QListWidget, QTreeWidget {
            border: 1px solid #3a3a3a;
            border-radius: 4px;
            padding: 5px;
            background-color: #1e1e1e;
            color: white;
        }
        QTreeWidget::item:selected, QListWidget::item:selected {
            background-color: #2a82da;
        }
        QTreeWidget::item {
            padding: 5px 0;
        }
        QTreeWidget::branch {
            background-color: #1e1e1e;
        }
        QTreeWidget::branch:selected {
            background-color: #2a82da;
        }
        QTreeWidget::item:hover, QTreeWidget::branch:hover {
            background-color: #2a82da50;
        }
        QTreeWidget {
            outline: none;
        }
        QTreeWidget::item:selected {
            border: none;
        }
        QMessageBox {
            background-color: #353535;
        }
        QMessageBox QLabel {
            color: white;
        }
        QMessageBox QPushButton {
            background-color: #2a82da;
            color: white;
            border: none;
            padding: 5px 15px;
            border-radius: 4px;
        }
        QMessageBox QPushButton:hover {
            background-color: #3a92ea;
        }
        """
        self.setStyleSheet(style)

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec_():
            self.refresh_iam_token()

    def refresh_iam_token(self):
        try:
            self.settings.refresh_iam_token()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка обновления токена", str(e))

    def copy_code(self):
        if self.current_action:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.current_action.code)
            msg_box = QMessageBox(self)
            msg_box.setStyleSheet(self.styleSheet())
            msg_box.information(self, "Копирование", "Код скопирован в буфер обмена!")

    def search_actions(self):
        query = self.search_input.text().lower()
        self.action_list.clear()
        for action in self.actions:
            if query in action.name.lower() or query in action.description.lower() or query in action.code.lower():
                self.action_list.addItem(action.name)

    def filter_by_category(self, item, column):
        category = item.text(column)
        self.action_list.clear()
        for action in self.actions:
            if action.category == category or category == "Все категории":
                self.action_list.addItem(action.name)

    def add_action(self):
        dialog = ActionDialog(self, categories=self.categories, settings=self.settings)
        if dialog.exec_():
            action_data = dialog.get_action_data()
            new_action = Action(**action_data)
            self.actions.append(new_action)
            self.update_categories([new_action.category])
            self.update_action_list()
            self.save_actions()

    def edit_action(self):
        if self.current_action:
            dialog = ActionDialog(self, self.current_action, self.categories, self.settings)
            if dialog.exec_():
                action_data = dialog.get_action_data()
                self.current_action.name = action_data['name']
                self.current_action.description = action_data['description']
                self.current_action.code = action_data['code']
                self.current_action.generated_code = action_data['generated_code']
                self.current_action.category = action_data['category']
                self.update_categories([self.current_action.category])
                self.save_actions()
                self.update_action_list()
                
                for i in range(self.action_list.count()):
                    if self.action_list.item(i).text() == self.current_action.name:
                        self.action_list.setCurrentItem(self.action_list.item(i))
                        break
                
                self.show_action_details(self.action_list.currentItem())

    def delete_action(self):
        if self.current_action:
            reply = QMessageBox.question(self, "Удалить действие", f"Вы уверены, что хотите удалить действие '{self.current_action.name}'?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.actions.remove(self.current_action)
                self.save_actions()
                self.update_action_list()
                self.action_details.clear()

    def show_action_details(self, item):
        if item is None:
            self.action_details.clear()
            self.current_action = None
        else:
            for action in self.actions:
                if action.name == item.text():
                    self.current_action = action
                    details = f"Название: {action.name}\n\n"
                    details += f"Категория: {action.category}\n\n"
                    details += f"Описание: {action.description}\n\n"
                    details += f"Код:\n{action.code}\n\n"
                    details += f"Сгенерированный код:\n{action.generated_code}"
                    self.action_details.setPlainText(details)
                    break

    def update_action_list(self):
        self.action_list.clear()
        for action in self.actions:
            self.action_list.addItem(action.name)

    def update_categories(self, new_categories):
        for category in new_categories:
            if category not in self.categories:
                self.categories.append(category)
        self.update_category_tree()

    def update_category_tree(self):
        self.category_tree.clear()
        all_categories = QTreeWidgetItem(self.category_tree)
        all_categories.setText(0, "Все категории")
        all_categories.setData(0, Qt.UserRole, "all")
        for category in self.categories:
            item = QTreeWidgetItem(self.category_tree)
            item.setText(0, category)
            item.setData(0, Qt.UserRole, category)
        self.category_tree.expandAll()

    def clean_unused_categories(self):
        used_categories = set(action.category for action in self.actions)
        unused_categories = [cat for cat in self.categories if cat not in used_categories]
        
        if unused_categories:
            reply = QMessageBox.question(self, "Удалить категории", 
                                         f"Следующие категории не используются:\n{', '.join(unused_categories)}\n\nУдалить их?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.categories = list(used_categories)
                self.update_category_tree()
                QMessageBox.information(self, "Категории удалены", "Неиспользуемые категории были удалены.")
        else:
            QMessageBox.information(self, "Нет неиспользуемых категорий", "Все категории используются.")

    def save_actions(self):
        with open('actions.json', 'w', encoding='utf-8') as f:
            json.dump([{**action.__dict__, 'generated_code': action.generated_code} for action in self.actions], f, ensure_ascii=False, indent=4)

    def load_actions(self):
        try:
            with open('actions.json', 'r', encoding='utf-8') as f:
                actions_data = json.load(f)
                self.actions = []
                for data in actions_data:
                    if 'category' not in data:
                        data['category'] = 'Без категории'
                    if 'generated_code' not in data:
                        data['generated_code'] = ''
                    action = Action(**data)
                    self.actions.append(action)
                    self.update_categories([action.category])
                
                self.update_action_list()
                self.update_category_tree()
        except FileNotFoundError:
            pass
        except json.JSONDecodeError:
            QMessageBox.warning(self, "Ошибка загрузки", "Файл с действиями поврежден. Начинаем с пустой библиотеки.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Произошла непредвиденная ошибка при загрузке действий: {str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = AutoTestLibrary()
    window.show()
    sys.exit(app.exec_())
