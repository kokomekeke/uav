import threading
import time
from pysagax.source.source_manager import (
    CoreServiceStatus,
    SourceManager,
    SourceStatus,
    Sources,
)
import pysagax.message.command_pb2 as proto_cmd

# from pysagax.spotclient import Client
from pysagax.spot.command_thread import CommandThread
from pysagax.ui.control_frame import ControlFrame
from pysagax.ui.playback_tab import PlaybackTab
from pysagax.ui.status_frame import StatusFrame


class StatusQueryThread(threading.Thread):
    def source_position_handler(self, resp) -> None:
        # telemetry packets also contains this info
        self.pb_tab.update(current_position=int(resp.position))

    def source_config_handler(self, resp) -> None:
        self.source_manager.source_config_handler(resp)
        self.ct_tab.config_update()
        self.status_frame.config_update()

    def source_config_status_handler(self, resp):
        self.source_manager.source_config_status_handler(resp)
        self.status_frame.config_update()

    def source_telemetry_handler(self, resp) -> None:
        # telemetry packet is handed over to the same handler used by stream connection
        telemetry = resp.telemetry
        self.client.client_window.telemetry_packet_handler(telemetry)

    def __init__(self, client) -> None:
        super().__init__(daemon=True)
        self.client = client

        self.comm: CommandThread = client.command_thread
        self.pb_tab: PlaybackTab = client.client_window.playback_tab
        self.ct_tab: ControlFrame = client.client_window.control_frame
        self.status_frame: StatusFrame = client.client_window.status_frame
        self.comm.set_response_handler(
            proto_cmd.TELEMETRY, self.source_telemetry_handler
        )
        self.comm.set_response_handler(proto_cmd.POSITION, self.source_position_handler)
        self.comm.set_response_handler(proto_cmd.CONFIG, self.source_config_handler)
        self.comm.set_response_handler(proto_cmd.CONFIG_STATUS, self.source_config_status_handler)

        self.source_manager = client.source_manager

        # instructions for continous querying the status of pysagaxUAV
        self.instruction_list = [
            proto_cmd.CONFIG,
            #proto_cmd.POSITION,
            #proto_cmd.TELEMETRY,
        ]
        self.commands = self.commands_from_instructions(self.instruction_list)

        # instructions for querying during configuring CoreService
        self.configuring_instruction_list = [
            proto_cmd.CONFIG_STATUS,
            #proto_cmd.TELEMETRY,
        ]
        self.configuring_commands = self.commands_from_instructions(self.configuring_instruction_list)

    def commands_from_instructions(self, instruction_list: list[proto_cmd.Instruction]):
        commands = []
        for i in instruction_list:
            cmd = proto_cmd.Command()
            cmd.instruction = i
            commands.append(cmd)
        return commands

    def run(self) -> None:
        while self.comm.is_alive():
            if self.source_manager.cs_status is not CoreServiceStatus.WORKING:
                if self.source_manager.is_cs_configuring:
                    self.comm.enqueue_commands(self.configuring_commands)
                else:
                    self.comm.enqueue_commands(self.commands)
            time.sleep(0.5)  # TODO: define a value for it in config
        self._disconnect_actions()

    def _disconnect_actions(self) -> None:
        self.source_manager.cs_status = CoreServiceStatus.DISCONNECTED
        self.source_manager.source_status = SourceStatus.DISABLED
        self.source_manager.current_source = Sources.NOT_SET

        self.pb_tab.update_buttons()
        self.ct_tab.config_update()
        self.status_frame.config_update()
