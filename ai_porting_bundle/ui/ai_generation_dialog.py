"""
AI Generation Dialog for creating clips using AI providers
"""

import os
import base64
import mimetypes
import subprocess
import tempfile
import time
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QComboBox, QCheckBox, QPushButton, QProgressBar, QMessageBox,
    QGroupBox, QSpinBox, QDoubleSpinBox, QFileDialog, QRadioButton
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap

from classes.app import get_app
from classes.logger import log
from classes.ai_providers.frame_extractor import FrameExtractor


class GenerationWorker(QThread):
    """Worker thread for AI generation to avoid blocking UI"""
    finished = pyqtSignal(str)  # Emits path to generated file
    error = pyqtSignal(str)     # Emits error message
    progress = pyqtSignal(str)  # Emits progress updates

    def __init__(self, provider, params):
        super().__init__()
        log.info(f"[AI Worker] Init with provider={type(provider).__name__}, params type={type(params)}")
        self.provider = provider
        self.params = params
        log.info(f"[AI Worker] Params keys: {list(params.keys()) if isinstance(params, dict) else 'NOT A DICT'}")

    def run(self):
        try:
            log.info(f"[AI Worker] Starting generation with params: {self.params}")
            self.progress.emit("Starting generation...")
            log.info(f"[AI Worker] Calling provider.generate(**params)")
            result_path = self.provider.generate(**self.params)
            log.info(f"[AI Worker] Generation complete: {result_path}")
            self.finished.emit(result_path)
        except Exception as e:
            log.error(f"[AI Worker] Generation error: {e}", exc_info=True)
            self.error.emit(str(e))


class AIGenerationDialog(QDialog):
    """Dialog for generating AI clips"""

    def __init__(self, parent, track_id, track_label):
        log.info(f"[AI Dialog Init] Starting init for track {track_id}, label {track_label}")
        try:
            super().__init__(parent)
            log.info("[AI Dialog Init] QDialog super().__init__() completed")
            self.track_id = track_id
            self.track_label = track_label
            self.generated_file_path = None
            self.worker = None
            self.record_process = None
            self.record_output_path = None
            self.user_audio_file = None
            self.audio_mode = "tts"
            log.info("[AI Dialog Init] Member variables set")

            self.setWindowTitle(f"Generate AI Clip - {track_label}")
            log.info("[AI Dialog Init] Window title set")
            self.setMinimumWidth(600)
            self.setMinimumHeight(500)
            log.info("[AI Dialog Init] Window size set")

            log.info("[AI Dialog Init] Calling setup_ui()")
            self.setup_ui()
            log.info("[AI Dialog Init] setup_ui() completed")
            log.info("[AI Dialog Init] Calling load_settings()")
            self.load_settings()
            log.info("[AI Dialog Init] __init__() completed successfully")
        except Exception as e:
            log.error(f"[AI Dialog Init] EXCEPTION during init: {e}", exc_info=True)
            raise

    def setup_ui(self):
        layout = QVBoxLayout()

        # Provider selection
        provider_group = QGroupBox("AI Provider")
        provider_layout = QVBoxLayout()

        self.provider_combo = QComboBox()
        self.populate_providers()
        self.provider_combo.currentIndexChanged.connect(self.on_provider_changed)
        provider_layout.addWidget(QLabel("Select Provider:"))
        provider_layout.addWidget(self.provider_combo)

        provider_group.setLayout(provider_layout)
        layout.addWidget(provider_group)

        # Character selection
        character_group = QGroupBox("Character (Optional)")
        character_layout = QVBoxLayout()
        
        char_row = QHBoxLayout()
        char_row.addWidget(QLabel("Select Character:"))
        self.character_combo = QComboBox()
        self.character_combo.addItem("(None)", None)
        self.populate_characters()
        self.character_combo.currentIndexChanged.connect(self.on_character_changed)
        char_row.addWidget(self.character_combo, 1)
        character_layout.addLayout(char_row)
        
        self.character_info_label = QLabel("")
        self.character_info_label.setWordWrap(True)
        self.character_info_label.setStyleSheet("color: #666; font-size: 10px;")
        character_layout.addWidget(self.character_info_label)
        
        character_group.setLayout(character_layout)
        layout.addWidget(character_group)

        # Generation parameters
        params_group = QGroupBox("Generation Parameters")
        params_layout = QVBoxLayout()

        # Prompt
        params_layout.addWidget(QLabel("Prompt:"))
        self.prompt_text = QTextEdit()
        self.prompt_text.setMaximumHeight(100)
        self.prompt_text.setPlaceholderText("Describe what you want to generate...")
        params_layout.addWidget(self.prompt_text)

        # Start Frame (First Frame) - automatically extracted from last clip
        start_frame_group = QGroupBox("Start Frame (First Frame)")
        start_frame_layout = QVBoxLayout()
        
        start_frame_row1 = QHBoxLayout()
        self.use_start_frame_cb = QCheckBox("Use last frame of previous clip as start frame")
        self.use_start_frame_cb.setChecked(True)
        self.use_start_frame_cb.toggled.connect(self.on_start_frame_toggled)
        start_frame_row1.addWidget(self.use_start_frame_cb)
        start_frame_layout.addLayout(start_frame_row1)
        
        start_frame_row2 = QHBoxLayout()
        self.start_frame_preview = QLabel("")
        self.start_frame_preview.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.start_frame_preview.setMinimumHeight(80)
        self.start_frame_preview.setVisible(False)
        self.start_frame_file_label = QLabel("")
        self.start_frame_file_label.setVisible(False)
        self.start_frame_browse_btn = QPushButton("Browse...")
        self.start_frame_browse_btn.setVisible(False)
        self.start_frame_browse_btn.clicked.connect(self.browse_start_frame)
        start_frame_row2.addWidget(self.start_frame_preview)
        start_frame_row2.addWidget(self.start_frame_file_label, 1)
        start_frame_row2.addWidget(self.start_frame_browse_btn)
        start_frame_layout.addLayout(start_frame_row2)
        
        start_frame_group.setLayout(start_frame_layout)
        params_layout.addWidget(start_frame_group)
        
        # End Frame - optional, separate from start frame
        end_frame_group = QGroupBox("End Frame (Optional)")
        end_frame_layout = QVBoxLayout()
        
        end_frame_row = QHBoxLayout()
        self.use_end_frame_cb = QCheckBox("Specify end frame for interpolation")
        self.use_end_frame_cb.toggled.connect(self.on_end_frame_toggled)
        end_frame_row.addWidget(self.use_end_frame_cb)
        end_frame_layout.addLayout(end_frame_row)
        
        end_frame_row2 = QHBoxLayout()
        self.end_frame_preview = QLabel("")
        self.end_frame_preview.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.end_frame_preview.setMinimumHeight(80)
        self.end_frame_preview.setVisible(False)
        self.end_frame_file_label = QLabel("")
        self.end_frame_file_label.setVisible(False)
        self.end_frame_browse_btn = QPushButton("Browse...")
        self.end_frame_browse_btn.setVisible(False)
        self.end_frame_browse_btn.clicked.connect(self.browse_end_frame)
        end_frame_row2.addWidget(self.end_frame_preview)
        end_frame_row2.addWidget(self.end_frame_file_label, 1)
        end_frame_row2.addWidget(self.end_frame_browse_btn)
        end_frame_layout.addLayout(end_frame_row2)
        
        end_frame_group.setLayout(end_frame_layout)
        params_layout.addWidget(end_frame_group)

        # Reference Images - optional, separate from start/end frames
        ref_group = QGroupBox("Reference Images (Optional)")
        ref_layout = QVBoxLayout()
        ref_row = QHBoxLayout()
        self.add_refs_btn = QPushButton("Add reference images...")
        self.add_refs_btn.clicked.connect(self.add_reference_images)
        self.refs_label = QLabel("(none)")
        ref_row.addWidget(self.add_refs_btn)
        ref_row.addWidget(self.refs_label, 1)
        ref_layout.addLayout(ref_row)
        ref_group.setLayout(ref_layout)
        params_layout.addWidget(ref_group)

        # Audio source (WaveSpeed)
        self.audio_group = QGroupBox("Audio Source")
        audio_layout = QVBoxLayout()
        self.audio_mode_tts = QRadioButton("Use ElevenLabs text-to-speech")
        self.audio_mode_tts.setChecked(True)
        self.audio_mode_tts.toggled.connect(lambda checked: checked and self.set_audio_mode("tts"))
        audio_layout.addWidget(self.audio_mode_tts)

        self.audio_script_text = QTextEdit()
        self.audio_script_text.setPlaceholderText("Enter script for ElevenLabs to speak...")
        self.audio_script_text.setMaximumHeight(80)
        audio_layout.addWidget(self.audio_script_text)

        self.audio_mode_record = QRadioButton("Record your voice and convert to character")
        self.audio_mode_record.toggled.connect(lambda checked: checked and self.set_audio_mode("record"))
        audio_layout.addWidget(self.audio_mode_record)

        record_row = QHBoxLayout()
        self.record_button = QPushButton("Start Recording")
        self.record_button.clicked.connect(self.toggle_recording)
        record_row.addWidget(self.record_button)
        self.record_status_label = QLabel("Not recording")
        record_row.addWidget(self.record_status_label, 1)
        audio_layout.addLayout(record_row)

        self.audio_mode_file = QRadioButton("Use existing audio (convert to character voice)")
        self.audio_mode_file.toggled.connect(lambda checked: checked and self.set_audio_mode("file"))
        audio_layout.addWidget(self.audio_mode_file)

        file_row = QHBoxLayout()
        self.audio_file_label = QLabel("No audio selected")
        file_row.addWidget(self.audio_file_label, 1)
        self.audio_file_button = QPushButton("Browse audio...")
        self.audio_file_button.clicked.connect(self.browse_audio_file)
        file_row.addWidget(self.audio_file_button)
        audio_layout.addLayout(file_row)

        self.audio_group.setLayout(audio_layout)
        self.audio_group.setVisible(False)
        params_layout.addWidget(self.audio_group)
        self.set_audio_mode("tts")

        # Duration (for video)
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel("Duration (seconds):"))
        self.duration_spin = QSpinBox()
        self.duration_spin.setMinimum(4)
        self.duration_spin.setMaximum(8)
        self.duration_spin.setSingleStep(2)
        self.duration_spin.setValue(8)
        duration_layout.addWidget(self.duration_spin)
        duration_layout.addStretch()
        params_layout.addLayout(duration_layout)

        # Quality/Resolution
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("Resolution:"))
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["720p", "1080p"])
        quality_layout.addWidget(self.resolution_combo)
        quality_layout.addStretch()
        params_layout.addLayout(quality_layout)

        params_group.setLayout(params_layout)
        layout.addWidget(params_group)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Buttons
        log.info("[AI Dialog UI] Creating buttons")
        button_layout = QHBoxLayout()
        self.generate_btn = QPushButton("Generate")
        log.info("[AI Dialog UI] Generate button created, connecting signal")
        self.generate_btn.clicked.connect(self.start_generation)
        log.info("[AI Dialog UI] Generate button signal connected")
        self.cancel_btn = QPushButton("Cancel")
        log.info("[AI Dialog UI] Cancel button created, connecting signal")
        self.cancel_btn.clicked.connect(self.reject)
        log.info("[AI Dialog UI] Cancel button signal connected")

        button_layout.addStretch()
        button_layout.addWidget(self.generate_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
        log.info("[AI Dialog UI] Buttons added to layout")

        log.info("[AI Dialog UI] Setting main layout")
        self.setLayout(layout)
        log.info("[AI Dialog UI] Main layout set, scheduling deferred init")
        QTimer.singleShot(0, self._deferred_init)
        log.info("[AI Dialog UI] setup_ui() complete")
    
    def _deferred_init(self):
        """Initialize dialog after it's shown to avoid signal connection issues"""
        try:
            if self.use_start_frame_cb.isChecked():
                self.on_start_frame_toggled(True)
            QTimer.singleShot(100, self.update_start_frame_preview)
        except Exception as e:
            log.error(f"Failed in deferred init: {e}")

    def populate_providers(self):
        """Populate provider dropdown based on track type and enabled providers"""
        s = get_app().get_settings()
        providers = []
        if s.get("ai.replicate.enabled") and self.track_label in ["Video", "Dialogue", "Visual Overlays", "Text/Overlays"]:
            providers.append(("Replicate (Veo / Image Models)", "replicate"))
        if s.get("ai.vertex.enabled") and self.track_label in ["Video", "Dialogue", "Visual Overlays", "Text/Overlays"]:
            providers.append(("Google Vertex (Veo 3.1)", "vertex"))
        if s.get("ai.elevenlabs.enabled") and self.track_label in ["Dialogue", "Music", "Sound FX"]:
            providers.append(("ElevenLabs (Text-to-Speech)", "elevenlabs"))
        if s.get("ai.wavespeed.enabled") and self.track_label in ["Video", "Dialogue"]:
            providers.append(("WaveSpeed InfiniteTalk (Lip-Sync)", "wavespeed"))
        if not providers:
            providers.append(("No providers enabled", None))
        for name, key in providers:
            self.provider_combo.addItem(name, key)

    def populate_characters(self):
        """Populate character dropdown from project data"""
        try:
            app = get_app()
            characters = app.project._data.get("characters", [])
            for char in characters:
                name = char.get("name", "Unnamed")
                self.character_combo.addItem(name, char)
        except Exception as e:
            log.error(f"Failed to populate characters: {e}")
    
    def on_character_changed(self):
        """Handle character selection - auto-populate reference images and voice ID"""
        char_data = self.character_combo.currentData()
        
        if not char_data:
            # No character selected
            self.character_info_label.setText("")
            return
        
        name = char_data.get("name", "")
        images = char_data.get("reference_images", [])
        voice_id = char_data.get("voice_id", "")
        
        # Update info label
        info_parts = []
        if images:
            info_parts.append(f"{len(images)} reference image(s)")
        if voice_id:
            info_parts.append(f"Voice ID: {voice_id}")
        
        if info_parts:
            self.character_info_label.setText(f"✓ {name}: " + ", ".join(info_parts))
        else:
            self.character_info_label.setText(f"⚠ {name}: No data configured")
        
        log.info(f"Character selected: {name} ({len(images)} images, voice: {voice_id})")

    def on_provider_changed(self):
        provider_key = self.provider_combo.currentData()
        if provider_key == "elevenlabs":
            self.use_start_frame_cb.setVisible(False)
            self.start_frame_preview.setVisible(False)
            self.start_frame_file_label.setVisible(False)
            self.start_frame_browse_btn.setVisible(False)
            self.use_end_frame_cb.setVisible(False)
            self.end_frame_preview.setVisible(False)
            self.end_frame_file_label.setVisible(False)
            self.end_frame_browse_btn.setVisible(False)
            self.add_refs_btn.setVisible(False)
            self.duration_spin.setEnabled(False)
            self.resolution_combo.setEnabled(False)
            self.audio_group.setVisible(False)
        else:
            self.use_start_frame_cb.setVisible(True)
            self.use_end_frame_cb.setVisible(True)
            self.add_refs_btn.setVisible(True)
            self.duration_spin.setEnabled(True)
            self.resolution_combo.setEnabled(True)
            self.on_start_frame_toggled(self.use_start_frame_cb.isChecked())
            self.on_end_frame_toggled(self.use_end_frame_cb.isChecked())
            self.audio_group.setVisible(provider_key == "wavespeed")
            if provider_key != "wavespeed":
                if self.record_process:
                    self.stop_recording()
                self.audio_mode_tts.setChecked(True)

    def load_settings(self):
        s = get_app().get_settings()
        prompt_key = f"ai.last_prompt.{self.track_label.lower().replace(' ', '_')}"
        last_prompt = s.get(prompt_key)
        if last_prompt:
            self.prompt_text.setPlainText(last_prompt)

    def save_settings(self):
        s = get_app().get_settings()
        prompt_key = f"ai.last_prompt.{self.track_label.lower().replace(' ', '_')}"
        # Only save if the setting exists (OpenShot's set() will warn if key doesn't exist)
        try:
            s.set(prompt_key, self.prompt_text.toPlainText())
        except Exception as e:
            log.debug(f"Could not save prompt to settings (key may not exist): {e}")

    def start_generation(self):
        log.info("[AI Dialog] start_generation() called")
        try:
            provider_key = self.provider_combo.currentData()
            log.info(f"[AI Dialog] Provider key: {provider_key}")
            if not provider_key:
                QMessageBox.warning(self, "No Provider", "Please enable an AI provider in the Models tab first.")
                return
            
            prompt = self.prompt_text.toPlainText().strip()
            log.info(f"[AI Dialog] Prompt length: {len(prompt)}")
            if not prompt:
                QMessageBox.warning(self, "No Prompt", "Please enter a prompt describing what you want to generate.")
                return
            
            self.save_settings()
            s = get_app().get_settings()
            api_key = s.get(f"ai.{provider_key}.api_key")
            
            # Vertex uses service account instead of API key
            if provider_key not in ("vertex",) and not api_key:
                QMessageBox.warning(self, "No API Key", f"Please set your {provider_key} API key in the Models tab first.")
                return

            first_frame_path = None
            if self.use_start_frame_cb.isChecked():
                if hasattr(self, "_start_frame_path") and self._start_frame_path:
                    first_frame_path = self._start_frame_path
                else:
                    self.status_label.setText("Extracting last frame from previous clip...")
                    first_frame_path = FrameExtractor.extract_last_frame_from_track(self.track_id)
                    if first_frame_path:
                        self._start_frame_path = first_frame_path
                        self.show_start_frame_preview(first_frame_path)
                    else:
                        self.status_label.setText("No previous clip found, generating from scratch...")
            
            last_frame_path = None
            if self.use_end_frame_cb.isChecked() and hasattr(self, "_end_frame_path") and self._end_frame_path:
                last_frame_path = self._end_frame_path

            # Get character data if selected
            char_data = self.character_combo.currentData()
            char_ref_images = []
            char_voice_id = None
            if char_data:
                char_ref_images = char_data.get("reference_images", [])
                char_voice_id = char_data.get("voice_id", "")
                log.info(f"Using character data: {len(char_ref_images)} images, voice: {char_voice_id}")

            duration_val = self.duration_spin.value()
            if duration_val not in (4, 6, 8):
                duration_val = min((4, 6, 8), key=lambda x: abs(x - duration_val))
                self.duration_spin.setValue(duration_val)
            
            params = {
                "prompt": prompt,
                "duration": duration_val,
                "resolution": self.resolution_combo.currentText(),
            }
            
            if provider_key == "replicate":
                from classes.ai_providers import replicate as replicate_mod
                provider = replicate_mod.ReplicateProvider(api_key=api_key)
                params["model"] = "google/veo-3.1"
                params["aspect_ratio"] = "16:9"
                params["generate_audio"] = True
                if first_frame_path:
                    params["first_frame_image"] = first_frame_path
                if last_frame_path:
                    params["last_frame_image"] = last_frame_path
                # Use character reference images if available, otherwise use manually added ones
                ref_imgs = char_ref_images if char_ref_images else (list(self._reference_images) if hasattr(self, "_reference_images") and self._reference_images else [])
                if ref_imgs:
                    params["reference_images"] = ref_imgs
                    params["duration"] = 8
                    params["resolution"] = "1080p"
            elif provider_key == "elevenlabs":
                from classes.ai_providers import elevenlabs as el_mod
                provider = el_mod.ElevenLabsProvider(api_key=api_key)
                params = {"text": prompt}
                # Use character voice ID if available
                if char_voice_id:
                    params["voice_id"] = char_voice_id
                    log.info(f"Using character voice ID: {char_voice_id}")
            elif provider_key == "vertex":
                log.info("[AI Dialog] Setting up Vertex provider")
                project_id = s.get("ai.vertex.project_id") or ""
                location = s.get("ai.vertex.location") or "us-central1"
                creds_path = s.get("ai.vertex.credentials_path") or ""
                model_name = s.get("ai.vertex.model") or "publishers/google/models/veo-3.1"
                log.info(f"[AI Dialog] Vertex config: project={project_id}, creds={creds_path}")
                if not project_id or not creds_path:
                    QMessageBox.warning(self, "Vertex AI Not Configured",
                                        "Set Vertex credentials path and project ID in the Models tab.")
                    return
                from classes.ai_providers import vertex as vx_mod
                provider = vx_mod.VertexVeoProvider(credentials_path=creds_path, project_id=project_id,
                                                    location=location, model=model_name)
                if first_frame_path:
                    params["first_frame_image"] = first_frame_path
                if last_frame_path:
                    params["last_frame_image"] = last_frame_path
                # Use character reference images if available, otherwise use manually added ones
                ref_imgs = char_ref_images if char_ref_images else (list(self._reference_images) if hasattr(self, "_reference_images") and self._reference_images else [])
                if ref_imgs:
                    params["reference_images"] = ref_imgs
                    params["duration"] = 8
                    params["resolution"] = "1080p"
            elif provider_key == "wavespeed":
                from classes.ai_providers import wavespeed as ws_mod
                from classes.ai_providers import elevenlabs as el_mod
                provider = ws_mod.WaveSpeedProvider(api_key=api_key)

                if self.record_process:
                    self.stop_recording()

                # Determine image source (prefer character reference image)
                image_path = None
                if char_ref_images:
                    image_path = char_ref_images[0]
                elif first_frame_path:
                    image_path = first_frame_path
                elif hasattr(self, "_reference_images") and self._reference_images:
                    image_path = self._reference_images[0]
                if not image_path or not os.path.exists(image_path):
                    QMessageBox.warning(self, "Missing Image", "WaveSpeed requires at least one reference image (character or start frame).")
                    return

                eleven_key = s.get("ai.elevenlabs.api_key")
                audio_path = None

                if self.audio_mode == "tts":
                    script = self.audio_script_text.toPlainText().strip()
                    if not script:
                        QMessageBox.warning(self, "No Script", "Enter dialogue text for ElevenLabs to speak.")
                        return
                    if not eleven_key:
                        QMessageBox.warning(self, "ElevenLabs Key Missing", "Set your ElevenLabs API key in the Models tab to synthesize audio.")
                        return
                    voice_id = char_voice_id or None
                    el_provider = el_mod.ElevenLabsProvider(api_key=eleven_key)
                    audio_path = el_provider.generate(text=script, voice_id=voice_id, model_id="eleven_multilingual_v2")
                elif self.audio_mode == "record":
                    if not self.record_output_path or not os.path.exists(self.record_output_path):
                        QMessageBox.warning(self, "No Recording", "Record audio before generating.")
                        return
                    if not eleven_key:
                        QMessageBox.warning(self, "ElevenLabs Key Missing", "Set your ElevenLabs API key in the Models tab to convert recorded audio.")
                        return
                    voice_id = char_voice_id or None
                    el_provider = el_mod.ElevenLabsProvider(api_key=eleven_key)
                    audio_path = el_provider.speech_to_speech(self.record_output_path, voice_id=voice_id, model_id="eleven_multilingual_sts_v2")
                elif self.audio_mode == "file":
                    if not self.user_audio_file or not os.path.exists(self.user_audio_file):
                        QMessageBox.warning(self, "No Audio File", "Select an audio file to use.")
                        return
                    if eleven_key and char_voice_id:
                        el_provider = el_mod.ElevenLabsProvider(api_key=eleven_key)
                        audio_path = el_provider.speech_to_speech(self.user_audio_file, voice_id=char_voice_id, model_id="eleven_multilingual_sts_v2")
                    else:
                        audio_path = self.convert_audio_to_mp3(self.user_audio_file)
                else:
                    QMessageBox.warning(self, "Audio Mode", "Select an audio source for WaveSpeed.")
                    return

                if not audio_path or not os.path.exists(audio_path):
                    QMessageBox.warning(self, "Audio Error", "Failed to prepare audio for WaveSpeed.")
                    return

                params["image_path"] = image_path
                params["audio_path"] = audio_path
                params["prompt"] = prompt
                params["resolution"] = self.resolution_combo.currentText()
            else:
                QMessageBox.warning(self, "Error", f"Unknown provider: {provider_key}")
                return

            log.info(f"[AI Dialog] Creating worker with params: {list(params.keys())}")
            self.worker = GenerationWorker(provider, params)
            self.worker.finished.connect(self.on_generation_finished, Qt.QueuedConnection)
            self.worker.error.connect(self.on_generation_error, Qt.QueuedConnection)
            self.worker.progress.connect(self.on_generation_progress, Qt.QueuedConnection)
            self.generate_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            self.status_label.setText("Generating... This may take several minutes.")
            self.worker.start()
            log.info("[AI Dialog] Worker started")
            
        except Exception as e:
            log.error(f"[AI Dialog] EXCEPTION in start_generation: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to start generation:\n\n{e}")

    def on_generation_progress(self, message):
        self.status_label.setText(message)

    def on_generation_finished(self, file_path):
        log.info(f"[AI Dialog] on_generation_finished called: {file_path}")
        self.generated_file_path = file_path
        self.status_label.setText(f"✓ Generated: {os.path.basename(file_path)}")
        self.progress_bar.setVisible(False)
        self.generate_btn.setEnabled(True)
        # Wait for worker thread to finish before closing
        if self.worker and self.worker.isRunning():
            log.info("[AI Dialog] Waiting for worker thread to finish...")
            self.worker.wait(5000)  # Wait up to 5 seconds
        # Don't show modal dialog - just auto-accept and let the parent handle it
        # QMessageBox.information(self, "Generation Complete",
        #                         f"Clip generated successfully!\n\nFile: {file_path}\n\nClick OK to add it to the timeline.")
        self.accept()

    def on_generation_error(self, error_message):
        log.info(f"[AI Dialog] on_generation_error called: {error_message}")
        self.status_label.setText(f"✗ Error: {error_message}")
        self.progress_bar.setVisible(False)
        self.generate_btn.setEnabled(True)
        # Wait for worker thread to finish before continuing
        if self.worker and self.worker.isRunning():
            log.info("[AI Dialog] Waiting for worker thread to finish after error...")
            self.worker.wait(5000)  # Wait up to 5 seconds
        # Don't show modal dialog on error - just display in status
        # QMessageBox.critical(self, "Generation Failed", f"Failed to generate clip:\n\n{error_message}")

    def on_start_frame_toggled(self, checked):
        if checked:
            self.start_frame_preview.setVisible(True)
            self.start_frame_file_label.setVisible(True)
            self.start_frame_browse_btn.setVisible(True)
            if not hasattr(self, "_start_frame_path") or not self._start_frame_path:
                QTimer.singleShot(0, self.update_start_frame_preview)
        else:
            self.start_frame_preview.setVisible(False)
            self.start_frame_file_label.setVisible(False)
            self.start_frame_browse_btn.setVisible(False)
            if hasattr(self, "_start_frame_path"):
                delattr(self, "_start_frame_path")

    def on_end_frame_toggled(self, checked):
        if checked:
            self.end_frame_preview.setVisible(True)
            self.end_frame_file_label.setVisible(True)
            self.end_frame_browse_btn.setVisible(True)
        else:
            self.end_frame_preview.setVisible(False)
            self.end_frame_file_label.setVisible(False)
            self.end_frame_browse_btn.setVisible(False)
            if hasattr(self, "_end_frame_path"):
                delattr(self, "_end_frame_path")

    def browse_start_frame(self):
        try:
            file, _ = QFileDialog.getOpenFileName(
                self, 
                "Select Start Frame Image", 
                "", 
                "Images (*.png *.jpg *.jpeg *.webp)",
                options=QFileDialog.DontUseNativeDialog
            )
            if file and os.path.exists(file):
                self._start_frame_path = file
                self.show_start_frame_preview(file)
        except Exception as e:
            log.error(f"Failed to browse start frame: {e}")

    def browse_end_frame(self):
        try:
            file, _ = QFileDialog.getOpenFileName(
                self, 
                "Select End Frame Image", 
                "", 
                "Images (*.png *.jpg *.jpeg *.webp)",
                options=QFileDialog.DontUseNativeDialog
            )
            if file and os.path.exists(file):
                self._end_frame_path = file
                self.show_end_frame_preview(file)
        except Exception as e:
            log.error(f"Failed to browse end frame: {e}")

    def update_start_frame_preview(self):
        try:
            path = FrameExtractor.extract_last_frame_from_track(self.track_id)
            if path and os.path.exists(path):
                self._start_frame_path = path
                self.show_start_frame_preview(path)
        except Exception:
            pass

    def show_start_frame_preview(self, image_path):
        pix = QPixmap(image_path)
        if not pix.isNull():
            self.start_frame_preview.setPixmap(pix.scaledToHeight(80, Qt.SmoothTransformation))
            self.start_frame_preview.setToolTip(f"Start frame: {image_path}")
            self.start_frame_preview.setVisible(True)
            self.start_frame_file_label.setText(f"Start frame: {os.path.basename(image_path)}")
            self.start_frame_file_label.setVisible(True)

    def show_end_frame_preview(self, image_path):
        pix = QPixmap(image_path)
        if not pix.isNull():
            self.end_frame_preview.setPixmap(pix.scaledToHeight(80, Qt.SmoothTransformation))
            self.end_frame_preview.setToolTip(f"End frame: {image_path}")
            self.end_frame_preview.setVisible(True)
            self.end_frame_file_label.setText(f"End frame: {os.path.basename(image_path)}")
            self.end_frame_file_label.setVisible(True)

    def add_reference_images(self):
        try:
            files, _ = QFileDialog.getOpenFileNames(
                self, 
                "Select Reference Images", 
                "", 
                "Images (*.png *.jpg *.jpeg *.webp)",
                options=QFileDialog.DontUseNativeDialog
            )
            if files:
                self._reference_images = files
                names = [os.path.basename(f) for f in files]
                self.refs_label.setText(", ".join(names[:3]) + (" ..." if len(names) > 3 else ""))
        except Exception as e:
            log.error(f"Failed to browse reference images: {e}")

    def set_audio_mode(self, mode):
        if mode == self.audio_mode:
            return
        if mode != "record" and self.record_process:
            self.stop_recording()
        self.audio_mode = mode
        self.audio_script_text.setEnabled(mode == "tts")
        if mode == "tts" and not self.audio_script_text.toPlainText().strip():
            self.audio_script_text.setPlainText(self.prompt_text.toPlainText())
        self.record_button.setEnabled(mode == "record")
        self.audio_file_button.setEnabled(mode == "file")
        self.audio_file_label.setEnabled(mode == "file")
        if mode != "file":
            self.audio_file_label.setText("No audio selected")
            self.user_audio_file = None
        if mode != "record":
            self.record_status_label.setText("Not recording")
            self.record_button.setText("Start Recording")

    def toggle_recording(self):
        if self.record_process:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        try:
            fd, path = tempfile.mkstemp(prefix="openshot_record_", suffix=".wav")
            os.close(fd)
            # Default command for macOS (avfoundation). Users may adjust device index if needed.
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "avfoundation",
                "-i", ":0",
                "-ac", "1",
                "-ar", "44100",
                path,
            ]
            self.record_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.record_output_path = path
            self.record_button.setText("Stop Recording")
            self.record_status_label.setText("Recording... click stop when finished")
        except FileNotFoundError:
            self.record_process = None
            self.record_output_path = None
            QMessageBox.critical(self, "ffmpeg not found", "ffmpeg is required for recording. Please install ffmpeg and ensure it is in your PATH.")
        except Exception as e:
            self.record_process = None
            self.record_output_path = None
            log.error(f"Failed to start recording: {e}", exc_info=True)
            QMessageBox.critical(self, "Recording Error", f"Could not start recording: {e}")

    def stop_recording(self):
        if not self.record_process:
            return
        try:
            self.record_process.terminate()
            try:
                self.record_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.record_process.kill()
        finally:
            self.record_process = None
            self.record_button.setText("Start Recording")
            if self.record_output_path and os.path.exists(self.record_output_path):
                self.record_status_label.setText(os.path.basename(self.record_output_path))
            else:
                self.record_status_label.setText("Recording failed")

    def browse_audio_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select audio file",
            "",
            "Audio Files (*.wav *.mp3 *.m4a *.flac *.aac)",
            options=QFileDialog.DontUseNativeDialog,
        )
        if file_path:
            self.user_audio_file = file_path
            self.audio_file_label.setText(os.path.basename(file_path))
        else:
            self.user_audio_file = None
            self.audio_file_label.setText("No audio selected")

    def convert_audio_to_mp3(self, input_path):
        try:
            fd, path = tempfile.mkstemp(prefix="openshot_audio_", suffix=".mp3")
            os.close(fd)
            cmd = [
                "ffmpeg",
                "-y",
                "-i", input_path,
                "-vn",
                "-ar", "44100",
                "-ac", "2",
                "-b:a", "192k",
                path,
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.decode("utf-8", errors="ignore"))
            return path
        except FileNotFoundError:
            QMessageBox.critical(self, "ffmpeg not found", "ffmpeg is required to process audio. Please install ffmpeg and ensure it is available in PATH.")
            raise
        except Exception as e:
            log.error(f"Failed to convert audio: {e}", exc_info=True)
            raise

