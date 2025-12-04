"""Automation tab for harvesting, scheduling, and SDS generation.

Provides tools for automated data collection and processing workflows.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

from PySide6 import QtWidgets

from . import BaseTab, TabContext
from ..components import WorkerSignals


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

    # Action handlers
    def _on_run_harvest_process(self) -> None:
        """Handle harvest + process execution."""
        cas_file = self.cas_file_input.text().strip()
        output_dir = self.harvest_output_input.text().strip()

        if not cas_file or not Path(cas_file).exists():
            self._set_status("Select a valid CAS file", error=True)
            return

        if not output_dir:
            self._set_status("Select an output folder", error=True)
            return

        process_immediately = self.process_checkbox.isChecked()
        use_rag = not self.no_rag_checkbox.isChecked()
        download_limit = self.harvest_limit.value()

        self._set_status(f"Starting harvest (limit: {download_limit} per CAS)…")
        self.automation_status.setText("Harvesting…")
        self._start_task(
            self._harvest_process_task,
            Path(cas_file),
            Path(output_dir),
            download_limit,
            process_immediately,
            use_rag,
            on_progress=self._on_harvest_progress,
            on_result=self._on_harvest_process_done,
        )

    def _harvest_process_task(
        self,
        cas_file: Path,
        output_dir: Path,
        limit: int,
        process: bool,
        use_rag: bool,
        *,
        signals: WorkerSignals | None = None,
    ) -> dict:
        """Execute harvest and process in background."""
        try:
            from ...harvester.core import SDSHarvester
            from ...harvester.inventory_sync import InventorySync
            from ...sds.processor import SDSProcessor

            harvester = SDSHarvester()
            sync = InventorySync()
            processor = SDSProcessor() if process else None

            output_dir.mkdir(parents=True, exist_ok=True)
            cas_numbers = [line.strip() for line in cas_file.read_text().splitlines()
                          if line.strip() and not line.startswith("#")]

            if not cas_numbers:
                if signals:
                    signals.error.emit("No valid CAS numbers in file")
                return {"success": False, "error": "No valid CAS numbers", "downloaded": 0, "processed": 0}

            downloaded = []
            processed = 0
            total = len(cas_numbers)

            for idx, cas in enumerate(cas_numbers, 1):
                if signals:
                    signals.progress.emit(int(50 * idx / total))
                    signals.message.emit(f"Searching CAS {cas} ({idx}/{total})…")

                results = harvester.find_sds(cas)
                if not results:
                    continue

                for res in results[:limit]:
                    file_path = harvester.download_sds(res, output_dir)
                    if file_path:
                        downloaded.append(file_path)
                        sync.sync_download(cas, file_path, source=res.source, url=res.url)

                        if processor:
                            try:
                                res_proc = processor.process(file_path, use_rag=use_rag)
                                processed += 1
                                if signals:
                                    signals.message.emit(f"Processed {file_path.name} (completeness: {res_proc.completeness:.2f})")
                            except Exception as exc:
                                if signals:
                                    signals.message.emit(f"Processing failed for {file_path.name}: {exc}")
                    else:
                        sync.mark_missing(cas, source=res.source, url=res.url, error_message="download failed")

            if signals:
                signals.progress.emit(100)
                signals.message.emit(f"Complete: {len(downloaded)} downloaded, {processed} processed")

            return {
                "success": True,
                "downloaded": len(downloaded),
                "processed": processed,
                "files": [str(p) for p in downloaded],
            }
        except Exception as e:
            if signals:
                signals.error.emit(str(e))
            return {"success": False, "error": str(e), "downloaded": 0, "processed": 0}

    def _on_harvest_progress(self, progress: int, message: str) -> None:
        """Handle harvest progress updates."""
        self.automation_status.setText(message)
        self._set_status(message)

    def _on_harvest_process_done(self, result: object) -> None:
        """Handle harvest + process completion."""
        if isinstance(result, dict) and result.get("success"):
            msg = f"Harvest complete: {result.get('downloaded', 0)} downloaded, {result.get('processed', 0)} processed"
            self._set_status(msg)
            self.automation_status.setText(msg)
        else:
            error = result.get("error") if isinstance(result, dict) else str(result)
            self._set_status(f"Harvest failed: {error}", error=True)
            self.automation_status.setText("Failed")

    def _on_run_scheduler(self) -> None:
        """Handle scheduler start."""
        cas_file = self.cas_file_input.text().strip()
        if not cas_file or not Path(cas_file).exists():
            self._set_status("Select a valid CAS file for scheduler", error=True)
            return

        interval = self.interval_spin.value()
        iterations = self.iterations_spin.value()
        output_dir = Path(self.harvest_output_input.text().strip())
        process_immediately = self.process_checkbox.isChecked()
        use_rag = not self.no_rag_checkbox.isChecked()
        download_limit = self.harvest_limit.value()

        self._set_status(f"Starting scheduler (interval: {interval}m, iterations: {iterations or '∞'})…")
        self.automation_status.setText("Scheduler running…")
        self._start_task(
            self._scheduler_task,
            Path(cas_file),
            interval,
            iterations,
            output_dir,
            download_limit,
            process_immediately,
            use_rag,
            on_progress=self._on_scheduler_progress,
            on_result=self._on_scheduler_done,
        )

    def _scheduler_task(
        self,
        cas_file: Path,
        interval: int,
        iterations: int,
        output_dir: Path,
        limit: int,
        process: bool,
        use_rag: bool,
        *,
        signals: WorkerSignals | None = None,
    ) -> dict:
        """Execute scheduler loop in background."""
        try:
            from ...harvester.core import SDSHarvester
            from ...harvester.inventory_sync import InventorySync
            from ...sds.processor import SDSProcessor

            cas_numbers = [line.strip() for line in cas_file.read_text().splitlines()
                          if line.strip() and not line.startswith("#")]
            if not cas_numbers:
                return {"success": False, "error": "No valid CAS numbers"}

            iteration = 0
            total_downloaded = 0
            total_processed = 0

            while True:
                iteration += 1
                if signals:
                    signals.message.emit(f"Scheduler iteration {iteration}…")

                harvester = SDSHarvester()
                sync = InventorySync()
                processor = SDSProcessor() if process else None
                output_dir.mkdir(parents=True, exist_ok=True)

                for cas in cas_numbers:
                    results = harvester.find_sds(cas)
                    if not results:
                        continue

                    for res in results[:limit]:
                        file_path = harvester.download_sds(res, output_dir)
                        if file_path:
                            total_downloaded += 1
                            sync.sync_download(cas, file_path, source=res.source, url=res.url)

                            if processor:
                                try:
                                    processor.process(file_path, use_rag=use_rag)
                                    total_processed += 1
                                except Exception:
                                    pass
                        else:
                            sync.mark_missing(cas, source=res.source, url=res.url, error_message="download failed")

                if signals:
                    signals.message.emit(f"Iteration {iteration} complete (total: {total_downloaded} downloaded)")

                # Check exit condition
                if iterations and iteration >= iterations:
                    break

                # Sleep before next iteration
                sleep_seconds = interval * 60
                for _ in range(interval):
                    if signals:
                        signals.message.emit(f"Waiting {interval - _} minutes until next run…")
                    time.sleep(60)

            return {
                "success": True,
                "iterations": iteration,
                "total_downloaded": total_downloaded,
                "total_processed": total_processed,
            }
        except Exception as e:
            if signals:
                signals.error.emit(str(e))
            return {"success": False, "error": str(e)}

    def _on_scheduler_progress(self, progress: int, message: str) -> None:
        """Handle scheduler progress updates."""
        self.automation_status.setText(message)

    def _on_scheduler_done(self, result: object) -> None:
        """Handle scheduler completion."""
        if isinstance(result, dict) and result.get("success"):
            msg = f"Scheduler complete: {result.get('iterations', 0)} iterations, {result.get('total_downloaded', 0)} downloaded"
            self._set_status(msg)
            self.automation_status.setText(msg)
        else:
            error = result.get("error") if isinstance(result, dict) else str(result)
            self._set_status(f"Scheduler failed: {error}", error=True)
            self.automation_status.setText("Failed")

    def _on_export_packet(self) -> None:
        """Handle experiment packet export."""
        matrix_file = self.packet_matrix_input.text().strip()
        sds_dir = self.packet_sds_dir_input.text().strip()
        cas_input = self.packet_cas_input.text().strip()

        if not matrix_file or not Path(matrix_file).exists():
            self._set_status("Select a valid matrix file", error=True)
            return

        if not sds_dir or not Path(sds_dir).exists():
            self._set_status("Select a valid SDS folder", error=True)
            return

        if not cas_input:
            self._set_status("Enter CAS numbers", error=True)
            return

        cas_numbers = [c.strip() for c in cas_input.split(",") if c.strip()]
        self._set_status(f"Creating experiment packet for {len(cas_numbers)} compounds…")
        self._start_task(
            self._export_packet_task,
            Path(matrix_file),
            Path(sds_dir),
            cas_numbers,
            on_result=self._on_packet_done,
        )

    def _export_packet_task(
        self,
        matrix_file: Path,
        sds_dir: Path,
        cas_numbers: list[str],
        *,
        signals: WorkerSignals | None = None,
    ) -> dict:
        """Create experiment packet zip."""
        try:
            def find_sds_files(sds_dir: Path, cas_list: list[str]) -> list[Path]:
                """Find SDS files matching CAS numbers."""
                cas_set = {c.replace("-", "").strip() for c in cas_list}
                matches: list[Path] = []
                for path in sds_dir.rglob("*.pdf"):
                    norm = path.stem.replace("-", "").upper()
                    if any(norm.startswith(cas.replace("-", "").upper()) for cas in cas_set):
                        matches.append(path)
                return matches

            sds_files = find_sds_files(sds_dir, cas_numbers)
            if not sds_files:
                if signals:
                    signals.error.emit("No matching SDS PDFs found")
                return {"success": False, "error": "No matching SDS PDFs found"}

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                packet_meta = {
                    "cas_numbers": cas_numbers,
                    "matrix_file": matrix_file.name,
                    "sds_files": [p.name for p in sds_files],
                }

                # Copy matrix
                shutil.copy2(matrix_file, tmp / matrix_file.name)

                # Copy SDS
                for pdf in sds_files:
                    shutil.copy2(pdf, tmp / pdf.name)

                # Metadata
                (tmp / "packet_meta.json").write_text(json.dumps(packet_meta, indent=2))

                # Create zip
                output_dir = Path("packets")
                output_dir.mkdir(parents=True, exist_ok=True)
                zip_path = output_dir / f"experiment_packet_{cas_numbers[0].replace('-', '')}.zip"

                with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for file_path in tmp.iterdir():
                        zf.write(file_path, arcname=file_path.name)

                if signals:
                    signals.message.emit(f"Packet created: {zip_path}")

                return {
                    "success": True,
                    "packet_path": str(zip_path),
                    "sds_count": len(sds_files),
                }
        except Exception as e:
            if signals:
                signals.error.emit(str(e))
            return {"success": False, "error": str(e)}

    def _on_packet_done(self, result: object) -> None:
        """Handle packet export completion."""
        if isinstance(result, dict) and result.get("success"):
            msg = f"Packet created: {result.get('sds_count', 0)} SDS files included"
            self._set_status(msg)
            self.automation_status.setText(msg)
        else:
            error = result.get("error") if isinstance(result, dict) else str(result)
            self._set_status(f"Packet export failed: {error}", error=True)
            self.automation_status.setText("Failed")

    def _on_generate_sds_pdf(self) -> None:
        """Handle SDS PDF generation."""
        data_file = self.gen_data_input.text().strip()
        output_pdf = self.gen_out_input.text().strip()

        if not data_file or not Path(data_file).exists():
            self._set_status("Select a valid JSON data file", error=True)
            return

        if not output_pdf:
            self._set_status("Specify output PDF path", error=True)
            return

        self._set_status(f"Generating SDS PDF…")
        self.automation_status.setText("Generating…")
        self._start_task(
            self._generate_sds_task,
            Path(data_file),
            Path(output_pdf),
            on_result=self._on_generate_done,
        )

    def _generate_sds_task(
        self,
        data_file: Path,
        output_pdf: Path,
        *,
        signals: WorkerSignals | None = None,
    ) -> dict:
        """Generate SDS PDF from JSON data."""
        try:
            from ...sds.sds_generator import SDSGenerator

            with open(data_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            generator = SDSGenerator()
            result_path = generator.generate(data, hazards=None, output_path=output_pdf)

            if signals:
                signals.message.emit(f"Generated: {result_path}")

            return {"success": True, "path": str(result_path)}
        except Exception as e:
            if signals:
                signals.error.emit(str(e))
            return {"success": False, "error": str(e)}

    def _on_generate_done(self, result: object) -> None:
        """Handle SDS generation completion."""
        if isinstance(result, dict) and result.get("success"):
            self._set_status(f"SDS PDF generated: {result.get('path')}")
            self.automation_status.setText("Generated successfully")
        else:
            error = result.get("error") if isinstance(result, dict) else str(result)
            self._set_status(f"SDS generation failed: {error}", error=True)
            self.automation_status.setText("Failed")
