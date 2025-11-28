"""Internationalization (i18n) support for bilingual UI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# Translation dictionary
TRANSLATIONS: Final[dict[str, dict[str, str]]] = {
    # === Application ===
    "app.title": {
        "pt": "RAG SDS Matrix",
        "en": "RAG SDS Matrix",
    },
    "app.version": {
        "pt": "Versão",
        "en": "Version",
    },
    "app.ready": {
        "pt": "Pronto",
        "en": "Ready",
    },
    # === Tabs ===
    "tab.rag": {
        "pt": "Base de Conhecimento",
        "en": "Knowledge Base",
    },
    "tab.sources": {
        "pt": "Fontes",
        "en": "Sources",
    },
    "tab.sds": {
        "pt": "Processador SDS",
        "en": "SDS Processor",
    },
    # === RAG Tab ===
    "rag.title": {
        "pt": "Gerenciador de Conhecimento RAG",
        "en": "RAG Knowledge Manager",
    },
    "rag.add_docs": {
        "pt": "Adicionar Documentos",
        "en": "Add Documents",
    },
    "rag.add_url": {
        "pt": "Adicionar URL",
        "en": "Add URL",
    },
    "rag.indexed_docs": {
        "pt": "Documentos Indexados",
        "en": "Indexed Documents",
    },
    "rag.search": {
        "pt": "Buscar na Base",
        "en": "Search Knowledge Base",
    },
    "rag.clear": {
        "pt": "Limpar Base",
        "en": "Clear Database",
    },
    "rag.status.indexing": {
        "pt": "Indexando documentos...",
        "en": "Indexing documents...",
    },
    "rag.status.ready": {
        "pt": "Base de conhecimento pronta",
        "en": "Knowledge base ready",
    },
    # === SDS Tab ===
    "sds.title": {
        "pt": "Processador de Fichas de Segurança",
        "en": "Safety Data Sheet Processor",
    },
    "sds.select_folder": {
        "pt": "Selecionar Pasta",
        "en": "Select Folder",
    },
    "sds.add_files": {
        "pt": "Adicionar Arquivos",
        "en": "Add Files",
    },
    "sds.process": {
        "pt": "Processar",
        "en": "Process",
    },
    "sds.process_all": {
        "pt": "Processar Todos",
        "en": "Process All",
    },
    "sds.export_csv": {
        "pt": "Exportar CSV",
        "en": "Export CSV",
    },
    "sds.export_excel": {
        "pt": "Exportar Excel",
        "en": "Export Excel",
    },
    "sds.clear_queue": {
        "pt": "Limpar Fila",
        "en": "Clear Queue",
    },
    "sources.title": {
        "pt": "Fontes de Conhecimento",
        "en": "Knowledge Sources",
    },
    "sources.local": {
        "pt": "Arquivos Locais",
        "en": "Local Files",
    },
    "sources.web": {
        "pt": "Fontes Online",
        "en": "Online Sources",
    },
    "sources.recent": {
        "pt": "Fontes Recentes",
        "en": "Recent Sources",
    },
    "sources.brightdata": {
        "pt": "Bright Data (raspagem automática)",
        "en": "Bright Data (automated crawl)",
    },
    # === Table Headers ===
    "table.file": {
        "pt": "Arquivo",
        "en": "File",
    },
    "table.status": {
        "pt": "Status",
        "en": "Status",
    },
    "table.product": {
        "pt": "Produto",
        "en": "Product",
    },
    "table.manufacturer": {
        "pt": "Fabricante",
        "en": "Manufacturer",
    },
    "table.cas": {
        "pt": "CAS",
        "en": "CAS",
    },
    "table.un": {
        "pt": "ONU",
        "en": "UN",
    },
    "table.class": {
        "pt": "Classe",
        "en": "Class",
    },
    "table.packing_group": {
        "pt": "Grupo Emb.",
        "en": "Pack. Group",
    },
    "table.incompatibilities": {
        "pt": "Incompatibilidades",
        "en": "Incompatibilities",
    },
    "table.confidence": {
        "pt": "Confiança",
        "en": "Confidence",
    },
    # === Status Messages ===
    "status.pending": {
        "pt": "Pendente",
        "en": "Pending",
    },
    "status.processing": {
        "pt": "Processando",
        "en": "Processing",
    },
    "status.completed": {
        "pt": "Concluído",
        "en": "Completed",
    },
    "status.failed": {
        "pt": "Falhou",
        "en": "Failed",
    },
    "status.enriching": {
        "pt": "Enriquecendo via RAG",
        "en": "Enriching via RAG",
    },
    # === Buttons ===
    "btn.cancel": {
        "pt": "Cancelar",
        "en": "Cancel",
    },
    "btn.close": {
        "pt": "Fechar",
        "en": "Close",
    },
    "btn.save": {
        "pt": "Salvar",
        "en": "Save",
    },
    "btn.refresh": {
        "pt": "Atualizar",
        "en": "Refresh",
    },
    "btn.settings": {
        "pt": "Configurações",
        "en": "Settings",
    },
    # === Dialogs ===
    "dialog.error": {
        "pt": "Erro",
        "en": "Error",
    },
    "dialog.warning": {
        "pt": "Aviso",
        "en": "Warning",
    },
    "dialog.info": {
        "pt": "Informação",
        "en": "Information",
    },
    "dialog.confirm": {
        "pt": "Confirmar",
        "en": "Confirm",
    },
    "dialog.success": {
        "pt": "Sucesso",
        "en": "Success",
    },
    # === Progress ===
    "progress.processing": {
        "pt": "Processando {current} de {total}...",
        "en": "Processing {current} of {total}...",
    },
    "progress.extracting": {
        "pt": "Extraindo texto...",
        "en": "Extracting text...",
    },
    "progress.analyzing": {
        "pt": "Analisando com IA...",
        "en": "Analyzing with AI...",
    },
    "progress.enriching": {
        "pt": "Enriquecendo dados...",
        "en": "Enriching data...",
    },
    # === Errors ===
    "error.no_files": {
        "pt": "Nenhum arquivo selecionado",
        "en": "No files selected",
    },
    "error.file_too_large": {
        "pt": "Arquivo muito grande (max: {max_mb}MB)",
        "en": "File too large (max: {max_mb}MB)",
    },
    "error.unsupported_format": {
        "pt": "Formato não suportado: {format}",
        "en": "Unsupported format: {format}",
    },
    "error.ollama_connection": {
        "pt": "Não foi possível conectar ao Ollama",
        "en": "Could not connect to Ollama",
    },
    "error.extraction_failed": {
        "pt": "Falha na extração: {error}",
        "en": "Extraction failed: {error}",
    },
    # === Settings ===
    "settings.title": {
        "pt": "Configurações",
        "en": "Settings",
    },
    "settings.language": {
        "pt": "Idioma",
        "en": "Language",
    },
    "settings.theme": {
        "pt": "Tema",
        "en": "Theme",
    },
    "settings.ollama_url": {
        "pt": "URL do Ollama",
        "en": "Ollama URL",
    },
    "settings.models": {
        "pt": "Modelos",
        "en": "Models",
    },
    # === Tooltips ===
    "tooltip.process": {
        "pt": "Processar arquivos selecionados",
        "en": "Process selected files",
    },
    "tooltip.export": {
        "pt": "Exportar resultados",
        "en": "Export results",
    },
    "tooltip.rag_enrich": {
        "pt": "Usar base de conhecimento para completar dados",
        "en": "Use knowledge base to complete data",
    },
}


@dataclass
class I18n:
    """Internationalization handler."""

    language: str = "pt"

    def get(self, key: str, **kwargs: str) -> str:
        """Get translated string for key.

        Args:
            key: Translation key (e.g., "app.title")
            **kwargs: Format arguments for string interpolation

        Returns:
            Translated string, or key if not found
        """
        translations = TRANSLATIONS.get(key, {})
        text = translations.get(self.language, translations.get("en", key))

        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError:
                pass

        return text

    def set_language(self, language: str) -> None:
        """Set current language."""
        if language in ("pt", "en"):
            self.language = language


# Global i18n instance
_i18n: I18n | None = None


def get_i18n() -> I18n:
    """Get global i18n instance."""
    global _i18n
    if _i18n is None:
        from .settings import get_settings

        settings = get_settings()
        _i18n = I18n(language=settings.ui.language)
    return _i18n


def get_text(key: str, **kwargs: str) -> str:
    """Convenience function to get translated text."""
    return get_i18n().get(key, **kwargs)


def set_language(language: str) -> None:
    """Set global language."""
    get_i18n().set_language(language)
