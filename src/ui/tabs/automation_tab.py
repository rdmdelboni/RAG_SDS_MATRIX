"""Automation tab for harvesting, scheduling, and SDS generation.

Provides tools for automated data collection and processing workflows.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtWidgets

from . import BaseTab, TabContext


class AutomationTab(BaseTab):
    """Tab for automation tasks including harvesting and scheduling."""

    def __init__(self, context: TabContext) -> None:
        super().__init__(context)
        self.project_root = Path.cwd()
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the automation tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Harvest and process group
        harvest_group = QtWidgets.QGroupBox("Harvest & Process")
        h_layout = QtWidgets.QGridLayout(harvest_group)
        row = 0

        self.cas_file_input = QtWidgets.QLineEdit()
        cas_btn = QtWidgets.QPushButton("Browse CAS file")
        self._style_button(cas_btn)
        cas_btn.clicked.connect(self._on_select_cas_file)
        h_layout.addWidget(QtWidgets.QLabel("CAS list file"), row, 0)
        h_layout.addWidget(self.cas_file_input, row, 1)
        h_layout.addWidget(cas_btn, row, 2)
        row += 1

        self.harvest_output_input = QtWidgets.QLineEdit(str(self.project_root / "data/input/harvested"))
        out_btn = QtWidgets.QPushButton("Browse output folder")
        self._style_button(out_btn)
        out_btn.clicked.connect(self._on_select_harvest_output)
        h_layout.addWidget(QtWidgets.QLabel("Output folder"), row, 0)
        h_layout.addWidget(self.harvest_output_input, row, 1)
        h_layout.addWidget(out_btn, row, 2)
        row += 1

        self.harvest_limit = QtWidgets.QSpinBox()
        self.harvest_limit.setRange(1, 10)
        self.harvest_limit.setValue(3)
        self.process_checkbox = QtWidgets.QCheckBox("Process immediately")
        self.process_checkbox.setChecked(True)
        self.no_rag_checkbox = QtWidgets.QCheckBox("Disable RAG during processing")
        h_layout.addWidget(QtWidgets.QLabel("Max downloads per CAS"), row, 0)
        h_layout.addWidget(self.harvest_limit, row, 1)
        row += 1
        h_layout.addWidget(self.process_checkbox, row, 0, 1, 2)
        row += 1
        h_layout.addWidget(self.no_rag_checkbox, row, 0, 1, 2)
        row += 1

        harvest_btn = QtWidgets.QPushButton("Run Harvest + Process")
        self._style_button(harvest_btn)
        harvest_btn.clicked.connect(self._on_run_harvest_process)
        h_layout.addWidget(harvest_btn, row, 0, 1, 3)

        layout.addWidget(harvest_group)

        # Scheduler group
        sched_group = QtWidgets.QGroupBox("Scheduled Harvest")
        s_layout = QtWidgets.QGridLayout(sched_group)
        self.interval_spin = QtWidgets.QSpinBox()
        self.interval_spin.setRange(5, 24 * 60)
        self.interval_spin.setValue(60)
        self.iterations_spin = QtWidgets.QSpinBox()
        self.iterations_spin.setRange(0, 1000)
        self.iterations_spin.setValue(0)
        s_layout.addWidget(QtWidgets.QLabel("Interval (minutes)"), 0, 0)
        s_layout.addWidget(self.interval_spin, 0, 1)
        s_layout.addWidget(QtWidgets.QLabel("Iterations (0 = infinite)"), 1, 0)
        s_layout.addWidget(self.iterations_spin, 1, 1)
        sched_btn = QtWidgets.QPushButton("Start Scheduler (background)")
        self._style_button(sched_btn)
        sched_btn.clicked.connect(self._on_run_scheduler)
        s_layout.addWidget(sched_btn, 2, 0, 1, 2)
        layout.addWidget(sched_group)

        # Experiment packet group
        packet_group = QtWidgets.QGroupBox("Experiment Packet")
        p_layout = QtWidgets.QGridLayout(packet_group)
        row = 0
        self.packet_matrix_input = QtWidgets.QLineEdit()
        m_btn = QtWidgets.QPushButton("Browse matrix export")
        self._style_button(m_btn)
        m_btn.clicked.connect(self._on_select_packet_matrix)
        p_layout.addWidget(QtWidgets.QLabel("Matrix file"), row, 0)
        p_layout.addWidget(self.packet_matrix_input, row, 1)
        p_layout.addWidget(m_btn, row, 2)
        row += 1
        self.packet_sds_dir_input = QtWidgets.QLineEdit(str(self.project_root / "data/input/harvested"))
        sd_btn = QtWidgets.QPushButton("Browse SDS folder")
        self._style_button(sd_btn)
        sd_btn.clicked.connect(self._on_select_packet_sds_dir)
        p_layout.addWidget(QtWidgets.QLabel("SDS folder"), row, 0)
        p_layout.addWidget(self.packet_sds_dir_input, row, 1)
        p_layout.addWidget(sd_btn, row, 2)
        row += 1
        self.packet_cas_input = QtWidgets.QLineEdit()
        self.packet_cas_input.setPlaceholderText("Comma-separated CAS numbers")
        p_layout.addWidget(QtWidgets.QLabel("CAS list"), row, 0)
        p_layout.addWidget(self.packet_cas_input, row, 1, 1, 2)
        row += 1
        packet_btn = QtWidgets.QPushButton("Create Packet")
        self._style_button(packet_btn)
        packet_btn.clicked.connect(self._on_export_packet)
        p_layout.addWidget(packet_btn, row, 0, 1, 3)
        layout.addWidget(packet_group)

        # SDS generation group (stub)
        gen_group = QtWidgets.QGroupBox("SDS Generator (stub)")
        g_layout = QtWidgets.QGridLayout(gen_group)
        row = 0
        self.gen_data_input = QtWidgets.QLineEdit(str(self.project_root / "examples/sds_stub.json"))
        data_btn = QtWidgets.QPushButton("Browse JSON")
        self._style_button(data_btn)
        data_btn.clicked.connect(self._on_select_gen_data)
        g_layout.addWidget(QtWidgets.QLabel("Data JSON"), row, 0)
        g_layout.addWidget(self.gen_data_input, row, 1)
        g_layout.addWidget(data_btn, row, 2)
        row += 1
        self.gen_out_input = QtWidgets.QLineEdit(str(self.project_root / "output/sds_stub.pdf"))
        out_btn2 = QtWidgets.QPushButton("Browse output PDF")
        self._style_button(out_btn2)
        out_btn2.clicked.connect(self._on_select_gen_output)
        g_layout.addWidget(QtWidgets.QLabel("Output PDF"), row, 0)
        g_layout.addWidget(self.gen_out_input, row, 1)
        g_layout.addWidget(out_btn2, row, 2)
        row += 1
        gen_btn = QtWidgets.QPushButton("Generate SDS PDF")
        self._style_button(gen_btn)
        gen_btn.clicked.connect(self._on_generate_sds_pdf)
        g_layout.addWidget(gen_btn, row, 0, 1, 3)
        layout.addWidget(gen_group)

        self.automation_status = QtWidgets.QLabel("Ready")
        self._style_label(self.automation_status, color=self.colors.get("subtext", "#a6adc8"))
        layout.addWidget(self.automation_status)

        layout.addStretch()

    # File selection handlers
    def _on_select_cas_file(self) -> None:
        """Handle CAS file selection."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select CAS list", str(self.project_root))
        if path:
            self.cas_file_input.setText(path)

    def _on_select_harvest_output(self) -> None:
        """Handle harvest output folder selection."""
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select output folder", str(self.project_root))
        if path:
            self.harvest_output_input.setText(path)

    def _on_select_packet_matrix(self) -> None:
        """Handle packet matrix file selection."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select matrix file", str(self.project_root))
        if path:
            self.packet_matrix_input.setText(path)

    def _on_select_packet_sds_dir(self) -> None:
        """Handle packet SDS directory selection."""
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select SDS folder", str(self.project_root))
        if path:
            self.packet_sds_dir_input.setText(path)

    def _on_select_gen_data(self) -> None:
        """Handle SDS generator data selection."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select JSON data", str(self.project_root))
        if path:
            self.gen_data_input.setText(path)

    def _on_select_gen_output(self) -> None:
        """Handle SDS generator output selection."""
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Select output PDF", str(self.project_root / "output/sds_stub.pdf")
        )
        if path:
            self.gen_out_input.setText(path)

    # Action handlers (to be implemented)
    def _on_run_harvest_process(self) -> None:
        """Handle harvest + process execution."""
        self._set_status("Harvest + process not yet fully implemented")

    def _on_run_scheduler(self) -> None:
        """Handle scheduler start."""
        self._set_status("Scheduler not yet fully implemented")

    def _on_export_packet(self) -> None:
        """Handle experiment packet export."""
        self._set_status("Packet export not yet fully implemented")

    def _on_generate_sds_pdf(self) -> None:
        """Handle SDS PDF generation."""
        self._set_status("SDS generation not yet fully implemented")
