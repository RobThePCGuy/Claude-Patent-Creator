"""Optional desktop GUI for editing settings (``patent-creator config --gui``).

A thin Tkinter form generated from the :data:`mcp_server.config.OPTIONS` schema,
so the list of options never drifts from the single source of truth. All
validation and persistence are delegated to :mod:`mcp_server.config`; this module
only builds widgets. Tkinter is imported lazily inside :func:`launch` so importing
this module never requires a display.
"""

import sys

# Work both as a package module (tests: mcp_server.config_gui) and as a bare
# module under the CLI's sys.path setup (cli.py: from config_gui import launch).
try:
    from . import config as _config
except ImportError:  # pragma: no cover - exercised only via the CLI entry point
    import config as _config


_DEFAULT_LABEL = "(default)"


def _choice_display(value: str) -> str:
    return _DEFAULT_LABEL if value == "" else value


def _choice_value(display: str) -> str:
    return "" if display == _DEFAULT_LABEL else display


def _plan_save(entries):
    """Decide what the GUI's Save should persist.

    ``entries`` is an iterable of ``(option, current_value, original_value)``.
    Only fields the user actually changed are persisted (so opening the window
    never copies an env-sourced secret or a built-in default onto disk), and each
    changed value is validated. Returns ``(to_save, errors)``.
    """
    to_save: dict = {}
    errors: list = []
    for opt, current, original in entries:
        if current == original:
            continue
        error = _config.validate(opt.key, current)
        if error:
            errors.append(f"{opt.label}: {error}")
            continue
        to_save[opt.key] = _config.normalize(opt.key, current)
    return to_save, errors


def launch() -> int:
    """Open the settings window. Returns a process exit code."""
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except Exception as exc:  # tkinter missing or no display
        print(
            "[X] The settings GUI is unavailable (Tkinter not installed or no display).",
            file=sys.stderr,
        )
        print(f"    {exc}", file=sys.stderr)
        print(
            "    Use the command line instead, e.g.:\n"
            "      patent-creator config set GOOGLE_CLOUD_PROJECT my-project-id",
            file=sys.stderr,
        )
        return 1

    root = tk.Tk()
    root.title("Claude Patent Creator - Settings")
    root.minsize(560, 480)

    # Scrollable body so the form never overflows small screens.
    outer = ttk.Frame(root)
    outer.pack(fill="both", expand=True)
    canvas = tk.Canvas(outer, highlightthickness=0)
    scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    body = ttk.Frame(canvas)
    body.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=body, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    header = ttk.Label(
        body,
        text=f"Config file: {_config.config_path()}\n"
        "Priority: environment variable > this file > default",
        justify="left",
    )
    header.grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 8))

    widgets: dict = {}  # key -> (option, tk variable)
    grid_row = 1
    sections: dict = {}
    for opt in _config.OPTIONS:
        sections.setdefault(opt.section, []).append(opt)

    for section, opts in sections.items():
        frame = ttk.LabelFrame(body, text=section)
        frame.grid(row=grid_row, column=0, columnspan=2, sticky="ew", padx=12, pady=6)
        frame.columnconfigure(1, weight=1)
        grid_row += 1

        for inner_row, opt in enumerate(opts):
            value, source = _config.get_effective(opt.key)
            ttk.Label(frame, text=opt.label).grid(
                row=inner_row * 2, column=0, sticky="nw", padx=8, pady=(8, 0)
            )

            if opt.type == "bool":
                original = "true" if value.lower() == "true" else "false"
                var = tk.BooleanVar(value=value.lower() == "true")
                ttk.Checkbutton(frame, variable=var).grid(
                    row=inner_row * 2, column=1, sticky="w", padx=8, pady=(8, 0)
                )
            elif opt.type == "choice":
                original = value
                var = tk.StringVar(value=_choice_display(value))
                ttk.Combobox(
                    frame,
                    textvariable=var,
                    values=[_choice_display(c) for c in opt.choices],
                    state="readonly",
                ).grid(row=inner_row * 2, column=1, sticky="ew", padx=8, pady=(8, 0))
            else:
                original = value
                var = tk.StringVar(value=value)
                ttk.Entry(
                    frame,
                    textvariable=var,
                    show="•" if opt.is_secret else "",
                ).grid(row=inner_row * 2, column=1, sticky="ew", padx=8, pady=(8, 0))

            desc = opt.description + (f"  ({opt.note})" if opt.note else "")
            ttk.Label(
                frame, text=f"{desc}   [source: {source}]", foreground="#666", wraplength=460
            ).grid(row=inner_row * 2 + 1, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 4))

            # Keep the pre-filled value so Save only persists fields the user
            # actually changed — never copying env-sourced secrets or defaults
            # onto disk just because the window was opened.
            widgets[opt.key] = (opt, var, original)

    def on_save():
        entries = []
        for _key, (opt, var, original) in widgets.items():
            raw = var.get()
            if isinstance(raw, bool):
                raw = "true" if raw else "false"
            raw = _choice_value(str(raw)) if opt.type == "choice" else str(raw)
            entries.append((opt, raw, original))
        to_save, errors = _plan_save(entries)
        if errors:
            messagebox.showerror("Invalid settings", "\n".join(errors))
            return
        if to_save:
            _config.save_values(to_save)
        messagebox.showinfo(
            "Saved", f"Saved {len(to_save)} change(s) to\n{_config.config_path()}"
        )

    buttons = ttk.Frame(root)
    buttons.pack(fill="x", padx=12, pady=10)
    ttk.Button(buttons, text="Save", command=on_save).pack(side="right")
    ttk.Button(buttons, text="Close", command=root.destroy).pack(side="right", padx=(0, 8))

    root.mainloop()
    return 0
