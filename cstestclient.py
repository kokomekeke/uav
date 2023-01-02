#!/usr/bin/env python3
#
# Created by aron.szabo@sagaxcommunications.com on 21/12/2022.
#

import os
import socket
import struct
import threading
import tkinter
import tkinter.ttk
from time import sleep

import matplotlib.cm
import numpy as np
from matplotlib import pyplot, ticker, transforms
from matplotlib.animation import FuncAnimation
from matplotlib.backend_bases import key_press_handler
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2Tk)
from matplotlib.gridspec import GridSpec


class BaseConnectionThread(threading.Thread):
    """
    Base class for both the Command and Stream connections.
    """

    def __init__(self):
        super().__init__()
        # Thread is daemon, it will quit on closing the program.
        self.daemon = True

        self.host_port = ""
        """
        Host and port in <address>:<tcp port> format.
        """

        self.client_socket = None
        """
        Python client socket object 
        """

        self.disconnect = False
        """
        When the disconnect flag is set, the thread loop will quit on the next iteration.
        """

        self.connected = False
        """
        Flag that indicates if the socket is connected.
        """

        self.connect_action = None
        """
        This function handle is called when the socket is connected.
        """

        self.disconnect_action = None
        """
        This function handle is called when the socket is disconnected.
        """

        self.buf_size = 2048
        """
        This buffer size will be read at once from the TCP socket.
        """

        self.status_label_ref = None
        """
        Reference of the status label on the main window
        """

    def run(self):
        self.disconnect = False
        host_port_split = self.host_port.split(":")
        host, port = (host_port_split[0], host_port_split[1])
        try:
            self.connect_action()
            self.status_label_ref.config(text="Connecting...")
            self.client_socket = socket.socket()  # instantiate
            self.client_socket.settimeout(1.0)
            self.client_socket.connect((host, int(port)))  # connect to the server
            self.connected = True
            self.status_label_ref.config(text="Connected")
            while True:
                try:
                    if self.disconnect:
                        self.status_label_ref.config(text="Disconnected")
                        break
                    data = self.client_socket.recv(self.buf_size)  # receive response
                    if not data:  # If the pipe is broken, data will be empty string
                        self.status_label_ref.config(text="Disconnected")
                        break
                    self.receive_processing(data)
                except TimeoutError:
                    pass
        except TimeoutError:
            self.status_label_ref.config(text="Timed out")
            pass
        except ConnectionError:
            self.status_label_ref.config(text="Connection broken")
            pass
        self.connected = False
        self.client_socket.close()  # close the connection
        self.disconnect_action()

    def receive_processing(self, data: bytes):
        pass


class CommandsConnectionThread(BaseConnectionThread):

    def __init__(self):
        super().__init__()
        self.console_textarea_ref = None
        """
        Reference of the commands connection console textarea on the main window
        """

    def receive_processing(self, data: bytes):
        self.console_textarea_ref.configure(state='normal')  # Textarea has to be unlocked to enable modification
        self.console_textarea_ref.insert(tkinter.END, '\n')
        self.console_textarea_ref.insert(tkinter.END, data.decode())
        self.console_textarea_ref.see(tkinter.END)  # Scroll to the bottom
        self.console_textarea_ref.configure(state='disabled')  # Block user editing


class StreamConnectionThread(BaseConnectionThread):

    def __init__(self):
        super().__init__()

        self.recreate_canvas_action = None
        """
        Action that recreates plot canvas
        """

        self.buffer = bytearray()
        """
        Binary packet data buffer
        """

        self.packet_count = 0
        """
        Overall packet count
        """

        self.buf_size = 65536
        """
        This buffer size will be read at once from the TCP socket.
        """

        self.waterfall_size = 200
        """
        Amount of spectrum lines to be displayed on the waterfall diagram.
        """

        self.fig_ref = None
        """
        Reference to the matplotlib figure.
        """

        self.waterfall = np.ones([1, 1])
        """
        Magnitude waterfall data (numpy matrix)
        """

        self.azimuth_spectrum = np.ones([1])
        """
        Azimuth spectrum data (numpy vector)
        """

        self.elevation_spectrum = np.ones([1])
        """
        Elevation spectrum data (numpy vector)
        """

        self.magnitude_plot = None
        """
        Matplotlib plot (axes) object for the magnitude plot
        """

        self.azimuth_plot = None
        """
        Matplotlib plot (axes) object for the azimuth plot
        """

        self.elevation_plot = None
        """
        Matplotlib plot (axes) object for the elevation plot
        """

        self.magnitude_image = None
        """
        Matplotlib image object for the magnitude plot
        """

        self.azimuth_image = None
        """
        Matplotlib image object for the azimuth plot
        """

        self.elevation_image = None
        """
        Matplotlib image object for the elevation plot
        """

        self.animation = None
        """
        Matplotlib FuncAnimation object for animating the graphs
        """

        self.animation_started = False
        """
        Indicates whether the animation and plot objects have been created
        """

        self._center_frequency = 0
        """
        Center frequency of the last burst
        """

        self._iq_rate = 0
        """
        Iq rate of the last burst
        """

    def create_anim(self, bin_count, centerfreq, iqrate, vmin, vmax):

        self.recreate_canvas_action()

        class HalfLocator(ticker.Locator):
            """
            Tick locator for matplotlib plot
            Set a tick on each integer multiple of a base within the view interval.
            """

            def __init__(self, max=1.0):
                self._max = max

            def set_params(self, max):
                """Set parameters within this locator."""
                if max is not None:
                    self._max = max

            def __call__(self):
                """Return the locations of the ticks."""
                vmin, vmax = self.axis.get_view_interval()
                return self.tick_values(vmin, vmax)

            def tick_values(self, vmin, vmax):
                if vmax < vmin:
                    vmin, vmax = vmax, vmin

                step = self._max / 4
                locs = []
                while len(locs) < 4:
                    locs = [loc for loc in np.arange(0, self._max, step) if vmin <= loc <= vmax]
                    step /= 2
                if self._max <= vmax:
                    locs.append(self._max)
                return self.raise_if_exceeds(locs)

            def view_limits(self, dmin, dmax):
                """
                Set the view limits
                """
                return matplotlib.transforms.nonsingular(
                    dmin, dmax, expander=1e-12, tiny=1e-13)

        def update_imag(frame_number):
            """
            Called on each frame of the graph animation
            """
            # self.waterfall = np.random.rand(100, bin_count)
            self.magnitude_image.set_data(self.waterfall)
            self.azimuth_image.set_ydata(self.azimuth_spectrum)
            self.elevation_image.set_ydata(self.elevation_spectrum)
            return [self.magnitude_image, self.azimuth_image, self.elevation_image]

        self.fig_ref.clf()
        grid_spec = GridSpec(nrows=2, ncols=2, figure=self.fig_ref)

        def bin_freq_formatter(x, pos=None):
            return f"{((x - bin_count / 2) * (iqrate / bin_count) + centerfreq) / 1e6:.3f}M"
            pass

        def sample_id_formatter(x, pos=None):
            return f"{x - self.waterfall_size:.0f}"
            pass

        def azimuth_format_coord(x, y):
            if 0 < x < len(self.azimuth_spectrum):
                val = self.azimuth_spectrum[int(x)]
            else:
                val = 0
            return f"Frequency: {bin_freq_formatter(x)}, Angle: {val:.3f} rad ({val / np.pi * 180:.2f} deg)"

        def elevation_format_coord(x, y):
            if 0 < x < len(self.elevation_spectrum):
                val = self.elevation_spectrum[int(x)]
            else:
                val = 0
            return f"Frequency: {bin_freq_formatter(x)}, Angle: {val:.3f} rad ({val / np.pi * 180:.2f} deg)"

        locator = HalfLocator(max=bin_count)

        self.waterfall = np.zeros([self.waterfall_size, bin_count])
        self.azimuth_spectrum = np.zeros([bin_count])
        self.elevation_spectrum = np.zeros([bin_count])
        self.magnitude_plot = self.fig_ref.add_subplot(grid_spec[:, 0])
        self.azimuth_plot = self.fig_ref.add_subplot(grid_spec[0, 1])
        self.elevation_plot = self.fig_ref.add_subplot(grid_spec[1, 1])
        self.magnitude_image = self.magnitude_plot.imshow(self.waterfall, cmap=matplotlib.cm.get_cmap('gnuplot'),
                                                          animated=True, vmax=vmax, vmin=vmin)
        self.azimuth_image = self.azimuth_plot.plot(self.azimuth_spectrum, lw=1, color='red', animated=True)[0]
        self.elevation_image = self.elevation_plot.plot(self.elevation_spectrum, lw=1, color='blue', animated=True)[0]

        self.magnitude_plot.xaxis.set_major_formatter(ticker.FuncFormatter(bin_freq_formatter))
        self.magnitude_plot.xaxis.set_major_locator(locator)
        self.magnitude_plot.yaxis.set_major_formatter(ticker.FuncFormatter(sample_id_formatter))

        self.magnitude_plot.set_label("Magnitude")
        self.magnitude_plot.set_ylabel("Packets")
        self.magnitude_plot.set_aspect(4)

        pi_chr = chr(0x03C0)
        self.azimuth_plot.xaxis.set_major_formatter(ticker.FuncFormatter(bin_freq_formatter))
        self.azimuth_plot.xaxis.set_major_locator(locator)
        self.azimuth_plot.yaxis.set_major_formatter(ticker.StrMethodFormatter("{x:.2f}"))
        self.azimuth_plot.grid(axis='y')
        self.azimuth_plot.format_coord = azimuth_format_coord
        self.azimuth_plot.set_ylim(-np.pi, np.pi)
        self.azimuth_plot.set_yticks([-np.pi, -np.pi / 2, 0, np.pi / 2, np.pi])
        self.azimuth_plot.set_yticklabels(
            [f"-{pi_chr}", f"-{pi_chr}/2", "0", f"+{pi_chr}/2", f"+{pi_chr}"]
        )
        self.azimuth_plot.set_ylabel("Azimuth")
        self.azimuth_plot.set_label("Azimuth")

        self.elevation_plot.xaxis.set_major_formatter(ticker.FuncFormatter(bin_freq_formatter))
        self.elevation_plot.xaxis.set_major_locator(locator)
        self.elevation_plot.yaxis.set_major_formatter(ticker.StrMethodFormatter("{x:.2f}"))
        self.elevation_plot.grid(axis='y')
        self.elevation_plot.format_coord = elevation_format_coord
        self.elevation_plot.set_ylim(-np.pi, np.pi)
        self.elevation_plot.set_yticks([-np.pi, -np.pi / 2, 0, np.pi / 2, np.pi])
        self.elevation_plot.set_yticklabels(
            [f"-{pi_chr}", f"-{pi_chr}/2", "0", f"+{pi_chr}/2", f"+{pi_chr}"]
        )
        self.elevation_plot.set_ylabel("Elevation")
        self.elevation_plot.set_label("Elevation")
        self.animation = FuncAnimation(self.fig_ref, update_imag, interval=25, blit=True)
        grid_spec.tight_layout(figure=self.fig_ref)
        grid_spec.update()
        self.fig_ref.canvas.draw()

    def receive_processing(self, data: bytes):
        self.buffer += bytearray(data)
        if len(self.buffer) >= 8:  # packet header is 28 bytes
            stream_id = int.from_bytes(self.buffer[0:4], "little")
            type_id = int.from_bytes(self.buffer[4:8], "little")
            if type_id == 2:  # end of file, flush buffer
                self.buffer = bytearray()
                self.animation_started = False
            elif len(self.buffer) >= 28 and type_id == 1:
                center_frequency = struct.unpack('f', self.buffer[8:12])[0]
                iq_rate = struct.unpack('f', self.buffer[12:16])[0]
                sample_index = int.from_bytes(self.buffer[16:24], "little")
                bin_count = int.from_bytes(self.buffer[24:28], "little")
                packet_size = 3 * 4 * bin_count + 28
                if len(self.buffer) >= packet_size:  # we got the entire packet in buffer

                    self.status_label_ref.config(
                        text=f"Packet {self.packet_count} - Stream {stream_id}, index {sample_index}"
                    )
                    magnitude_spectrum = np.asarray(struct.unpack(f"{bin_count}f", self.buffer[28:28 + bin_count * 4]))
                    self.azimuth_spectrum = np.asarray(
                        struct.unpack(f"{bin_count}f", self.buffer[28 + bin_count * 4: 28 + bin_count * 4 * 2]))
                    self.elevation_spectrum = np.asarray(
                        struct.unpack(f"{bin_count}f", self.buffer[28 + bin_count * 4 * 2: 28 + bin_count * 4 * 3]))

                    if (
                            not self.animation_started
                            or bin_count != self.waterfall.shape[1]
                            or center_frequency != self._center_frequency
                            or iq_rate != self._iq_rate
                    ):
                        # Animation can be created, because at this point we know bin count and other properties
                        # Also restart when bin count or any other parameter has changed
                        self.create_anim(bin_count, center_frequency, iq_rate, np.min(magnitude_spectrum),
                                         np.max(magnitude_spectrum))
                        self._iq_rate = iq_rate
                        self._center_frequency = center_frequency
                        self.animation_started = True

                    # FIFO on the waterfall data structure
                    self.waterfall = np.append(self.waterfall[-self.waterfall_size + 1:, :], [magnitude_spectrum],
                                               axis=0)

                    self.packet_count += 1
                    self.buffer = self.buffer[packet_size:]  # drop packet from buffer


class ClientWindow(tkinter.Frame):

    def __init__(self):
        super().__init__()
        self.fig = None
        self.canvas = None
        self.canvas_toolbar = None

        self.style = tkinter.ttk.Style()
        self.style.theme_use("default")

        self.pack(fill=tkinter.BOTH, expand=1)

        self.host_command = tkinter.StringVar(value="localhost:12936")
        """
        Variable for the current value of the command host textbox
        """

        self.host_stream = tkinter.StringVar(value="localhost:12937")
        """
        Variable for the current value of the stream host textbox
        """

        # Load host settings into the address boxes
        if os.path.exists("hosts.txt"):
            with open('hosts.txt') as f:
                self.host_command.set(f.readline().strip())
                self.host_stream.set(f.readline().strip())

        self.command_string = tkinter.StringVar(value="")
        """
        Variable for the current value of the command box
        """

        status_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        status_frame.pack(fill=tkinter.BOTH, side=tkinter.BOTTOM, expand=False)

        self.status_label = tkinter.Label(status_frame, text="Not connected")
        self.status_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        connect_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        connect_frame.pack(fill=tkinter.BOTH, expand=False, side=tkinter.TOP)

        host_command_label = tkinter.Label(connect_frame, text="Command host:")
        host_command_label.pack(side=tkinter.LEFT, fill=tkinter.BOTH, padx=5, pady=10, expand=True)

        self.host_command_entry = tkinter.Entry(connect_frame, textvariable=self.host_command)
        self.host_command_entry.pack(side=tkinter.LEFT, padx=5, expand=True)

        host_stream_label = tkinter.Label(connect_frame, text="Stream host:")
        host_stream_label.pack(side=tkinter.LEFT, fill=tkinter.BOTH, padx=5, pady=10, expand=True)

        self.host_stream_entry = tkinter.Entry(connect_frame, textvariable=self.host_stream)
        self.host_stream_entry.pack(side=tkinter.LEFT, padx=5, expand=True)

        self.disconnect_button = tkinter.Button(connect_frame, text="Disconnect", command=self.disconnect_commands)
        self.disconnect_button.pack(side=tkinter.RIGHT, padx=5, pady=5)
        self.disconnect_button.configure(state='disabled')

        self.connect_button = tkinter.Button(connect_frame, text="Connect", command=self.connect_commands)
        self.connect_button.pack(side=tkinter.RIGHT)

        self.plot_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        self.plot_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.TOP)

        self.command_suggestions = set()

        # Load command suggestions from file
        if os.path.exists("commands.txt"):
            with open('commands.txt') as f:
                for line in f:
                    self.command_suggestions.add(line.strip())

        def save_command_to_suggestions(command):
            """
            Save command to suggestions. Called when sending a command to the server.
            """
            self.command_suggestions.add(command)
            # Also save fragments of commands
            if ":" in command:  # Save command group fragment.
                self.command_suggestions.add(command.split(":")[0] + ":")
            if "?" in command:  # Save command without arguments.
                self.command_suggestions.add(command.split("?")[0] + "?")
            if "!" in command:  # Save command without arguments.
                self.command_suggestions.add(command.split("!")[0] + "!")
            command_history_sorted = list(self.command_suggestions)
            command_history_sorted.sort()
            with open('commands.txt', 'w') as f1:
                f1.writelines(h + '\n' for h in command_history_sorted)

        self.console_textarea = tkinter.Text(self, height=5, width=52)
        self.console_textarea.pack(fill=tkinter.BOTH, expand=False, side=tkinter.TOP)
        self.console_textarea.configure(state='disabled')

        # Configure a tag for the console area to indicate sent commands with blue
        # (received response will be default black)
        self.console_textarea.tag_configure("i", foreground="blue")

        self.command_thread = None
        self.stream_thread = None

        def send_cmd(*args):
            """
            Send the command from the command entry box to the client. Called on pressing the Return key.
            """
            cmd = self.command_string.get().replace("\n", "").replace("\r", "")
            self.command_string.set("")
            for cmd_line in cmd.split(";"):  # One command per line
                if not cmd_line:
                    continue
                cmd_line = cmd_line.strip()
                cmd_line += ";"
                save_command_to_suggestions(cmd_line)
                self.command_thread.client_socket.send(cmd_line.encode())
                self.console_textarea.configure(state='normal')  # Textarea has to be unlocked to enable modification
                self.console_textarea.insert(tkinter.END, '\n')
                self.console_textarea.insert(tkinter.END, cmd_line)
                self.console_textarea.tag_add("i", "end -1 lines", "end -1 chars")  # Tag, so that it will be blue
                self.console_textarea.see(tkinter.END)  # Scroll to the bottom
                self.console_textarea.configure(state='disabled')  # Block user editing
                sleep(0.1)

        def suggestions_filter(*args):
            """
            Filter the suggestions box. Called when a letter is typed to the command input box.
            """
            command_suggestions_lb.delete(0, tkinter.END)  # Clear suggestions box
            command_history_sorted = list(self.command_suggestions)
            command_history_sorted.sort()
            typed_command_string = self.command_string.get()  # Typed in command (fragment)
            if ":" not in typed_command_string:
                # If no ":" yet, display only command beginning fragments
                command_history_sorted = filter(
                    lambda command: ":" not in command or command.endswith(":"),
                    command_history_sorted
                )
            if not ("?" in typed_command_string or "!" in typed_command_string):
                # Do not display commands with arguments, if the whole command has not been typed yet.
                command_history_sorted = filter(
                    lambda command: ("!" not in command and "?" not in command)
                                    or command.endswith("!") or command.endswith("?"),
                    command_history_sorted
                )
            for history_item in command_history_sorted:
                if history_item.upper().startswith(typed_command_string.upper()):
                    command_suggestions_lb.insert(tkinter.END, history_item)

        def autocomplete(*args):
            """
            Grab the first from the suggestions. Called on the Tab key.
            """
            self.command_string.set(command_suggestions_lb.get(0))
            self.command_entry.focus()
            self.command_entry.icursor(tkinter.END)
            return 'break'

        def to_suggestions_list(*args):
            """
            Move from the command input box to the suggestions list. Called on the Down key.
            """
            command_suggestions_lb.focus()
            self.command_string.set(command_suggestions_lb.get(0))
            return 'break'

        def select_suggestion_cmd(*args):
            """
            Select a command from the list and use it in the command input box.
            """
            if command_suggestions_lb.size() > 0:
                self.command_string.set(command_suggestions_lb.get(command_suggestions_lb.curselection()))

        def to_command_box(*args):
            """
            Return from the command suggestion list to the command input box. Called on the Enter or Tab key.
            """
            self.command_entry.focus()
            self.command_entry.icursor(tkinter.END)
            return 'break'

        command_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        command_frame.pack(fill=tkinter.BOTH, expand=False, side=tkinter.TOP)

        self.command_entry = tkinter.Entry(command_frame, textvariable=self.command_string)
        self.command_entry.pack(side=tkinter.TOP, fill=tkinter.X, padx=5, expand=True)
        self.command_entry.bind('<Return>', send_cmd)
        self.command_entry.bind('<KeyRelease>', suggestions_filter)
        self.command_entry.bind('<Tab>', autocomplete)
        self.command_entry.bind('<Down>', to_suggestions_list)
        self.command_entry.configure(state='disabled')

        command_suggestions_lb = tkinter.Listbox(command_frame)

        command_suggestions_lb.bind("<<ListboxSelect>>", select_suggestion_cmd)
        command_suggestions_lb.bind("<Tab>", to_command_box)
        command_suggestions_lb.bind("<Return>", to_command_box)

        command_suggestions_lb.pack(side=tkinter.TOP, fill=tkinter.X, padx=5, expand=True)
        suggestions_filter()

    def create_canvas(self):
        """
        Creates matplotlib canvas for graph plots. Called when connecting to the client.
        """
        if self.canvas is not None:  # Remove old widget if there is one
            self.canvas.get_tk_widget().destroy()
            self.canvas = None
        if self.canvas_toolbar is not None:
            self.canvas_toolbar.destroy()
            self.canvas_toolbar = None
        self.fig = pyplot.Figure(constrained_layout=True)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)  # A tk.DrawingArea.
        # self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=1)

        self.canvas_toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame)
        self.canvas_toolbar.update()

        def on_canvas_key_press(event):
            key_press_handler(event, self.canvas, self.canvas_toolbar)

        self.canvas.mpl_connect("key_press_event", on_canvas_key_press)
        self.canvas_toolbar.pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=1)
        if self.stream_thread is not None:
            self.stream_thread.fig_ref = self.fig
            self.command_entry.focus()

    def connect_action(self):
        """
        Events triggered by successful connection
        """
        self.connect_button.configure(state='disabled')
        self.host_command_entry.configure(state='disabled')
        self.host_stream_entry.configure(state='disabled')
        self.disconnect_button.configure(state='normal')
        self.command_entry.configure(state='normal')
        self.command_entry.focus()

    def disconnect_action(self):
        """
        Events triggered by client disconnect
        """
        self.disconnect_button.configure(state='disabled')
        self.command_entry.configure(state='disabled')
        self.host_command_entry.configure(state='normal')
        self.host_stream_entry.configure(state='normal')
        self.connect_button.configure(state='normal')
        self.command_string.set("")
        self.disconnect_commands()  # to disconnect the other thread

    def connect_commands(self):
        """
        Action of the "Connect" button
        """
        self.command_thread = CommandsConnectionThread()
        self.command_thread.console_textarea_ref = self.console_textarea
        self.command_thread.connect_action = self.connect_action
        self.command_thread.disconnect_action = self.disconnect_action
        self.command_thread.host_port = self.host_command.get()
        self.command_thread.status_label_ref = self.status_label
        self.command_thread.start()
        self.stream_thread = StreamConnectionThread()
        self.stream_thread.recreate_canvas_action = self.create_canvas
        self.stream_thread.connect_action = self.connect_action
        self.stream_thread.disconnect_action = self.disconnect_action
        self.stream_thread.host_port = self.host_stream.get()
        self.stream_thread.canvas_ref = self.canvas
        self.stream_thread.status_label_ref = self.status_label
        self.stream_thread.start()
        with open('hosts.txt', 'w') as f1:
            f1.write(self.host_command.get() + '\n')
            f1.write(self.host_stream.get() + '\n')

    def disconnect_commands(self):
        """
        Action of the "Disconnect" button
        """
        self.command_thread.disconnect = True
        self.stream_thread.disconnect = True


if __name__ == '__main__':
    root = tkinter.Tk()
    ex = ClientWindow()
    root.geometry("1024x768")
    root.wm_title("CS Test Client")
    root.mainloop()
