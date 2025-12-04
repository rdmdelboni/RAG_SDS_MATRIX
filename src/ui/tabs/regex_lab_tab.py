"""Regex Lab tab for testing and optimizing extraction patterns.

Provides an interface to test regex patterns on individual SDS documents
and save patterns to the catalog.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from PySide6 import QtWidgets

from . import BaseTab, TabContext
from ...sds.regex_catalog import get_regex_catalog
from ...sds.profile_router import ProfileRouter
from ..components import WorkerSignals


class RegexLabTab(BaseTab):
    """Tab for testing and editing regex extraction patterns."""

    def __init__(self, context: TabContext) -> None:
        super().__init__(context)
        self.project_root = Path.cwd()
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the regex lab tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # File picker
        file_row = QtWidgets.QHBoxLayout()
        self.regex_file_input = QtWidgets.QLineEdit()
        file_btn = QtWidgets.QPushButton("Browse SDS")
        self._style_button(file_btn)
        file_btn.clicked.connect(self._on_select_regex_file)
        file_row.addWidget(QtWidgets.QLabel("SDS file"))
        file_row.addWidget(self.regex_file_input)
        file_row.addWidget(file_btn)
        layout.addLayout(file_row)

        # Profile selector + optional fields
        ctrl_row = QtWidgets.QHBoxLayout()
        self.profile_combo = QtWidgets.QComboBox()
        self.profile_combo.addItem("Auto")
        for name in self.context.profile_router.list_profiles():
            self.profile_combo.addItem(name)
        ctrl_row.addWidget(QtWidgets.QLabel("Profile"))
        ctrl_row.addWidget(self.profile_combo)

        self.fields_input = QtWidgets.QLineEdit()
        self.fields_input.setPlaceholderText(
            "Optional: fields comma-separated (e.g., product_name,cas_number)"
        )
        ctrl_row.addWidget(self.fields_input)

        run_btn = QtWidgets.QPushButton("Run regex extraction")
        self._style_button(run_btn)
        run_btn.clicked.connect(self._on_run_regex_lab)
        ctrl_row.addWidget(run_btn)
        layout.addLayout(ctrl_row)

        # Results table
        self.regex_table = QtWidgets.QTableWidget()
        self.regex_table.setColumnCount(4)
        self.regex_table.setHorizontalHeaderLabels(["Field", "Value", "Confidence", "Source"])
        self.regex_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.regex_table)

        # Pattern editor
        editor_group = QtWidgets.QGroupBox("Edit / Save Pattern")
        e_layout = QtWidgets.QGridLayout(editor_group)
        row = 0
        self.regex_profile_edit = QtWidgets.QLineEdit()
        self.regex_field_edit = QtWidgets.QLineEdit()
        self.regex_pattern_edit = QtWidgets.QLineEdit()
        self.regex_flags_edit = QtWidgets.QLineEdit("im")
        e_layout.addWidget(QtWidgets.QLabel("Profile"), row, 0)
        e_layout.addWidget(self.regex_profile_edit, row, 1)
        row += 1
        e_layout.addWidget(QtWidgets.QLabel("Field"), row, 0)
        e_layout.addWidget(self.regex_field_edit, row, 1)
        row += 1
        e_layout.addWidget(QtWidgets.QLabel("Pattern"), row, 0)
        e_layout.addWidget(self.regex_pattern_edit, row, 1)
        row += 1
        e_layout.addWidget(QtWidgets.QLabel("Flags (imxs)"), row, 0)
        e_layout.addWidget(self.regex_flags_edit, row, 1)
        row += 1
        save_btn = QtWidgets.QPushButton("Save pattern to catalog")
        self._style_button(save_btn)
        save_btn.clicked.connect(self._on_save_regex_pattern)
        reload_btn = QtWidgets.QPushButton("Reload profiles")
        self._style_button(reload_btn)
        reload_btn.clicked.connect(self._on_reload_profiles)
        e_layout.addWidget(save_btn, row, 0)
        e_layout.addWidget(reload_btn, row, 1)
        layout.addWidget(editor_group)

        self.regex_status = QtWidgets.QLabel("Ready")
        self._style_label(self.regex_status, color=self.colors.get("subtext", "#a6adc8"))
        layout.addWidget(self.regex_status)

        layout.addStretch()

    def _on_select_regex_file(self) -> None:
        """Handle file selection for regex lab."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select SDS", str(self.project_root))
        if path:
            self.regex_file_input.setText(path)

    def _on_run_regex_lab(self) -> None:
        """Handle regex lab run button."""
        file_path = self.regex_file_input.text().strip()
        if not file_path or not Path(file_path).exists():
            self._set_status("Select a valid SDS file for regex lab", error=True)
            self.regex_status.setText("No file selected")
            return
        profile_choice = self.profile_combo.currentText()
        fields_raw = self.fields_input.text().strip()
        fields = [f.strip() for f in fields_raw.split(",") if f.strip()] if fields_raw else None

        self._start_task(
            self._regex_lab_task,
            Path(file_path),
            profile_choice,
            fields,
            on_result=self._on_regex_lab_done,
        )
        self.regex_status.setText("Running…")

    def _regex_lab_task(
        self,
        file_path: Path,
        profile_choice: str,
        fields: list[str] | None,
        *,
        signals: WorkerSignals | None = None,
    ) -> dict:
        """Execute regex lab task in background."""
        doc = self.context.sds_extractor.extract_document(file_path)
        text = doc.get("text", "")
        sections = doc.get("sections", {})
        profile = None
        if profile_choice and profile_choice != "Auto":
            profile = self.context.profile_router.identify_profile(text, preferred=profile_choice)
        else:
            profile = self.context.profile_router.identify_profile(text)

        results = self.context.heuristics.extract_all_fields(text, sections, profile=profile)
        if fields:
            results = {k: v for k, v in results.items() if k in fields}
        if signals:
            signals.message.emit(f"Detected profile: {profile.name}")
        return {"profile": profile.name, "results": results}

    def _on_regex_lab_done(self, result: object) -> None:
        """Handle regex lab completion."""
        if not isinstance(result, dict):
            self.regex_status.setText("No results")
            return
        profile = result.get("profile", "Auto")
        results = result.get("results", {}) or {}
        rows = []
        for field, data in results.items():
            rows.append(
                {
                    "field": field,
                    "value": str(data.get("value", "")),
                    "confidence": f"{data.get('confidence', 0.0):.2f}",
                    "source": data.get("source", ""),
                }
            )
        self.regex_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.regex_table.setItem(r, 0, QtWidgets.QTableWidgetItem(row["field"]))
            self.regex_table.setItem(r, 1, QtWidgets.QTableWidgetItem(row["value"]))
            self.regex_table.setItem(r, 2, QtWidgets.QTableWidgetItem(row["confidence"]))
            self.regex_table.setItem(r, 3, QtWidgets.QTableWidgetItem(row["source"]))
        self.regex_table.resizeColumnsToContents()
        self.regex_status.setText(f"Profile: {profile} | Fields: {len(rows)}")
        self._set_status(f"Regex lab: profile {profile}, {len(rows)} fields")

    def _on_save_regex_pattern(self) -> None:
        """Save regex pattern to catalog."""
        profile = self.regex_profile_edit.text().strip() or self.profile_combo.currentText()
        field = self.regex_field_edit.text().strip()
        pattern = self.regex_pattern_edit.text().strip()
        flags = self.regex_flags_edit.text().strip() or "im"
        if not profile or profile == "Auto" or not field or not pattern:
            self._set_status("Profile, field, and pattern are required", error=True)
            self.regex_status.setText("Missing required fields")
            return
        try:
            catalog_path = self.project_root / "data/regex/regexes.json"
            if not catalog_path.exists():
                raise FileNotFoundError(f"Catalog not found at {catalog_path}")
            with open(catalog_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            profiles = data.get("profiles", [])
            target = next((p for p in profiles if p.get("name", "").lower() == profile.lower()), None)
            if not target:
                target = {"name": profile, "identifiers": [], "regexes": {}}
                profiles.append(target)
            target.setdefault("regexes", {})
            target["regexes"][field] = {"pattern": pattern, "flags": flags}
            data["profiles"] = profiles
            data["version"] = f"ui-edit-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            with open(catalog_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._set_status(f"Saved pattern for {profile}.{field}")
            self.regex_status.setText(f"Saved to catalog ({catalog_path.name})")
        except Exception as exc:
            self._set_status(f"Failed to save pattern: {exc}", error=True)
            self.regex_status.setText("Save failed")

    def _on_reload_profiles(self) -> None:
        """Reload profiles from catalog."""
        try:
            get_regex_catalog.cache_clear()
            # Note: context.profile_router is already created at startup
            # We create a new one to refresh
            new_router = ProfileRouter()
            current = self.profile_combo.currentText()
            self.profile_combo.clear()
            self.profile_combo.addItem("Auto")
            for name in new_router.list_profiles():
                self.profile_combo.addItem(name)
            idx = self.profile_combo.findText(current)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)
            self._set_status("Profiles reloaded from catalog")
            self.regex_status.setText("Profiles reloaded")
        except Exception as exc:
            self._set_status(f"Failed to reload profiles: {exc}", error=True)
