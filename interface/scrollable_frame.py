import tkinter as tk


class ScrollableFrame(tk.Frame):
    # Constructor
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Frames are not scrollable by default.
        # This widget draws a frame inside a Canvas widget so that the canvas scrolling will actually scroll the Frame
        # inside it.
        self.canvas = tk.Canvas(self, highlightthickness=0, **kwargs)
        self.vsb = tk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.sub_frame = tk.Frame(self.canvas, **kwargs)

        self.sub_frame.bind("<Configure>", self._on_frame_configure)
        self.sub_frame.bind("<Enter>", self._activate_mousewheel)
        self.sub_frame.bind("<Leave>", self._deactivate_mousewheel)

        # Place the sub_frame in the canvas
        self.canvas.create_window((0, 0), window=self.sub_frame, anchor="nw")

        # Link the scrollbar and canvas together
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.X, expand=True)
        # Make sure the scrollbar expands to the full frame height
        self.vsb.pack(side=tk.RIGHT, fill=tk.Y)

    # Make the whole canvas content (defined by the .bbox("all") coordinates) scrollable.
    def _on_frame_configure(self, event: tk.Event):

        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    # Activate the _on_mousewheel() callback when the mouse enters the canvas sub_frame
    def _activate_mousewheel(self, event: tk.Event):

        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    # Deactivate the _on_mousewheel() callback when the mouse leaves the canvas sub_frame
    def _deactivate_mousewheel(self, event: tk.Event):

        self.canvas.unbind_all("<MouseWheel>")

    # Scroll the canvas content when the MouseWheel is triggered
    def _on_mousewheel(self, event: tk.Event):

        # Decrease "60" to increase the sensitivity
        self.canvas.yview_scroll(int(-1 * (event.delta / 60)), "units")
