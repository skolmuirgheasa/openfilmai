"""
Characters Widget - Manage AI character profiles with reference images and voice IDs
"""

import os
import json
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QDialog, QLabel, QLineEdit, QFileDialog,
    QMessageBox, QGroupBox, QFormLayout
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QIcon

from classes.app import get_app
from classes.logger import log


class CharacterDialog(QDialog):
    """Dialog for creating/editing a character"""
    
    def __init__(self, parent, character_data=None):
        super().__init__(parent)
        self.character_data = character_data or {}
        self.reference_images = list(self.character_data.get("reference_images", []))
        
        self.setWindowTitle("Edit Character" if character_data else "New Character")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self.setup_ui()
        self.load_data()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Name
        name_group = QGroupBox("Character Name")
        name_layout = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., John Smith")
        name_layout.addRow("Name:", self.name_edit)
        name_group.setLayout(name_layout)
        layout.addWidget(name_group)
        
        # Reference Images
        images_group = QGroupBox("Reference Images (up to 3, order matters)")
        images_layout = QVBoxLayout()
        
        self.image_labels = []
        self.image_paths = [None, None, None]
        
        for i in range(3):
            img_row = QHBoxLayout()
            
            label = QLabel(f"Image {i+1}:")
            label.setMinimumWidth(60)
            img_row.addWidget(label)
            
            preview = QLabel("No image")
            preview.setFixedSize(80, 80)
            preview.setStyleSheet("border: 1px solid #ccc; background: #f0f0f0;")
            preview.setAlignment(Qt.AlignCenter)
            preview.setScaledContents(False)
            self.image_labels.append(preview)
            img_row.addWidget(preview)
            
            path_label = QLabel("")
            path_label.setWordWrap(True)
            img_row.addWidget(path_label, 1)
            
            browse_btn = QPushButton("Browse...")
            browse_btn.clicked.connect(lambda checked, idx=i: self.browse_image(idx))
            img_row.addWidget(browse_btn)
            
            clear_btn = QPushButton("Clear")
            clear_btn.clicked.connect(lambda checked, idx=i: self.clear_image(idx))
            img_row.addWidget(clear_btn)
            
            images_layout.addLayout(img_row)
        
        images_group.setLayout(images_layout)
        layout.addWidget(images_group)
        
        # Voice ID
        voice_group = QGroupBox("ElevenLabs Voice ID")
        voice_layout = QFormLayout()
        self.voice_id_edit = QLineEdit()
        self.voice_id_edit.setPlaceholderText("e.g., 21m00Tcm4TlvDq8ikWAM")
        voice_layout.addRow("Voice ID:", self.voice_id_edit)
        
        help_label = QLabel('<a href="https://elevenlabs.io/app/voice-library">Find voice IDs in ElevenLabs</a>')
        help_label.setOpenExternalLinks(True)
        voice_layout.addRow("", help_label)
        
        voice_group.setLayout(voice_layout)
        layout.addWidget(voice_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        save_btn.setDefault(True)
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
    
    def load_data(self):
        """Load existing character data"""
        if self.character_data:
            self.name_edit.setText(self.character_data.get("name", ""))
            self.voice_id_edit.setText(self.character_data.get("voice_id", ""))
            
            images = self.character_data.get("reference_images", [])
            for i, img_path in enumerate(images[:3]):
                if img_path and os.path.exists(img_path):
                    self.set_image(i, img_path)
    
    def browse_image(self, index):
        """Browse for a reference image"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                f"Select Reference Image {index + 1}",
                "",
                "Images (*.png *.jpg *.jpeg *.webp)",
                options=QFileDialog.DontUseNativeDialog
            )
            if file_path:
                self.set_image(index, file_path)
        except Exception as e:
            log.error(f"Failed to browse image: {e}")
    
    def set_image(self, index, path):
        """Set an image at the given index"""
        self.image_paths[index] = path
        
        # Update preview
        pix = QPixmap(path)
        if not pix.isNull():
            self.image_labels[index].setPixmap(pix.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.image_labels[index].setToolTip(path)
        
        # Update path label (find it in the layout)
        img_row = self.image_labels[index].parent().layout()
        if img_row and img_row.count() >= 3:
            path_label = img_row.itemAt(2).widget()
            if isinstance(path_label, QLabel):
                path_label.setText(os.path.basename(path))
    
    def clear_image(self, index):
        """Clear an image at the given index"""
        self.image_paths[index] = None
        self.image_labels[index].clear()
        self.image_labels[index].setText("No image")
        self.image_labels[index].setToolTip("")
        
        # Clear path label
        img_row = self.image_labels[index].parent().layout()
        if img_row and img_row.count() >= 3:
            path_label = img_row.itemAt(2).widget()
            if isinstance(path_label, QLabel):
                path_label.setText("")
    
    def get_data(self):
        """Get the character data from the form"""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Invalid Input", "Please enter a character name.")
            return None
        
        # Filter out None values from image paths
        images = [p for p in self.image_paths if p]
        
        return {
            "name": name,
            "reference_images": images,
            "voice_id": self.voice_id_edit.text().strip()
        }


class CharactersWidget(QWidget):
    """Widget for managing AI character profiles"""
    
    character_changed = pyqtSignal()  # Emitted when characters are modified
    
    def __init__(self, parent):
        super().__init__(parent)
        try:
            self.app = get_app()
            self.characters = []
            self.setup_ui()
            self.load_characters()
            log.info("CharactersWidget initialized successfully")
        except Exception as e:
            log.error(f"Failed to initialize CharactersWidget: {e}", exc_info=True)
            # Create a minimal error widget
            error_layout = QVBoxLayout()
            error_label = QLabel(f"Error loading Characters widget: {e}")
            error_label.setWordWrap(True)
            error_layout.addWidget(error_label)
            self.setLayout(error_layout)
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header
        header = QLabel("<b>AI Characters</b>")
        layout.addWidget(header)
        
        # Character list
        self.character_list = QListWidget()
        self.character_list.setAlternatingRowColors(True)
        self.character_list.itemDoubleClicked.connect(self.edit_character)
        layout.addWidget(self.character_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        add_btn = QPushButton("+ New Character")
        add_btn.clicked.connect(self.add_character)
        btn_layout.addWidget(add_btn)
        
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self.edit_character)
        btn_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self.delete_character)
        btn_layout.addWidget(delete_btn)
        
        layout.addLayout(btn_layout)
        
        # Info label
        info = QLabel("Characters store reference images and voice IDs for AI generation.")
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(info)
        
        self.setLayout(layout)
    
    def load_characters(self):
        """Load characters from project data"""
        try:
            project_data = self.app.project._data
            self.characters = project_data.get("characters", [])
            # Merge with persistent backup if project has none
            if not self.characters:
                backup_path = Path.home() / ".openshot_qt" / "ai_characters.json"
                if backup_path.exists():
                    with open(backup_path, "r", encoding="utf-8") as f:
                        backup_chars = json.load(f)
                        if isinstance(backup_chars, list):
                            self.characters = backup_chars
                            project_data["characters"] = backup_chars
                            self.app.project.has_unsaved_changes = True
                            try:
                                self.app.project.save()
                                log.info("Restored characters from backup into project")
                            except Exception as save_ex:
                                log.error(f"Failed to persist restored characters: {save_ex}", exc_info=True)
            self.refresh_list()
        except Exception as e:
            log.error(f"Failed to load characters: {e}")
            self.characters = []

    def save_characters(self):
        """Save characters to project data"""
        try:
            # Add to project data
            if "characters" not in self.app.project._data:
                self.app.project._data["characters"] = []
            self.app.project._data["characters"] = self.characters
            
            # Persist backup to disk immediately
            backup_dir = Path.home() / ".openshot_qt"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / "ai_characters.json"
            try:
                with open(backup_path, "w", encoding="utf-8") as f:
                    json.dump(self.characters, f, indent=2)
                log.info(f"Wrote characters backup to {backup_path}")
            except Exception as backup_ex:
                log.error(f"Failed to write characters backup: {backup_ex}")
            
            # Mark project as modified and save immediately so crashes don't lose data
            self.app.project.has_unsaved_changes = True
            try:
                project_path = getattr(self.app.project, "file_path", None)
                if not project_path and hasattr(self.app.project, "filename"):
                    project_path = self.app.project.filename
                if project_path:
                    self.app.project.save(project_path)
                else:
                    self.app.project.save(self.app.project.filename)
                log.info(f"Saved {len(self.characters)} characters to project (persisted)")
            except Exception as save_ex:
                log.error(f"Failed to persist characters to project file: {save_ex}", exc_info=True)
            
            self.character_changed.emit()
        except Exception as e:
            log.error(f"Failed to save characters: {e}")
    
    def refresh_list(self):
        """Refresh the character list display"""
        self.character_list.clear()
        for char in self.characters:
            name = char.get("name", "Unnamed")
            img_count = len(char.get("reference_images", []))
            voice = "✓" if char.get("voice_id") else "✗"
            
            item = QListWidgetItem(f"{name} ({img_count} imgs, voice: {voice})")
            item.setData(Qt.UserRole, char)
            self.character_list.addItem(item)
    
    def add_character(self):
        """Add a new character"""
        dlg = CharacterDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            if data:
                self.characters.append(data)
                self.save_characters()
                self.refresh_list()
    
    def edit_character(self):
        """Edit the selected character"""
        current = self.character_list.currentItem()
        if not current:
            return
        
        char_data = current.data(Qt.UserRole)
        index = self.characters.index(char_data)
        
        dlg = CharacterDialog(self, char_data)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            if data:
                self.characters[index] = data
                self.save_characters()
                self.refresh_list()
    
    def delete_character(self):
        """Delete the selected character"""
        current = self.character_list.currentItem()
        if not current:
            return
        
        char_data = current.data(Qt.UserRole)
        name = char_data.get("name", "this character")
        
        reply = QMessageBox.question(
            self,
            "Delete Character",
            f"Are you sure you want to delete '{name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.characters.remove(char_data)
            self.save_characters()
            self.refresh_list()
    
    def get_characters(self):
        """Get all characters"""
        return self.characters
    
    def get_character_by_name(self, name):
        """Get a character by name"""
        for char in self.characters:
            if char.get("name") == name:
                return char
        return None

