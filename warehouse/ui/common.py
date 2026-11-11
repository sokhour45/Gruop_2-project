"""Shared widgets and modal-form behavior."""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Generator, Sequence

from warehouse.validation import FieldError, validation_gate


class Screen(ttk.Frame):
    def __init__(self, parent: tk.Misc, app: "WarehouseApp"):
        super().__init__(parent, padding=(28, 24, 28, 28))
        self.app = app

    def refresh(self) -> None:
        pass

    def make_tree(
        self, parent: tk.Misc, columns: Sequence[tuple[str, str, int]]
    ) -> ttk.Treeview:
        names = [column[0] for column in columns]
        tree = ttk.Treeview(parent, columns=names, show="headings", selectmode="browse")
        for key, title, width in columns:
            tree.heading(key, text=title, command=lambda col=key, widget=tree: self.sort_tree(widget, col))
            tree.column(key, width=width, anchor="w")
        tree.tag_configure("low_stock", background="#fff1f2", foreground="#991b1b")
        return tree

    @staticmethod
    def sort_tree(tree: ttk.Treeview, column: str) -> None:
        rows = [(tree.set(item, column), item) for item in tree.get_children("")]
        try:
            rows.sort(key=lambda row: float(row[0]))
        except ValueError:
            rows.sort(key=lambda row: row[0].casefold())
        reverse = bool(getattr(tree, "_sort_reverse_" + column, False))
        if reverse:
            rows.reverse()
        for index, (_, item) in enumerate(rows):
            tree.move(item, "", index)
        setattr(tree, "_sort_reverse_" + column, not reverse)


class ModalForm(tk.Toplevel):
    def __init__(self, parent: tk.Misc, title: str, app: "WarehouseApp"):
        super().__init__(parent)
        self.app = app
        self.title(title)
        self.configure(background="#ffffff")
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", lambda _event: self.cancel())
        self.grab_set()
        self.fields: dict[str, ttk.Entry | ttk.Combobox] = {}
        self._gate_iterator: Generator[bool, None, bool] | None = None
        self.after(50, self._center)

    def _center(self) -> None:
        self.update_idletasks()
        parent = self.master.winfo_toplevel()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def add_entry(
        self, parent: tk.Misc, row: int, key: str, label: str, value: str = ""
    ) -> ttk.Entry:
        ttk.Label(parent, text=label, style="Modal.TLabel").grid(
            row=row, column=0, sticky="w", padx=(0, 12), pady=5
        )
        entry = ttk.Entry(parent, width=34)
        entry.grid(row=row, column=1, sticky="ew", pady=5)
        entry.insert(0, value)
        self.fields[key] = entry
        return entry

    def add_combo(
        self,
        parent: tk.Misc,
        row: int,
        key: str,
        label: str,
        values: Sequence[str],
        selected: str,
    ) -> ttk.Combobox:
        ttk.Label(parent, text=label, style="Modal.TLabel").grid(
            row=row, column=0, sticky="w", padx=(0, 12), pady=5
        )
        combo = ttk.Combobox(parent, values=values, state="readonly", width=31)
        combo.grid(row=row, column=1, sticky="ew", pady=5)
        if selected:
            combo.set(selected)
        self.fields[key] = combo
        return combo

    def field_values(self) -> dict[str, str]:
        return {
            key: widget.get().strip()
            for key, widget in self.fields.items()
        }

    def focus_field(self, key: str) -> None:
        widget = self.fields.get(key)
        if widget is not None:
            widget.focus_set()
            if isinstance(widget, ttk.Entry) and not isinstance(widget, ttk.Combobox):
                widget.selection_range(0, tk.END)

    def show_validation_errors(self, errors: Sequence[FieldError]) -> None:
        for error in errors:
            widget = self.fields.get(error.field)
            if isinstance(widget, ttk.Combobox):
                widget.configure(style="Invalid.TCombobox")
            elif isinstance(widget, ttk.Entry):
                widget.configure(style="Invalid.TEntry")
        self.app.set_status("; ".join(error.message for error in errors), error=True)
        messagebox.showerror("Check the form", "\n".join(error.message for error in errors), parent=self)

    def gate(self, validate: Callable[[], tuple[bool, Sequence[FieldError]]]) -> bool:
        for widget in self.fields.values():
            if isinstance(widget, ttk.Combobox):
                widget.configure(style="TCombobox")
            elif isinstance(widget, ttk.Entry):
                widget.configure(style="TEntry")
        if self._gate_iterator is None:
            self._gate_iterator = validation_gate(
                validate, self.show_validation_errors, self.focus_field
            )
        try:
            next(self._gate_iterator)
        except StopIteration as result:
            self._gate_iterator = None
            return bool(result.value)
        except Exception:
            self._gate_iterator = None
            raise
        return False

    def cancel(self) -> None:
        self.destroy()

    def finish(self) -> None:
        self.grab_release()
        self.destroy()
