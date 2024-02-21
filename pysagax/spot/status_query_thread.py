import threading
import time
from pysagax.source.source_manager import (
    CoreServiceStatus,
    SourceManager,
    SourceStatus,
    Sources,
)
import pysagax.message.command_pb2 as proto

from pysagax.spot.commands_handler_thread import CommandsHandlerThread
from pysagax.ui.control_frame import ControlFrame
from pysagax.ui.playback_tab import PlaybackTab
from pysagax.ui.status_frame import StatusFrame


class StatusQueryThread(threading.Thread):
    def source_position_handler(self, resp) -> None:    
        #telemetry also contains this info (once implemented in pysagaxUAV)
        self.pb_tab.position_variable.set(int(resp.position))

    def source_config_handler(self, resp) -> None:
        self.source_manager.source_config_handler(resp)
        self.ct_tab.path_update()
        self.status_frame.path_update()

    def source_telemetry_handler(self, resp) -> None:
        self.source_manager.source_telemetry_handler(resp)
        source_length = resp.telemetry.source.length
        self.pb_tab.position_slider.configure(to=source_length)
        self.pb_tab.update_buttons()
        self.pb_tab.update_recording_status()

    def __init__(
        self,
        comm: CommandsHandlerThread,
        pb_tab: PlaybackTab,
        ct_tab: ControlFrame,
        status_frame: StatusFrame,
        source_manager: SourceManager,
    ) -> None:
        super().__init__(daemon=True)
        self.comm = comm
        self.pb_tab = pb_tab
        self.ct_tab = ct_tab
        self.status_frame = status_frame
        self.comm.set_response_handler(proto.TELEMETRY, self.source_telemetry_handler)
        self.comm.set_response_handler(proto.POSITION, self.source_position_handler)
        self.comm.set_response_handler(proto.CONFIG, self.source_config_handler)

        self.source_manager = source_manager

        # instructions for continous querying the status of pysagaxUAV
        self.instruction_list = [proto.CONFIG, proto.POSITION, proto.TELEMETRY]
        self.commands = []
        for i in self.instruction_list:
            cmd = proto.Command()
            cmd.instruction = i
            self.commands.append(cmd)

    def run(self) -> None:
        while self.comm.is_alive():
            if self.source_manager.cs_status is not CoreServiceStatus.WORKING:
                self.comm.enqueue_commands(self.commands)
            time.sleep(0.5)   #TODO: define a value for it in config
        self._disconnect_actions()

    def _disconnect_actions(self) -> None:
        self.source_manager.cs_status = CoreServiceStatus.DISCONNECTED
        self.source_manager.source_status = SourceStatus.NOT_READY
        self.source_manager.current_source = Sources.NOT_SET

        self.pb_tab.update_buttons()
        self.ct_tab.path_update()
        self.status_frame.path_update()
