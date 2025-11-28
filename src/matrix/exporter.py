"""Export matrices and results to various formats."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ..config.settings import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class MatrixExporter:
    """Export matrices to CSV, Excel, PDF, and JSON formats."""

    def __init__(self) -> None:
        """Initialize exporter."""
        self.settings = get_settings()
        from ..database import get_db_manager

        self.db = get_db_manager()

    def export_to_csv(
        self,
        dataframe: pd.DataFrame,
        output_path: Path | str,
        index: bool = True,
    ) -> bool:
        """Export matrix to CSV format.

        Args:
            dataframe: DataFrame to export
            output_path: Output file path
            index: Whether to include index

        Returns:
            True if successful
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            dataframe.to_csv(output_path, index=index, encoding="utf-8")

            logger.info("Exported matrix to CSV: %s", output_path)
            return True

        except Exception as e:
            logger.error("CSV export failed: %s", e)
            return False

    def export_to_excel(
        self,
        dataframes: dict[str, pd.DataFrame] | pd.DataFrame,
        output_path: Path | str,
        include_summary: bool = True,
    ) -> bool:
        """Export matrix to Excel format with multiple sheets.

        Args:
            dataframes: DataFrame or dict of sheet_name -> DataFrame
            output_path: Output file path
            include_summary: Whether to add summary sheet

        Returns:
            True if successful
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Normalize to dict
            if isinstance(dataframes, pd.DataFrame):
                sheets = {"Matriz": dataframes}
            else:
                sheets = dataframes

            with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                for sheet_name, df in sheets.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=True)

                # Add summary sheet if requested
                if include_summary:
                    summary_df = pd.DataFrame(
                        {
                            "Data de Exportacao": [
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            ],
                            "Total de Abas": [len(sheets)],
                            "Formato": ["Excel (.xlsx)"],
                        }
                    )
                    summary_df.to_excel(
                        writer,
                        sheet_name="Resumo",
                        index=False,
                    )

            logger.info("Exported matrices to Excel: %s", output_path)
            return True

        except Exception as e:
            logger.error("Excel export failed: %s", e)
            return False

    def export_to_json(
        self,
        data: dict[str, Any] | list[dict[str, Any]],
        output_path: Path | str,
        pretty: bool = True,
    ) -> bool:
        """Export data to JSON format.

        Args:
            data: Data to export
            output_path: Output file path
            pretty: Whether to pretty-print JSON

        Returns:
            True if successful
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                if pretty:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                else:
                    json.dump(data, f, ensure_ascii=False)

            logger.info("Exported data to JSON: %s", output_path)
            return True

        except Exception as e:
            logger.error("JSON export failed: %s", e)
            return False

    def export_to_pdf(
        self,
        dataframe: pd.DataFrame,
        output_path: Path | str,
        title: str | None = None,
    ) -> bool:
        """Export matrix to PDF format.

        Args:
            dataframe: DataFrame to export
            output_path: Output file path
            title: Optional PDF title

        Returns:
            True if successful
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Check for required dependencies
            try:
                from reportlab.lib import colors, pagesizes
                from reportlab.lib.styles import getSampleStyleSheet
                from reportlab.lib.units import inch
                from reportlab.platypus import (
                    Paragraph,
                    SimpleDocTemplate,
                    Table,
                    TableStyle,
                )
            except ImportError:
                logger.warning(
                    "reportlab not installed, falling back to simple PDF export"
                )
                return self._export_to_pdf_simple(dataframe, output_path, title)

            # Create PDF document
            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=pagesizes.landscape(pagesizes.A4),
                topMargin=0.5 * inch,
                bottomMargin=0.5 * inch,
                leftMargin=0.5 * inch,
                rightMargin=0.5 * inch,
            )

            elements = []
            styles = getSampleStyleSheet()

            # Add title if provided
            if title:
                title_paragraph = Paragraph(title, styles["Heading1"])
                elements.append(title_paragraph)

            # Convert DataFrame to table
            table_data = [dataframe.columns.tolist()] + dataframe.values.tolist()

            table = Table(table_data, repeatRows=1)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )

            elements.append(table)
            doc.build(elements)

            logger.info("Exported matrix to PDF: %s", output_path)
            return True

        except Exception as e:
            logger.error("PDF export failed: %s", e)
            return False

    def export_decisions_long(self) -> pd.DataFrame:
        """Export matrix decisions with justification/fonte."""
        try:
            with self.db._lock:
                rows = self.db.conn.execute(
                    """
                    SELECT product_a, product_b, cas_a, cas_b, decision,
                           source_layer, rule_source, justification, decided_at
                    FROM matrix_decisions
                    ORDER BY decided_at DESC;
                    """
                ).fetchall()

            columns = [
                "product_a",
                "product_b",
                "cas_a",
                "cas_b",
                "decision",
                "source_layer",
                "rule_source",
                "justification",
                "decided_at",
            ]
            return pd.DataFrame(rows, columns=columns)
        except Exception as exc:
            logger.error("Failed to export matrix decisions: %s", exc)
            return pd.DataFrame()

    def _export_to_pdf_simple(
        self,
        dataframe: pd.DataFrame,
        output_path: Path | str,
        title: str | None = None,
    ) -> bool:
        """Simple PDF export as fallback (using matplotlib).

        Args:
            dataframe: DataFrame to export
            output_path: Output file path
            title: Optional title

        Returns:
            True if successful
        """
        try:
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(14, 10))
            ax.axis("tight")
            ax.axis("off")

            table = ax.table(
                cellText=dataframe.values,
                colLabels=dataframe.columns,
                cellLoc="center",
                loc="center",
            )

            table.auto_set_font_size(False)
            table.set_fontsize(8)
            table.scale(1, 1.5)

            if title:
                plt.title(title, pad=20, fontsize=14, fontweight="bold")

            plt.savefig(output_path, dpi=150, bbox_inches="tight")
            plt.close()

            logger.info("Exported matrix to PDF (matplotlib): %s", output_path)
            return True

        except Exception as e:
            logger.error("Simple PDF export failed: %s", e)
            return False

    def export_report(
        self,
        matrices: dict[str, pd.DataFrame],
        statistics: dict[str, Any],
        output_dir: Path | str,
        format_type: str = "all",
    ) -> dict[str, bool]:
        """Export comprehensive report in multiple formats.

        Args:
            matrices: Dictionary of matrix_name -> DataFrame
            statistics: Statistics dictionary
            output_dir: Output directory
            format_type: Format(s) to export ('csv', 'excel', 'json', 'all')

        Returns:
            Dictionary of format -> success status
        """
        try:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            results = {}
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Export matrices
            if format_type in ("csv", "all"):
                for name, df in matrices.items():
                    csv_path = output_dir / f"{name}_{timestamp}.csv"
                    results[f"{name}_csv"] = self.export_to_csv(df, csv_path)

            if format_type in ("excel", "all"):
                excel_path = output_dir / f"matrizes_{timestamp}.xlsx"
                results["excel"] = self.export_to_excel(matrices, excel_path)

            if format_type in ("json", "all"):
                json_path = output_dir / f"estatisticas_{timestamp}.json"
                results["json"] = self.export_to_json(statistics, json_path)

            logger.info(
                "Report exported to %s with formats: %s",
                output_dir,
                format_type,
            )

            return results

        except Exception as e:
            logger.error("Report export failed: %s", e)
            return {}

    def export_dangerous_chemicals_report(
        self,
        chemicals: list[dict[str, Any]],
        output_path: Path | str,
    ) -> bool:
        """Export dangerous chemicals as CSV/Excel report.

        Args:
            chemicals: List of dangerous chemical records
            output_path: Output file path

        Returns:
            True if successful
        """
        try:
            df = pd.DataFrame(chemicals)

            # Select key columns
            cols_to_export = [
                "product_name",
                "manufacturer",
                "hazard_class",
                "un_number",
                "cas_number",
                "incompatibilities",
                "processing_time",
            ]

            # Only include columns that exist
            available_cols = [c for c in cols_to_export if c in df.columns]
            df = df[available_cols]

            rename_map = {
                "product_name": "Produto",
                "manufacturer": "Fabricante",
                "hazard_class": "Classe de Perigo",
                "un_number": "Numero ONU",
                "cas_number": "Numero CAS",
                "incompatibilities": "Incompatibilidades",
                "processing_time": "Tempo de Processamento (s)",
            }
            df = df.rename(
                columns={k: v for k, v in rename_map.items() if k in df.columns}
            )

            output_path = Path(output_path)

            if output_path.suffix.lower() == ".csv":
                return self.export_to_csv(df, output_path)
            elif output_path.suffix.lower() in (".xlsx", ".xls"):
                return self.export_to_excel(df, output_path)
            else:
                logger.error("Unsupported format: %s", output_path.suffix)
                return False

        except Exception as e:
            logger.error("Dangerous chemicals report export failed: %s", e)
            return False
