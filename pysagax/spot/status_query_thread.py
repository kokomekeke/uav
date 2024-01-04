import threading
import time

from pysagax.spot.commands_handler_thread import CommandsHandlerThread
from pysagax.ui.control_frame import ControlFrame
from pysagax.ui.playback_tab import PlaybackTab


class StatusQueryThread(threading.Thread):
    def source_length_handler(self, cmd: str, resp: list[str]) -> None:
        if resp[0] == "0":
            source_length = int(resp[1])
            self.pb_tab.position_slider.configure(to=source_length)

    def source_position_handler(self, cmd: str, resp: list[str]) -> None:
        if resp[0] == "0":
            self.pb_tab.position_variable.set(int(resp[1]))

    def source_path_handler(self, cmd: str, resp: list[str]) -> None:
        self.ct_tab.path_update(resp)

    def source_status_handler(self, cmd: str, resp: list[str]) -> None:
        self.pb_tab.source_configured = True if int(resp[1]) else False
        self.pb_tab.source_running = True if int(resp[2]) else False
        self.pb_tab.set_buttons_enabled()

    def recording_status_handler(self, cmd: str, resp: list[str]) -> None:
        rec_activated = True if int(resp[1]) else False
        rec_running = True if int(resp[2]) else False
        self.pb_tab.rec_status_string.set(
            "🟣"
            if (not rec_activated) and (not rec_running)
            else "🟢"
            if rec_activated and (not rec_running)
            else "🟠"
            if rec_activated and rec_running
            else "❓"
        )
        self.pb_tab.rec_status_label.configure(
            fg=(
                "Aqua"
                if (not rec_activated) and (not rec_running)
                else "LimeGreen"
                if rec_activated and (not rec_running)
                else "Red"
                if rec_activated and rec_running
                else "Red"
            )
        )

    def __init__(
        self, comm: CommandsHandlerThread, pb_tab: PlaybackTab, ct_tab: ControlFrame
    ) -> None:
        super().__init__(daemon=True)
        self.comm = comm
        self.pb_tab = pb_tab
        self.ct_tab = ct_tab
        self.comm.set_response_handler("SOURCE:Status?", self.source_status_handler)
        self.comm.set_response_handler(
            "RECORDING:Status?", self.recording_status_handler
        )
        self.comm.set_response_handler("SOURCE:Length?", self.source_length_handler)
        self.comm.set_response_handler("SOURCE:Position?", self.source_position_handler)
        self.comm.set_response_handler("SOURCE:Path?", self.source_path_handler)

    def run(self) -> None:
        while self.comm.is_alive():
            if not self.pb_tab.working:
                self.comm.enqueue_commands(
                    "SOURCE:Status?;RECORDING:Status?;SOURCE:Length?;SOURCE:Position?;SOURCE:Path?;"
                )
            time.sleep(0.2)
