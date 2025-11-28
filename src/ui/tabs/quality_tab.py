"""
Quality Dashboard Tab for monitoring data quality metrics.
"""

from __future__ import annotations

import customtkinter as ctk
from tkinter import messagebox
from typing import Any, Dict, List

from ..components import SimpleTable, TitledFrame, TitleLabel


class QualityTab(ctk.CTkFrame):
    """
    Quality Dashboard for monitoring extraction quality and validation metrics.
    """

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup Quality Dashboard tab."""
        self.configure(fg_color="transparent")
        TitleLabel(
            self,
            text="Quality Dashboard",
            text_color=self.app.colors["text"],
        )

        # Main container with scrolling
        main_container = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
        )
        main_container.pack(fill="both", expand=True, padx=20, pady=10)

        # === Overall Metrics Section ===
        metrics_frame = TitledFrame(
            main_container,
            title="Overall Quality Metrics",
            fg_color=self.app.colors["surface"],
        )
        metrics_frame.pack(fill="x", pady=(0, 15))

        self.metrics_container = ctk.CTkFrame(
            metrics_frame,
            fg_color="transparent",
        )
        self.metrics_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Metric cards grid
        self.metric_cards = {}
        metrics = [
            ("total_docs", "Total Documents", "📄"),
            ("avg_confidence", "Avg Confidence", "🎯"),
            ("validated_count", "Validated", "✓"),
            ("excellent_count", "Excellent Quality", "🌟"),
        ]

        for idx, (key, label, icon) in enumerate(metrics):
            card = self._create_metric_card(
                self.metrics_container, icon, label, "Loading..."
            )
            card.grid(row=idx // 2, column=idx % 2, padx=5, pady=5, sticky="ew")
            self.metrics_container.columnconfigure(idx % 2, weight=1)
            self.metric_cards[key] = card

        # === Quality Distribution Section ===
        distribution_frame = TitledFrame(
            main_container,
            title="Quality Tier Distribution",
            fg_color=self.app.colors["surface"],
        )
        distribution_frame.pack(fill="x", pady=(0, 15))

        self.quality_bars = {}
        quality_tiers = [
            ("excellent", "Excellent", "🌟", "#50fa7b"),
            ("good", "Good", "✓", "#8be9fd"),
            ("acceptable", "Acceptable", "~", "#f1fa8c"),
            ("poor", "Poor", "⚠", "#ffb86c"),
            ("unreliable", "Unreliable", "✗", "#ff5555"),
        ]

        for tier, label, icon, color in quality_tiers:
            bar_frame = self._create_quality_bar(
                distribution_frame, icon, label, 0, 0, color
            )
            bar_frame.pack(fill="x", padx=10, pady=5)
            self.quality_bars[tier] = bar_frame

        # === Validation Status Section ===
        validation_frame = TitledFrame(
            main_container,
            title="External Validation Status",
            fg_color=self.app.colors["surface"],
        )
        validation_frame.pack(fill="x", pady=(0, 15))

        self.validation_label = ctk.CTkLabel(
            validation_frame,
            text="Loading validation statistics...",
            font=("JetBrains Mono", 11),
            text_color=self.app.colors["text"],
            justify="left",
        )
        self.validation_label.pack(fill="x", padx=10, pady=10)

        # === Cache Performance Section ===
        cache_frame = TitledFrame(
            main_container,
            title="PubChem Cache Performance",
            fg_color=self.app.colors["surface"],
        )
        cache_frame.pack(fill="x", pady=(0, 15))

        self.cache_label = ctk.CTkLabel(
            cache_frame,
            text="No cache data available",
            font=("JetBrains Mono", 11),
            text_color=self.app.colors["text"],
            justify="left",
        )
        self.cache_label.pack(fill="x", padx=10, pady=10)

        # === Recent Issues Section ===
        issues_frame = TitledFrame(
            main_container,
            title="Low Quality Documents",
            fg_color=self.app.colors["surface"],
        )
        issues_frame.pack(fill="both", expand=True, pady=(0, 15))

        self.issues_table = SimpleTable(
            issues_frame,
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
            header_color=self.app.colors["surface"],
            accent_color=self.app.colors["accent"],
            min_col_width=100,
        )
        self.issues_table.pack(fill="both", expand=True, padx=10, pady=10)

        # === Action Buttons ===
        button_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        button_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkButton(
            button_frame,
            text="🔄 Refresh Dashboard",
            command=self._on_refresh,
            fg_color=self.app.colors["accent"],
            text_color=self.app.colors["header"],
            font=self.app.button_font,
            corner_radius=6,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            button_frame,
            text="📊 Export Quality Report",
            command=self._on_export_report,
            fg_color=self.app.colors.get("secondary", self.app.colors["surface"]),
            text_color=self.app.colors["text"],
            font=self.app.button_font,
            corner_radius=6,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            button_frame,
            text="🗑️ Clear Cache",
            command=self._on_clear_cache,
            fg_color=self.app.colors.get("warning", "#ffb86c"),
            text_color=self.app.colors["header"],
            font=self.app.button_font,
            corner_radius=6,
        ).pack(side="left", padx=5)

        # Initial load
        self.after(100, self._on_refresh)

    def _create_metric_card(
        self, parent, icon: str, label: str, value: str
    ) -> ctk.CTkFrame:
        """Create a metric display card."""
        card = ctk.CTkFrame(
            parent,
            fg_color=self.app.colors["input"],
            corner_radius=8,
        )

        # Icon
        icon_label = ctk.CTkLabel(
            card,
            text=icon,
            font=("Arial", 32),
        )
        icon_label.pack(pady=(10, 5))

        # Value
        value_label = ctk.CTkLabel(
            card,
            text=value,
            font=("JetBrains Mono", 20, "bold"),
            text_color=self.app.colors["accent"],
        )
        value_label.pack()

        # Label
        label_label = ctk.CTkLabel(
            card,
            text=label,
            font=("JetBrains Mono", 10),
            text_color=self.app.colors["text"],
        )
        label_label.pack(pady=(0, 10))

        # Store references for updates
        card.value_label = value_label
        card.label_label = label_label

        return card

    def _create_quality_bar(
        self,
        parent,
        icon: str,
        label: str,
        count: int,
        total: int,
        color: str,
    ) -> ctk.CTkFrame:
        """Create a horizontal quality bar."""
        container = ctk.CTkFrame(parent, fg_color="transparent")

        # Label with icon
        label_frame = ctk.CTkFrame(container, fg_color="transparent")
        label_frame.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            label_frame,
            text=f"{icon} {label}",
            font=("JetBrains Mono", 11),
            text_color=self.app.colors["text"],
            width=150,
            anchor="w",
        ).pack(side="left")

        # Progress bar
        bar_container = ctk.CTkFrame(
            container,
            fg_color=self.app.colors["input"],
            height=24,
            corner_radius=4,
        )
        bar_container.pack(side="left", fill="x", expand=True, padx=(0, 10))

        progress = ctk.CTkProgressBar(
            bar_container,
            width=200,
            height=20,
            progress_color=color,
            fg_color=self.app.colors["bg"],
        )
        progress.pack(fill="both", expand=True, padx=2, pady=2)
        progress.set(0)

        # Count label
        count_label = ctk.CTkLabel(
            container,
            text="0 / 0 (0.0%)",
            font=("JetBrains Mono", 11),
            text_color=self.app.colors["text"],
            width=120,
        )
        count_label.pack(side="left")

        # Store references
        container.progress = progress
        container.count_label = count_label

        return container

    def _on_refresh(self) -> None:
        """Refresh all dashboard data."""
        import threading

        thread = threading.Thread(target=self._load_data_async, daemon=True)
        thread.start()

    def _load_data_async(self) -> None:
        """Load dashboard data asynchronously."""
        try:
            # Get database results
            results = self.app.db.fetch_results(limit=1000)

            # Calculate metrics
            total = len(results)
            validated = sum(1 for r in results if r.get("validated"))

            confidences = [
                r.get("avg_confidence", 0)
                for r in results
                if r.get("avg_confidence") is not None
            ]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

            # Quality tier distribution
            quality_dist = {
                "excellent": 0,
                "good": 0,
                "acceptable": 0,
                "poor": 0,
                "unreliable": 0,
            }
            for r in results:
                tier = r.get("quality_tier", "").lower()
                if tier in quality_dist:
                    quality_dist[tier] += 1

            # Low quality documents
            low_quality = [
                r
                for r in results
                if r.get("quality_tier", "").lower() in ("poor", "unreliable")
            ]

            # Get cache stats
            try:
                from ...sds.processor import SDSProcessor
                processor = SDSProcessor()
                cache_stats = processor.external_validator.get_cache_stats()
            except Exception:
                cache_stats = None

            # Update UI
            self.after(0, lambda: self._update_ui(
                total, avg_conf, validated, quality_dist, low_quality, cache_stats
            ))

        except Exception as e:
            self.app.logger.error(f"Failed to load quality dashboard: {e}")
            self.after(
                0,
                lambda err=str(e): messagebox.showerror(
                    "Dashboard Error", f"Failed to load data: {err}"
                ),
            )

    def _update_ui(
        self,
        total: int,
        avg_conf: float,
        validated: int,
        quality_dist: Dict[str, int],
        low_quality: List[Dict[str, Any]],
        cache_stats: Dict[str, Any] | None,
    ) -> None:
        """Update UI with loaded data."""
        # Update metric cards
        self.metric_cards["total_docs"].value_label.configure(text=str(total))
        self.metric_cards["avg_confidence"].value_label.configure(
            text=f"{avg_conf*100:.1f}%"
        )
        self.metric_cards["validated_count"].value_label.configure(
            text=f"{validated}/{total}"
        )
        self.metric_cards["excellent_count"].value_label.configure(
            text=str(quality_dist["excellent"])
        )

        # Update quality bars
        for tier, count in quality_dist.items():
            if tier in self.quality_bars:
                bar = self.quality_bars[tier]
                percentage = (count / total * 100) if total > 0 else 0
                progress_val = count / total if total > 0 else 0

                bar.progress.set(progress_val)
                bar.count_label.configure(
                    text=f"{count} / {total} ({percentage:.1f}%)"
                )

        # Update validation status
        val_rate = (validated / total * 100) if total > 0 else 0
        validation_text = (
            f"Validated Documents: {validated} / {total} ({val_rate:.1f}%)\n"
            f"Unvalidated: {total - validated}\n\n"
            "External validation via PubChem API provides confidence boosts\n"
            "for chemical names, CAS numbers, and formulas."
        )
        self.validation_label.configure(text=validation_text)

        # Update cache stats
        if cache_stats:
            cache_text = (
                f"Cache Size: {cache_stats['size']} / {cache_stats['max_size']} entries\n"
                f"Hits: {cache_stats['hits']} | Misses: {cache_stats['misses']}\n"
                f"Hit Rate: {cache_stats['hit_rate']:.1f}%\n"
                f"Evictions: {cache_stats['evictions']}\n"
                f"TTL: {cache_stats['ttl_seconds']}s"
            )
        else:
            cache_text = "Cache statistics not available (no processor running)"
        self.cache_label.configure(text=cache_text)

        # Update low quality table
        if low_quality:
            headers = ["Filename", "Quality", "Confidence", "Validated"]
            rows = [
                (
                    r.get("filename", "")[:40],
                    r.get("quality_tier", "unknown"),
                    f"{r.get('avg_confidence', 0)*100:.1f}%",
                    "✓" if r.get("validated") else "✗",
                )
                for r in low_quality[:20]  # Limit to 20
            ]
            self.issues_table.set_data(
                headers, rows, accent_color=self.app.colors["accent"]
            )
        else:
            self.issues_table.set_data(
                ["Status"],
                [("No low quality documents found! 🎉",)],
            )

    def _on_export_report(self) -> None:
        """Export quality report to file."""
        from tkinter import filedialog
        import json
        from datetime import datetime

        filepath = filedialog.asksaveasfilename(
            title="Export Quality Report",
            defaultextension=".json",
            filetypes=[
                ("JSON files", "*.json"),
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ],
        )

        if not filepath:
            return

        try:
            results = self.app.db.fetch_results(limit=1000)

            report = {
                "generated_at": datetime.now().isoformat(),
                "total_documents": len(results),
                "quality_distribution": {},
                "validation_stats": {},
                "low_quality_documents": [],
            }

            # Calculate distributions
            for tier in ["excellent", "good", "acceptable", "poor", "unreliable"]:
                count = sum(1 for r in results if r.get("quality_tier", "").lower() == tier)
                report["quality_distribution"][tier] = count

            validated = sum(1 for r in results if r.get("validated"))
            report["validation_stats"] = {
                "validated": validated,
                "unvalidated": len(results) - validated,
                "validation_rate": (validated / len(results) * 100) if results else 0,
            }

            # Low quality docs
            low_quality = [
                {
                    "filename": r.get("filename"),
                    "quality_tier": r.get("quality_tier"),
                    "confidence": r.get("avg_confidence"),
                    "validated": bool(r.get("validated")),
                }
                for r in results
                if r.get("quality_tier", "").lower() in ("poor", "unreliable")
            ]
            report["low_quality_documents"] = low_quality

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            messagebox.showinfo("Export Success", f"Quality report saved to:\n{filepath}")

        except Exception as e:
            self.app.logger.error(f"Failed to export report: {e}")
            messagebox.showerror("Export Error", f"Failed to export report: {e}")

    def _on_clear_cache(self) -> None:
        """Clear the PubChem cache."""
        if not messagebox.askyesno(
            "Clear Cache",
            "Are you sure you want to clear the PubChem cache?\n\n"
            "This will remove all cached API responses.",
        ):
            return

        try:
            from ...sds.processor import SDSProcessor
            processor = SDSProcessor()
            processor.external_validator.clear_cache()
            messagebox.showinfo("Cache Cleared", "PubChem cache has been cleared successfully.")
            self._on_refresh()
        except Exception as e:
            self.app.logger.error(f"Failed to clear cache: {e}")
            messagebox.showerror("Clear Error", f"Failed to clear cache: {e}")
