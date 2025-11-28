"""
Chat Tab for interacting with the LLM inside the application.
"""

from __future__ import annotations

import json
import threading
from tkinter import messagebox

import customtkinter as ctk

from ...utils.preferences import load_preferences, save_preferences
from ..components import TitledFrame, TitleLabel


class ChatTab(ctk.CTkFrame):
    """LLM chat interface."""

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup chat UI."""
        self.configure(fg_color="transparent")

        TitleLabel(self, text="Chat com LLM", text_color=self.app.colors["text"])

        main_frame = ctk.CTkFrame(
            self, fg_color=self.app.colors["surface"], corner_radius=10
        )
        main_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.preferences = load_preferences()

        # System prompt
        prompt_frame = TitledFrame(
            main_frame, "Instruções (opcional)", fg_color=self.app.colors["surface"]
        )
        prompt_frame.pack(fill="x", padx=10, pady=10)

        self.system_entry = ctk.CTkEntry(
            prompt_frame,
            placeholder_text="Ex.: Responda sempre em português e seja conciso.",
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
            font=("JetBrains Mono", 11),
        )
        self.system_entry.pack(fill="x", padx=10, pady=8)

        # Preferences memory
        prefs_frame = TitledFrame(
            main_frame, "Preferências (memória)", fg_color=self.app.colors["surface"]
        )
        prefs_frame.pack(fill="x", padx=10, pady=10)

        self.prefs_box = ctk.CTkTextbox(
            prefs_frame,
            height=120,
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
            font=("JetBrains Mono", 11),
        )
        self.prefs_box.pack(fill="x", padx=10, pady=(8, 4))
        self._render_preferences()

        prefs_btn_frame = ctk.CTkFrame(prefs_frame, fg_color="transparent")
        prefs_btn_frame.pack(fill="x", padx=10, pady=(0, 6))

        ctk.CTkButton(
            prefs_btn_frame,
            corner_radius=4,
            text="Salvar preferências",
            fg_color=self.app.colors["primary"],
            text_color=self.app.colors["header"],
            font=self.app.button_font_sm,
            command=self._on_save_prefs,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            prefs_btn_frame,
            corner_radius=4,
            text="Recarregar",
            fg_color=self.app.colors["surface"],
            text_color=self.app.colors["text"],
            font=self.app.button_font_sm,
            command=self._render_preferences,
        ).pack(side="left", padx=4)

        # Chat history
        history_frame = TitledFrame(
            main_frame, "Histórico", fg_color=self.app.colors["surface"]
        )
        history_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.history_box = ctk.CTkTextbox(
            history_frame,
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
            font=("JetBrains Mono", 11),
            wrap="word",
        )
        self.history_box.pack(fill="both", expand=True, padx=10, pady=8)
        self.history_box.insert("1.0", "Inicie uma conversa com a LLM.\n")
        self.history_box.configure(state="disabled")

        # Message input + buttons
        input_frame = TitledFrame(
            main_frame, "Mensagem", fg_color=self.app.colors["surface"]
        )
        input_frame.pack(fill="x", padx=10, pady=10)

        self.message_box = ctk.CTkTextbox(
            input_frame,
            height=120,
            fg_color=self.app.colors["input"],
            text_color=self.app.colors["text"],
            font=("JetBrains Mono", 11),
        )
        self.message_box.pack(fill="x", padx=10, pady=(10, 6))
        # Key bindings: Shift+Enter nova linha, Ctrl+Enter envia
        self.message_box.bind("<Shift-Return>", lambda event: None)  # allow newline
        self.message_box.bind("<Control-Return>", self._on_ctrl_enter)

        btn_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(0, 8))

        send_btn = ctk.CTkButton(
            btn_frame,
            corner_radius=4,
            text="Enviar",
            fg_color=self.app.colors["primary"],
            text_color=self.app.colors["header"],
            font=self.app.button_font,
            command=self._on_send,
        )
        send_btn.pack(side="left", padx=5)

        clear_btn = ctk.CTkButton(
            btn_frame,
            corner_radius=4,
            text="Limpar",
            fg_color=self.app.colors["surface"],
            text_color=self.app.colors["text"],
            font=self.app.button_font_sm,
            command=self._clear_input,
        )
        clear_btn.pack(side="left", padx=5)

    # === Actions ===

    def _on_send(self) -> None:
        """Handle send button."""
        message = self.message_box.get("1.0", "end").strip()
        if not message:
            return

        system_prompt = (
            self.system_entry.get().strip()
            or "Você é um assistente e deve responder sempre em português, de forma concisa e objetiva."
        )
        # Anexar preferências salvas ao system prompt
        if self.preferences:
            prefs_json = json.dumps(self.preferences, ensure_ascii=False)
            system_prompt = f"{system_prompt}\n\nPreferências do usuário: {prefs_json}"

        # Optimistic update
        self._append_history("Você", message)
        self.message_box.delete("1.0", "end")

        thread = threading.Thread(
            target=self._send_async, args=(message, system_prompt)
        )
        thread.daemon = True
        thread.start()

    def _on_ctrl_enter(self, event=None) -> str:
        """Ctrl+Enter -> enviar; Shift+Enter já insere nova linha por padrão."""
        self._on_send()
        return "break"

    def _render_preferences(self) -> None:
        """Render preferences JSON in the textbox."""
        try:
            self.preferences = load_preferences()
            self.prefs_box.delete("1.0", "end")
            if self.preferences:
                self.prefs_box.insert(
                    "1.0", json.dumps(self.preferences, indent=2, ensure_ascii=False)
                )
            else:
                self.prefs_box.insert(
                    "1.0",
                    '{\n  "tom": "curto e direto",\n  "formato": "sempre em português" \n}',
                )
        except Exception as exc:  # pragma: no cover - UI helper
            self.prefs_box.delete("1.0", "end")
            self.prefs_box.insert("1.0", f"Erro ao carregar preferências: {exc}")

    def _on_save_prefs(self) -> None:
        """Persist edited preferences."""
        try:
            text = self.prefs_box.get("1.0", "end").strip()
            if not text:
                self.preferences = {}
                save_preferences({})
                return
            prefs = json.loads(text)
            if not isinstance(prefs, dict):
                raise ValueError("As preferências devem ser um objeto JSON.")
            save_preferences(prefs)
            self.preferences = prefs
            messagebox.showinfo(
                "Preferências salvas", "Memória de preferências atualizada."
            )
        except Exception as exc:
            messagebox.showerror("Erro ao salvar", f"Não foi possível salvar: {exc}")

    def _send_async(self, message: str, system_prompt: str) -> None:
        """Send message to LLM asynchronously."""
        try:
            reply = self.app.ollama.chat(message=message, system_prompt=system_prompt)
        except Exception as exc:
            reply = f"Erro ao conversar com a LLM: {exc}"

        self.after(0, lambda: self._append_history("LLM", reply))

    def _append_history(self, speaker: str, text: str) -> None:
        """Append a line to the history box."""
        try:
            self.history_box.configure(state="normal")
            self.history_box.insert("end", f"{speaker}: {text}\n\n")
            self.history_box.see("end")
        finally:
            self.history_box.configure(state="disabled")

    def _clear_input(self) -> None:
        """Clear the message box."""
        self.message_box.delete("1.0", "end")
