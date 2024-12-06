from __future__ import annotations

import queue
from typing import Any, Callable, Optional, Type
from time import sleep
import pysagax.message.heading_pb2 as proto_heading
import pysagax.message.command_pb2 as proto_cmd
import logging

class HeadingPbClient:
    def __init__(
        self,
        send_commands_function: Callable[[proto_cmd.Command], None],
        update_ui_callback: Callable[[], None],
    ) -> None:
        
        self._logger = logging.getLogger(self.__class__.__name__)
        self._send_commands_function = send_commands_function
        self._update_ui_callback = update_ui_callback
        self._heading_status = proto_heading.HeadingStatus()
        self._ui_dirty = False
        pass

    def ui_dirty(self) -> bool:
        _ui_dirty_val = self._ui_dirty
        self._ui_dirty = False
        return _ui_dirty_val

    def update_from_heading_status(self, status: proto_heading.HeadingStatus) -> None:
        if status.selected_source_type != self._heading_status.selected_source_type:
            self._ui_dirty = True
        self._heading_status = status
        self._update_ui_callback()

    def get_heading_source_types(self) -> list[str]:
        return [""] + list(self._heading_status.available_source_types) 

    def get_selected_source_type(self) -> str:
        return self._heading_status.selected_source_type

    def get_parameters(self) -> dict[str, list[Any]]:
        param_dict: dict[str, list[Any]] = dict()
        for param in self._heading_status.parameters:
            param_dict[param.name] = [param.type, param.value]
        return param_dict

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def update_parameter(self, key: str, value: Any) -> None:
        cmd = proto_cmd.Command()
        cmd.instruction = proto_cmd.CONFIG
        cmd.config.heading.selected_source_type = (
            self._heading_status.selected_source_type
        )
        # cmd.config.heading.parameters.update(key, value)
        self._logger.info(f"key {key} value {value} to {cmd.config.heading.parameters}")
        cmd.config.heading.parameters[key] = str(value)
        self._send_commands_function(cmd)

    def create(self, heading_source: str) -> None:
        cmd = proto_cmd.Command()
        cmd.instruction = proto_cmd.CONFIG
        self._logger.info(f"Heading source '{heading_source}' created")
        cmd.config.heading.selected_source_type = heading_source
        self._send_commands_function(cmd)

    def _poll_update(self) -> None:
        info_cmd = proto_cmd.Command()
        info_cmd.instruction = proto_cmd.INFO
        self._send_commands_function(info_cmd)

    def initialize(self) -> None:
        pass

    def close(self) -> None:
        pass
