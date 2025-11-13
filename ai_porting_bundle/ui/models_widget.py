from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout, QCheckBox,
    QLineEdit, QPushButton, QLabel, QHBoxLayout
)

from classes.app import get_app
from classes.logger import log


class ModelsWidget(QWidget):
    """
    Simple AI Models settings panel:
      - Replicate
      - ElevenLabs
      - WaveSpeed (InfiniteTalk)
    Stores settings using OpenShot's SettingStore with keys:
      ai.replicate.enabled, ai.replicate.api_key
      ai.elevenlabs.enabled, ai.elevenlabs.api_key
      ai.wavespeed.enabled, ai.wavespeed.api_key
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ = get_app()._tr
        self.s = get_app().get_settings()
        self.setObjectName("ModelsWidget")
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(8, 8, 8, 8)
        self.layout().setSpacing(10)

        # Header
        header = QLabel(self._("AI Models"))
        font = header.font()
        font.setPointSize(font.pointSize() + 2)
        font.setBold(True)
        header.setFont(font)
        self.layout().addWidget(header)

        # Provider sections
        self.grp_replicate = self._provider_group(
            title="Replicate",
            enabled_key="ai.replicate.enabled",
            api_key_key="ai.replicate.api_key",
            help_text=self._("Used for models like Veo, NanoBanana, etc.")
        )
        self.grp_elevenlabs = self._provider_group(
            title="ElevenLabs",
            enabled_key="ai.elevenlabs.enabled",
            api_key_key="ai.elevenlabs.api_key",
            help_text=self._("Text-to-speech and voice cloning.")
        )
        self.grp_wavespeed = self._provider_group(
            title="WaveSpeed (InfiniteTalk)",
            enabled_key="ai.wavespeed.enabled",
            api_key_key="ai.wavespeed.api_key",
            help_text=self._("Lip-sync image→video and video→video.")
        )

        self.layout().addWidget(self.grp_replicate)
        self.layout().addWidget(self.grp_elevenlabs)
        self.layout().addWidget(self.grp_wavespeed)

        # Save row
        save_row = QHBoxLayout()
        save_row.addStretch(1)
        self.btn_save = QPushButton(self._("Save"))
        self.btn_save.clicked.connect(self.save_settings)
        save_row.addWidget(self.btn_save)
        self.layout().addLayout(save_row)
        self.layout().addStretch(1)

        # Load initial values
        log.info("ModelsWidget: initializing")
        self.load_settings()

    def _provider_group(self, title, enabled_key, api_key_key, help_text=""):
        group = QGroupBox(title)
        group.setLayout(QFormLayout())
        group.layout().setLabelAlignment(Qt.AlignLeft)
        group.layout().setFormAlignment(Qt.AlignLeft | Qt.AlignTop)

        chk = QCheckBox(self._("Enabled"))
        chk.setObjectName(enabled_key)
        api = QLineEdit()
        api.setObjectName(api_key_key)
        api.setEchoMode(QLineEdit.Password)
        api.setPlaceholderText(self._("Enter API Key"))

        group.layout().addRow(chk)
        group.layout().addRow(self._("API Key:"), api)
        if help_text:
            hint = QLabel(help_text)
            hint.setWordWrap(True)
            hint.setStyleSheet("color: gray;")
            group.layout().addRow(hint)
        return group

    def load_settings(self):
        # Helper to get bool/string with default fallback
        def get_bool(key, default=False):
            try:
                val = self.s.get(key)
                log.debug(f"ModelsWidget: get_bool {key} -> {val}")
                return bool(val)
            except Exception as ex:
                log.warning(f"ModelsWidget: failed to load bool {key}: {ex}")
                return default

        def get_str(key, default=""):
            try:
                v = self.s.get(key)
                log.debug(f"ModelsWidget: get_str {key} -> {bool(v)}")
                return "" if v is None else str(v)
            except Exception as ex:
                log.warning(f"ModelsWidget: failed to load string {key}: {ex}")
                return default

        # Replicate
        replicate_enabled = get_bool("ai.replicate.enabled", False)
        replicate_key = get_str("ai.replicate.api_key")
        self._set_checked("ai.replicate.enabled", replicate_enabled)
        self._set_text("ai.replicate.api_key", replicate_key)
        log.info(f"ModelsWidget: Replicate enabled={replicate_enabled} key_present={bool(replicate_key)}")

        # ElevenLabs
        eleven_enabled = get_bool("ai.elevenlabs.enabled", False)
        eleven_key = get_str("ai.elevenlabs.api_key")
        self._set_checked("ai.elevenlabs.enabled", eleven_enabled)
        self._set_text("ai.elevenlabs.api_key", eleven_key)
        log.info(f"ModelsWidget: ElevenLabs enabled={eleven_enabled} key_present={bool(eleven_key)}")

        # WaveSpeed
        wave_enabled = get_bool("ai.wavespeed.enabled", False)
        wave_key = get_str("ai.wavespeed.api_key")
        self._set_checked("ai.wavespeed.enabled", wave_enabled)
        self._set_text("ai.wavespeed.api_key", wave_key)
        log.info(f"ModelsWidget: WaveSpeed enabled={wave_enabled} key_present={bool(wave_key)}")

    def _find(self, object_name):
        return self.findChild(QWidget, object_name)

    def _set_checked(self, key, value):
        w = self._find(key)
        if isinstance(w, QCheckBox):
            w.setChecked(value)

    def _set_text(self, key, value):
        w = self._find(key)
        if isinstance(w, QLineEdit):
            w.setText(value)

    def save_settings(self):
        def get_checked(key):
            w = self._find(key)
            return bool(w.isChecked()) if isinstance(w, QCheckBox) else False

        def get_text(key):
            w = self._find(key)
            return str(w.text()).strip() if isinstance(w, QLineEdit) else ""

        # Persist to SettingStore (keys must exist in defaults)
        self.s.set("ai.replicate.enabled", get_checked("ai.replicate.enabled"))
        self.s.set("ai.replicate.api_key", get_text("ai.replicate.api_key"))
        self.s.set("ai.elevenlabs.enabled", get_checked("ai.elevenlabs.enabled"))
        self.s.set("ai.elevenlabs.api_key", get_text("ai.elevenlabs.api_key"))
        self.s.set("ai.wavespeed.enabled", get_checked("ai.wavespeed.enabled"))
        self.s.set("ai.wavespeed.api_key", get_text("ai.wavespeed.api_key"))
        self.s.save()
        log.info("ModelsWidget: settings saved")

