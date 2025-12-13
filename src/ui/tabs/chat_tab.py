"""Chat tab for RAG-powered question answering.

Provides an interface for querying the knowledge base using natural language
with RAG (Retrieval-Augmented Generation) and LLM responses.
"""

from __future__ import annotations

from PySide6 import QtWidgets

from . import BaseTab, TabContext
from ..components import TaskRunner, WorkerSignals


class ChatTab(BaseTab):
    """Tab for chatting with the RAG-powered LLM system."""

    def __init__(self, context: TabContext) -> None:
        super().__init__(context)
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the chat tab UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # Title
        title = QtWidgets.QLabel("Chat with RAG System")
        self._style_label(title, bold=True)
        title.setStyleSheet(title.styleSheet() + f"; font-size: 14px;")
        layout.addWidget(title)

        # Info
        info = QtWidgets.QLabel(
            "Ask questions about your knowledge base. The system uses RAG to retrieve "
            "relevant documents and Ollama to generate responses."
        )
        self._style_label(info, color=self.colors.get("subtext", "#888888"))
        info.setWordWrap(True)
        layout.addWidget(info)

        # Chat display
        self.chat_display = QtWidgets.QTextEdit()
        self.chat_display.setReadOnly(True)
        self._style_textedit(self.chat_display)
        layout.addWidget(self.chat_display)

        # Input row
        input_row = QtWidgets.QHBoxLayout()
        self.chat_input = QtWidgets.QLineEdit()
        self.chat_input.setPlaceholderText("Ask a question about your knowledge base...")
        self.chat_input.returnPressed.connect(self._on_chat_send)  # Allow Enter to send
        self.chat_input.setStyleSheet(
            f"QLineEdit {{"
            f"background-color: {self.colors['input']};"
            f"color: {self.colors['text']};"
            f"border: 1px solid {self.colors['overlay']};"
            f"border-radius: 4px;"
            f"padding: 8px;"
            f"font-size: 11px;"
            f"}}"
        )
        self.chat_input.setMinimumHeight(36)
        input_row.addWidget(self.chat_input)

        send_btn = QtWidgets.QPushButton("📤 Send")
        self._style_button(send_btn)
        send_btn.clicked.connect(self._on_chat_send)
        send_btn.setMinimumHeight(36)
        input_row.addWidget(send_btn)

        layout.addLayout(input_row)

        # Status indicator
        self.chat_status = QtWidgets.QLabel("Ready")
        self._style_label(self.chat_status, color=self.colors.get("subtext", "#888888"))
        self.chat_status.setStyleSheet(self.chat_status.styleSheet() + "; font-size: 10px;")
        layout.addWidget(self.chat_status)

    def _on_chat_send(self) -> None:
        """Handle chat message sending with RAG context."""
        text = self.chat_input.text().strip()
        if not text:
            return

        # Add user message to display
        self.chat_display.append(f"<b>You:</b> {text}")
        self.chat_input.clear()
        self.chat_input.setEnabled(False)

        # Show thinking status
        self.chat_status.setText("🤔 Thinking...")
        self._style_label(self.chat_status, color=self.colors.get("accent", "#4fd1c5"))

        # Run in background thread
        self._start_task(self._chat_task, text, on_result=self._on_chat_response, on_progress=None)

    def _chat_task(self, text: str, *, signals: WorkerSignals | None = None) -> object:
        """Execute chat task in background."""
        try:
            # Get RAG context from vector store
            vector_store = self.context.ingestion.vector_store
            results = vector_store.search_with_context(text, k=3)

            context = ""
            if results:
                context = results  # search_with_context returns a formatted string
                if signals and context:
                    signals.message.emit("Found relevant documents for context")
            else:
                if signals:
                    signals.message.emit("No relevant documents found in knowledge base")

            # Get Ollama response with context
            response = self.context.ollama.chat(message=text, context=context)
            return response
        except Exception as e:
            if signals:
                signals.error.emit(str(e))
            return None

    def _on_chat_response(self, response: object) -> None:
        """Handle chat response from Ollama."""
        self.chat_input.setEnabled(True)

        if response:
            # Format the response nicely
            response_text = str(response).strip()
            self.chat_display.append(f"<b>Assistant:</b> {response_text}")
            self.chat_status.setText("✓ Response received")
            self._style_label(self.chat_status, color=self.colors.get("success", "#22c55e"))
            self._set_status("Chat response received")
        else:
            self.chat_display.append("<i style='color: #f87171;'>Error: Could not generate response</i>")
            self.chat_status.setText("✗ Failed to generate response")
            self._style_label(self.chat_status, color=self.colors.get("error", "#f87171"))
            self._set_status("Chat failed", error=True)
