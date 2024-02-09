import threading
import time
from pysagax.source.source_manager import (
    CoreServiceStatus,
    SourceManager,
    SourceStatus,
    Sources,
)

from pysagax.spot.commands_handler_thread import CommandsHandlerThread
from pysagax.ui.control_frame import ControlFrame
from pysagax.ui.playback_tab import PlaybackTab
from pysagax.ui.status_frame import StatusFrame


class StatusQueryThread(threading.Thread):
    def source_length_handler(self, cmd: str, resp: list[str]) -> None:
        if resp[0] == "0":
            source_length = int(resp[1])
            self.pb_tab.position_slider.configure(to=source_length)

    def source_position_handler(self, cmd: str, resp: list[str]) -> None:
        if resp[0] == "0":
            self.pb_tab.position_variable.set(int(resp[1]))

    def source_path_handler(self, cmd: str, resp: list[str]) -> None:
        self.source_manager.source_path_handler(resp)
        self.ct_tab.path_update()
        self.status_frame.path_update()

    def source_status_handler(self, cmd: str, resp: list[str]) -> None:
        self.source_manager.source_status_handler(resp)
        self.pb_tab.update_buttons()

    def recording_status_handler(self, cmd: str, resp: list[str]) -> None:
        self.source_manager.set_source_recording_status(resp)
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
        self.comm.set_response_handler("SOURCE:Status?", self.source_status_handler)
        self.comm.set_response_handler(
            "RECORDING:Status?", self.recording_status_handler
        )
        self.comm.set_response_handler("SOURCE:Length?", self.source_length_handler)
        self.comm.set_response_handler("SOURCE:Position?", self.source_position_handler)
        self.comm.set_response_handler("SOURCE:Path?", self.source_path_handler)

        self.source_manager = source_manager

    def run(self) -> None:
        while self.comm.is_alive():
            if self.source_manager.cs_status is not CoreServiceStatus.WORKING:
                self.comm.enqueue_commands(
                    "SOURCE:Status?;RECORDING:Status?;SOURCE:Length?;SOURCE:Position?;SOURCE:Path?;"
                )
            time.sleep(0.2)
        self._disconnect_actions()

    def _disconnect_actions(self) -> None:
        self.source_manager.cs_status = CoreServiceStatus.DISCONNECTED
        self.source_manager.source_status = SourceStatus.NOT_READY
        self.source_manager.current_source = Sources.NOT_SET

        self.pb_tab.update_buttons()
        self.ct_tab.path_update()
        self.status_frame.path_update()
