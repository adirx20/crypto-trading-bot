import tkinter as tk
import typing


class Autocomplete(tk.Entry):
    # Constructor
    def __init__(self, symbols: typing.List[str], *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._symbols = symbols

        self._lb: tk.Listbox
        self._lb_opened = False

        self.bind("<Up>", self._up_down)
        self.bind("<Down>", self._up_down)
        self.bind("<Right>", self._select)

        self._var = tk.StringVar()
        # Links the tk.Entry content to a stringVar()
        self.configure(textvariable=self._var)
        # When the self._var value changes
        self._var.trace("w", self._changed)

    # Open a Listbok when the tk.Entry content changes and get a list of symbols matching this content
    def _changed(self, var_name: str, index: str, mode: str):

        self._var.set(self._var.get().upper())

        # Closes the Listbox when the tk.Entry is empty
        if self._var.get() == "":
            if self._lb_opened:
                self._lb.destroy()
                self._lb_opened = False

        else:
            if not self._lb_opened:
                # Limits the number of items displayed in the Listbox
                self._lb = tk.Listbox(height=8)
                self._lb.place(x=self.winfo_x() + self.winfo_width(), y=self.winfo_y() + self.winfo_height() + 40)

                self._lb_opened = True

            # Finds symbols that start with the character that you typed in the tk.Entry widget
            symbols_matched = [symbol for symbol in self._symbols if symbol.startswith(self._var.get())]

            if len(symbols_matched) > 0:

                try:
                    self._lb.delete(0, tk.END)

                except tk.TclError:
                    pass

                for symbol in symbols_matched[:8]:
                    self._lb.insert(tk.END, symbol)

            # If no match, closes the Listbox if it was open
            else:
                if self._lb_opened:
                    self._lb.destroy()
                    self._lb_opened = False

    # Triggered when the keyboard Right arrow is pressed,
    # set the current Listbox item as a value of the tk.Entry widget.
    def _select(self, event: tk.Event):

        if self._lb_opened:
            self._var.set(self._lb.get(tk.ACTIVE))
            self._lb.destroy()
            self._lb_opened = False
            self.icursor(tk.END)

    # Move the Listbox cursor up or down depending on the keyboard key that was pressed
    def _up_down(self, event: tk.Event):

        if self._lb_opened:

            # No Listbox item selected yet
            if self._lb.curselection() == ():
                index = -1

            else:
                index = self._lb.curselection()[0]

            lb_size = self._lb.size()

            if index > 0 and event.keysym == "Up":
                self._lb.select_clear(first=index)

                index = str(index - 1)

                self._lb.selection_set(first=index)
                self._lb.activate(index)

            elif index < lb_size - 1 and event.keysym == "Down":
                self._lb.select_clear(first=index)

                index = str(index + 1)

                self._lb.selection_set(first=index)
                self._lb.activate(index)
