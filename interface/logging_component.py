import tkinter as tk
from datetime import datetime, timezone

from interface.styling import *


class Logging(tk.Frame):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logging_text = tk.Text(self, height=10, width=60, state=tk.DISABLED, bg=BG_COLOR, fg=FG_COLOR_2,
                                    font=GLOBAL_FONT, highlightthickness=False, bd=0)
        self.logging_text.pack(side=tk.TOP)

    # Add a new log message to the tk.Text widget, placed at the top, with the current UTC time in front of it.
    def add_log(self, message: str):

        # Unlocks the tk.Text widgets
        self.logging_text.configure(state=tk.NORMAL)
        self.logging_text.insert("1.0", datetime.now(timezone.utc).strftime("%a %H:%M:%S ::  ") + message + "\n")
        # Locks the tk.Text widget to avoid accidentally inserting in it
        self.logging_text.configure(state=tk.DISABLED)
