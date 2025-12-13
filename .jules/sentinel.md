## 2024-05-23 - DOM-based XSS in Flask Template
**Vulnerability:** Found a DOM-based XSS in `web_ui.py` where user input (CAS number) was directly injected into `innerHTML` via a logging function.
**Learning:** Even in server-side apps (Flask), inline JavaScript logic handling user input can be vulnerable if it uses `innerHTML` without sanitization. The `render_template_string` function doesn't protect against client-side DOM manipulation.
**Prevention:** Use `textContent` instead of `innerHTML` when possible. If `innerHTML` is required for styling, always implement an HTML escaping function for user-controlled variables.
