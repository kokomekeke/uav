#!/usr/bin/env python3
#
# Created by aron.szabo@sagaxcommunications.com on 21/12/2022.
#
from __future__ import annotations

import functools
import shlex

import zmq
from google.protobuf import json_format

import re
import pysagax.message.command_pb2 as proto
import argparse
import math
import multiprocessing
import os
import queue
import struct
import threading
import time
import tkinter
import typing
from datetime import datetime
from time import sleep
from tkinter import messagebox, ttk
from typing import Any, Callable, Optional

from pysagax.communication.req_rep import REQ

keys_cache = {"": []}


def is_indexing(identifier: str) -> Optional[tuple[str, int]]:
    result = re.search(r"(\w*)\[(\d+)\]$", identifier)
    if result:
        return result.group(1), int(result.group(2))
    else:
        return None


def strip_indexing(identifier):
    return re.sub(r"\[\d+\]$", "", identifier)


def rsetattr(obj, attr, val):
    global keys_cache
    pre, _, post = attr.rpartition(".")
    indexing = is_indexing(post)
    if indexing is not None:
        attr_got = rgetattr(rgetattr(obj, pre) if pre else obj, indexing[0])
        if callable(getattr(attr_got, "add", None)):
            while len(attr_got) <= indexing[1]:
                attr_got.add()
        elif callable(getattr(attr_got, "append", None)):
            while len(attr_got) <= indexing[1]:
                attr_got.append(0)
        attr_got[indexing[1]] = val
        return
    pre_without_indexing = strip_indexing(pre)
    obj_ret = rgetattr(obj, pre) if pre else obj
    if callable(getattr(obj_ret, "setdefault", None)):
        if post == "key":
            if pre_without_indexing not in keys_cache:
                keys_cache[pre_without_indexing] = []
            keys_cache[pre_without_indexing].append(val)
            return obj_ret.setdefault(val)
        elif post == "value":
            if pre_without_indexing in keys_cache:
                indexing = is_indexing(pre)
                obj_ret[keys_cache[pre_without_indexing][indexing[1]]] = val
                return
    return setattr(obj_ret, post, val)


# using wonder's beautiful simplification: https://stackoverflow.com/questions/31174295/getattr-and-setattr-on-nested-objects/31174427?noredirect=1#comment86638618_31174427


def rgetattr(obj, attr, *args):
    global keys_cache
    glob_attr = strip_indexing(attr)

    def _getattr(obj, attr):
        indexing = is_indexing(attr)
        if indexing is not None:
            attr_got = getattr(obj, indexing[0], *args)
            if (
                callable(getattr(attr_got, "get_or_create", None))
                and glob_attr in keys_cache
                and len(keys_cache[glob_attr]) > indexing[1]
            ):
                return keys_cache[glob_attr][indexing[1]]
            elif callable(getattr(attr_got, "setdefault", None)):
                return attr_got  # rsetattr takes care of that
            elif callable(getattr(attr_got, "add", None)):
                while len(attr_got) <= indexing[1]:
                    attr_got.add()
            elif callable(getattr(attr_got, "append", None)):
                while len(attr_got) <= indexing[1]:
                    attr_got.append(0)

            return attr_got[indexing[1]]
        else:
            return getattr(obj, attr, *args)

    return functools.reduce(_getattr, [obj] + attr.split("."))


class ZMQConnectionThread(threading.Thread):
    def __init__(self, address: str = "127.0.0.1") -> None:
        super().__init__(daemon=True)

        self.address = address

        # Define up- and downstream channels
        self._zmq = REQ(address_server=address, port_server=5556)
        self.disconnect: bool = False

        self.console_textarea_ref: Optional[tkinter.Text] = None
        """
        Reference of the commands connection console textarea on the main window
        """

        self.status_label_ref: Optional[tkinter.Label] = None
        """
        Reference of the status label on the main window
        """
        self.connect_callback: Optional[Callable[[], None]] = None
        """
        This function handle is called when the socket is initiating connection.
        """

        self.connected_callback: Optional[Callable[[], None]] = None
        """
        This function handle is called when the socket is initiating connection.
        """

        self.disconnect_callback: Optional[Callable[[], None]] = None
        """
        This function handle is called when the socket is disconnected.
        """

        self.connected: bool = False
        """
        Flag that indicates if the socket is connected.
        """
        self.send_queue = queue.Queue()

    def connect(self):
        """Connect and bind up- and downstream sockets"""

        if self.connect_callback is not None:
            self.connect_callback()
        self._zmq.connect()
        self.display_status_callback("ZMQ Connected")
        self.connected = True
        if self.connected_callback is not None:
            self.connected_callback()

    def display_status_callback(self, message: str) -> None:
        assert self.status_label_ref
        try:
            self.status_label_ref.config(text=message)
        except RuntimeError:
            pass  # it might happen when closing the window

    def run(self) -> None:
        """
        Entry point of the thread
        """
        self.connect()
        while not self.disconnect:
            try:
                command = self.send_queue.get(timeout=2)
                raw_response = self._zmq.send(command.SerializeToString())
                if raw_response is not None:
                    response = proto.Response()
                    response.ParseFromString(raw_response)

                    to_print = str(response)
                    assert self.console_textarea_ref
                    self.console_textarea_ref.configure(
                        state="normal"
                    )  # Textarea has to be unlocked to enable modification
                    self.console_textarea_ref.insert(tkinter.END, "\n--- Response\n")
                    self.console_textarea_ref.tag_add(
                        "j", f"end -15 chars", "end -1 chars"
                    )
                    self.console_textarea_ref.insert(tkinter.END, to_print)
                    self.console_textarea_ref.see(tkinter.END)  # Scroll to the bottom
                    self.console_textarea_ref.configure(
                        state="disabled"
                    )  # Block user editing
                else:
                    print("No response")
            except queue.Empty:
                pass
            except TimeoutError:
                self.display_status_callback("Connection timed out")
                break
            except ConnectionError:
                self.display_status_callback("Connection broken")
                break
        self.connected = False
        self.display_status_callback("Disconnected")
        if self.disconnect_callback is not None:
            self.disconnect_callback()


class VerticalScrolledFrame(
    ttk.Frame
):  # https://coderslegacy.com/python/make-scrollable-frame-in-tkinter/
    def __init__(self, parent, *args, **kw):
        ttk.Frame.__init__(self, parent, *args, **kw)

        # Create a canvas object and a vertical scrollbar for scrolling it.
        vscrollbar = ttk.Scrollbar(self, orient=tkinter.VERTICAL)
        vscrollbar.pack(fill=tkinter.Y, side=tkinter.RIGHT, expand=tkinter.FALSE)
        self.canvas = tkinter.Canvas(
            self,
            bd=0,
            highlightthickness=0,
            width=200,
            height=300,
            yscrollcommand=vscrollbar.set,
        )
        self.canvas.pack(side=tkinter.LEFT, fill=tkinter.BOTH, expand=tkinter.TRUE)
        vscrollbar.config(command=self.canvas.yview)

        # Reset the view
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

        # Create a frame inside the canvas which will be scrolled with it.
        self.interior = ttk.Frame(self.canvas, relief="groove")
        self.interior.bind("<Configure>", self._configure_interior)
        self.canvas.bind("<Configure>", self._configure_canvas)
        self.interior_id = self.canvas.create_window(
            0, 0, window=self.interior, anchor=tkinter.NW
        )

    def _configure_interior(self, event):
        # Update the scrollbars to match the size of the inner frame.
        size = (self.interior.winfo_reqwidth(), self.interior.winfo_reqheight())
        self.canvas.config(scrollregion=(0, 0, size[0], size[1]))
        if self.interior.winfo_reqwidth() != self.canvas.winfo_width():
            # Update the canvas's width to fit the inner frame.
            self.canvas.config(width=self.interior.winfo_reqwidth())

    def _configure_canvas(self, event):
        if self.interior.winfo_reqwidth() != self.canvas.winfo_width():
            # Update the inner frame's width to fill the canvas.
            self.canvas.itemconfigure(self.interior_id, width=self.canvas.winfo_width())


class PropSetter:
    def __init__(self, msg, field, descriptor, var, lambdas=[]):
        self.msg = msg
        self.field = field
        self.var = var
        self.descriptor = descriptor
        self.lambdas = lambdas

    def __call__(self):
        if not all([l() for l in self.lambdas]):
            # it is a part of a 'oneof', only include if that tab is selected
            return
        print(f"{self.field}={self.var.get()}")
        val = self.var.get()
        type = self.descriptor.type
        label = self.descriptor.label
        try:
            # if label == 3:  # repeated
            #     if type in [3, 4, 5, 6, 7, 13, 15, 16, 17, 18]:  # types of int
            #         val = [int(x.strip()) for x in val.split(",")]
            #     elif type == 2:  # float
            #         val = [float(x.strip()) for x in val.split(",")]
            #     else:
            #         val = [x.strip() for x in shlex.split(val)]
            #     for x in val:
            #         rgetattr(self.msg, self.field).append(x)
            #     return
            if type in [3, 4, 5, 6, 7, 13, 15, 16, 17, 18]:  # types of int
                val = int(val)
            elif type == 2:  # float
                val = float(val)
            elif type == 14:  # enum
                val = self.descriptor.enum_type.values_by_name[val].number
            if val != self.descriptor.default_value:
                rsetattr(self.msg, self.field, val)
            else:
                self.msg.ClearField(self.field)
        except ValueError:
            pass


class FakeDescriptor:
    def __init__(self, fields) -> None:
        self.fields = fields
        self.oneofs = []


class ClientWindow(tkinter.Frame):
    def __init__(self) -> None:
        global args
        super().__init__()

        self.zmq_thread: Optional[ZMQConnectionThread] = None

        self.pack(fill=tkinter.BOTH, expand=1)

        self.host_command = tkinter.StringVar(value="localhost")
        """
        Variable for the current value of the command host textbox
        """

        # Load host settings into the address boxes
        if os.path.exists("../hosts.txt"):
            with open("../hosts.txt") as f:
                self.host_command.set(f.readline().strip().split(":")[0])

        status_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        status_frame.pack(fill=tkinter.X, side=tkinter.BOTTOM, expand=False)

        status_command_label_label = tkinter.Label(
            status_frame,
            text="ZMQ Host:",
            font=tkinter.font.Font(weight=tkinter.font.BOLD, size=10),
        )
        status_command_label_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        self.status_command_label = tkinter.Label(
            status_frame, text="Not connected", font=tkinter.font.Font(size=10)
        )
        self.status_command_label.pack(side=tkinter.LEFT, padx=5, pady=10, anchor="w")

        connect_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        connect_frame.pack(fill=tkinter.BOTH, expand=False, side=tkinter.TOP)

        host_command_label = tkinter.Label(connect_frame, text="ZMQ host:")
        host_command_label.pack(
            side=tkinter.LEFT, fill=tkinter.BOTH, padx=5, pady=10, expand=True
        )

        self.host_command_entry = tkinter.Entry(
            connect_frame, textvariable=self.host_command
        )
        self.host_command_entry.pack(side=tkinter.LEFT, padx=5, expand=True)

        self.disconnect_button = tkinter.Button(
            connect_frame, text="Disconnect", command=self.disconnect_commands
        )
        self.disconnect_button.pack(side=tkinter.RIGHT, padx=5, pady=5)
        self.disconnect_button.configure(state="disabled")

        self.connect_button = tkinter.Button(
            connect_frame, text="Connect", command=self.connect_commands
        )
        self.connect_button.pack(side=tkinter.RIGHT)
        messages_frame = tkinter.Frame(self, relief=tkinter.RAISED, borderwidth=1)
        messages_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.TOP)
        command_frame = tkinter.Frame(
            messages_frame, relief=tkinter.RAISED, borderwidth=1
        )
        command_frame.pack(fill=tkinter.BOTH, expand=True, side=tkinter.LEFT)

        self.console_textarea = tkinter.Text(command_frame, height=16, width=40)
        self.console_textarea.pack(fill=tkinter.BOTH, expand=True, side=tkinter.TOP)
        self.console_textarea.configure(state="disabled")

        # Configure a tag for the console area to indicate sent commands with blue
        # (received response will be default black)
        self.console_textarea.tag_configure("i", foreground="blue")
        self.console_textarea.tag_configure("j", foreground="red")
        self.prop_setters: list[PropSetter] = []

        self.command_builder_frame = VerticalScrolledFrame(messages_frame)
        self.command_builder_frame_inner = self.command_builder_frame.interior

        self.sample_command = proto.Command()
        self.build_pb_frame(
            self.command_builder_frame_inner,
            self.sample_command,
            self.sample_command.DESCRIPTOR,
        )

        self.send_button = tkinter.Button(
            messages_frame, text="Send", command=self.send_commands
        )
        self.send_button.pack(side=tkinter.BOTTOM, padx=5, pady=5, fill=tkinter.X)
        self.command_builder_frame.pack(
            side=tkinter.LEFT, fill=tkinter.BOTH, padx=6, expand=False
        )

    def build_inner_control(
        self,
        master,
        command,
        descriptor,
        fieldname,
        selected_lambdas,
        field,
        row_i,
        draw_label=True,
    ):
        variable = tkinter.StringVar(value="")
        if draw_label:
            label = tkinter.Label(master, text=field.name, bd=1, relief="solid")
            label.grid(column=0, row=row_i, sticky="nesw", ipadx=2, ipady=2)

        if field.enum_type is not None:
            combo = ttk.Combobox(
                master,
                values=list(val.name for val in field.enum_type.values),
                textvariable=variable,
            )
            combo.grid(
                column=1,
                row=row_i,
                sticky=tkinter.E + tkinter.W,
                padx=0,
                pady=0,
            )
            variable.set(field.enum_type.values[0].name)
            self.prop_setters.append(
                PropSetter(command, fieldname, field, variable, selected_lambdas)
            )
        elif field.message_type is not None:  # LABEL_REPEATED == 3
            frame = tkinter.Frame(
                master, highlightbackground="gray", highlightthickness=1
            )
            self.build_pb_frame(
                frame, command, field.message_type, fieldname, selected_lambdas
            )
            frame.grid(
                column=1,
                row=row_i,
                sticky="news",
                padx=0,
                pady=0,
            )
        else:
            entry = tkinter.Entry(master, textvariable=variable)
            entry.grid(
                column=1,
                row=row_i,
                sticky="news",
                padx=0,
                pady=0,
            )
            self.prop_setters.append(
                PropSetter(command, fieldname, field, variable, selected_lambdas)
            )

    def repeated_field_minus(
        self,
        master,
        command,
        descriptor,
        fieldname,
        selected_lambdas,
        field,
        tabControl,
    ):
        i = tabControl.index(tkinter.END)

        if i > 1:
            print(f"removed {fieldname}[{i-2}]")
            self.prop_setters = list(
                filter(
                    lambda prop: not prop.field.startswith(f"{fieldname}[{i-2}]"),
                    self.prop_setters,
                )
            )
            tabControl.forget(tabControl.tabs()[-1])

    def repeated_field_plus_lambda(
        self,
        master,
        command,
        descriptor,
        fieldname,
        selected_lambdas,
        field,
        tabControl,
    ):
        return lambda: self.repeated_field_plus(
            master, command, descriptor, fieldname, selected_lambdas, field, tabControl
        )

    def repeated_field_plus(
        self,
        master,
        command,
        descriptor,
        fieldname,
        selected_lambdas,
        field,
        tabControl,
    ):
        i = tabControl.index(tkinter.END)
        frame = tkinter.Frame(master, highlightbackground="gray", highlightthickness=1)
        this_fn = f"{fieldname}.{field.name}[{i-1}]" if fieldname else field.name
        self.build_inner_control(
            frame,
            command,
            FakeDescriptor([field]),
            this_fn,
            selected_lambdas,
            field,
            0,
            draw_label=False,
        )
        tabControl.add(frame, text=f"[{i-1}]")

    def repeated_field_minus_lambda(
        self,
        master,
        command,
        descriptor,
        fieldname,
        selected_lambdas,
        field,
        tabControl,
    ):
        this_fn = f"{fieldname}.{field.name}" if fieldname else field.name
        return lambda: self.repeated_field_minus(
            master, command, descriptor, this_fn, selected_lambdas, field, tabControl
        )

    def build_pb_frame(
        self, master, command, descriptor, fieldname="", selected_lambdas=[]
    ):
        if not hasattr(command, "DESCRIPTOR"):
            return
        row_i = 0

        all_oneof_fields = []
        for oneof in descriptor.oneofs:
            all_oneof_fields.extend([field.name for field in oneof.fields])

        for i, field in enumerate(descriptor.fields):
            if field.name in all_oneof_fields:
                continue
            if field.label == 3:  # repeated
                tabControl = ttk.Notebook(master)
                frame_count_controls = tkinter.Frame(tabControl)
                plus_button = tkinter.Button(
                    frame_count_controls,
                    text="+",
                    command=self.repeated_field_plus_lambda(
                        master,
                        command,
                        descriptor,
                        fieldname,
                        selected_lambdas,
                        field,
                        tabControl,
                    ),
                )
                plus_button.grid(row=0, sticky="news")
                minus_button = tkinter.Button(
                    frame_count_controls,
                    text="-",
                    command=self.repeated_field_minus_lambda(
                        master,
                        command,
                        descriptor,
                        fieldname,
                        selected_lambdas,
                        field,
                        tabControl,
                    ),
                )
                minus_button.grid(row=1, sticky="news")

                tabControl.add(frame_count_controls, text=field.name)

                tabControl.grid(
                    column=0,
                    columnspan=2,
                    row=row_i,
                    sticky="news",
                    padx=0,
                    pady=0,
                )

            else:
                this_fn = f"{fieldname}.{field.name}" if fieldname else field.name
                self.build_inner_control(
                    master,
                    command,
                    descriptor,
                    this_fn,
                    selected_lambdas,
                    field,
                    row_i,
                )
            row_i += 1

        for oneof in descriptor.oneofs:
            label = tkinter.Label(master, text=oneof.name, bd=1, relief="solid")
            label.grid(column=0, row=row_i, sticky="news", ipadx=2, ipady=2)
            tabControl = ttk.Notebook(master)
            for i, oneof_field in enumerate(oneof.fields):
                sel_lambdas = selected_lambdas.copy()
                sel_lambdas.append(
                    (lambda final_i: (lambda: tabControl.index("current") == final_i))(
                        i
                    )
                )
                frame = tkinter.Frame(
                    master, highlightbackground="gray", highlightthickness=1
                )
                self.build_pb_frame(
                    frame,
                    command,
                    FakeDescriptor([oneof_field]),
                    fieldname,
                    selected_lambdas=sel_lambdas,
                )
                tabControl.add(frame, text=oneof_field.name)
            tabControl.grid(
                column=1,
                row=row_i,
                sticky="nesw",
                padx=0,
                pady=0,
            )
            row_i += 1

    def show_console(self, message: str, tag: str):
        self.console_textarea.configure(
            state="normal"
        )  # Textarea has to be unlocked to enable modification
        self.console_textarea.insert(tkinter.END, f"\n{message}\n")
        self.console_textarea.tag_add(
            tag, f"end -{len(message) + 2} chars", "end -1 chars"
        )
        self.console_textarea.see(tkinter.END)  # Scroll to the bottom
        self.console_textarea.configure(state="disabled")  # Block user editing

    def send_commands(self, *args: Any) -> None:
        global keys_cache
        keys_cache = {"": []}
        self.sample_command.Clear()
        for setter in self.prop_setters:
            setter()
        print()  # newline
        to_print = str(self.sample_command)
        self.console_textarea.configure(
            state="normal"
        )  # Textarea has to be unlocked to enable modification
        self.console_textarea.insert(tkinter.END, "\n--- Command\n")
        self.console_textarea.tag_add("j", f"end -14 chars", "end -1 chars")
        self.console_textarea.insert(tkinter.END, to_print)
        self.console_textarea.tag_add(
            "i", f"end -{len(to_print) + 1} chars", "end -1 chars"
        )  # Tag, so that it will be blue
        self.console_textarea.see(tkinter.END)  # Scroll to the bottom
        self.console_textarea.configure(state="disabled")  # Block user editing
        if self.zmq_thread is None or not self.zmq_thread.connected:
            self.show_console("Not connected!", "j")
            return
        self.zmq_thread.send_queue.put(self.sample_command)

    def connect_action(self) -> None:
        """
        Events triggered by successful connection
        """
        self.connect_button.configure(state="disabled")
        self.host_command_entry.configure(state="disabled")
        self.disconnect_button.configure(state="normal")

    def disconnect_action(self) -> None:
        """
        Events triggered by client disconnect
        """
        try:
            self.disconnect_button.configure(state="disabled")
            self.host_command_entry.configure(state="normal")
            self.connect_button.configure(state="normal")
            self.disconnect_commands()  # to disconnect the other thread
        except RuntimeError:
            pass  # it might happen when closing the window

    def connect_commands(self) -> None:
        """
        Action of the "Connect" button
        """
        self.zmq_thread = ZMQConnectionThread()
        self.zmq_thread.console_textarea_ref = self.console_textarea
        self.zmq_thread.connect_callback = self.connect_action
        self.zmq_thread.disconnect_callback = self.disconnect_action
        self.zmq_thread.address = self.host_command.get().split(":")[0]
        self.zmq_thread.status_label_ref = self.status_command_label
        self.zmq_thread.start()

    def disconnect_commands(self) -> None:
        """
        Action of the "Disconnect" button
        """
        if self.zmq_thread is not None:
            self.zmq_thread.disconnect = True


def main() -> None:
    multiprocessing.set_start_method("spawn")
    root = tkinter.Tk()
    ex = ClientWindow()
    root.geometry("1024x768")
    root.wm_title("PySagax-UAV ZMQ Test Client")
    root.mainloop()
    ex.disconnect_commands()


if __name__ == "__main__":
    main()
