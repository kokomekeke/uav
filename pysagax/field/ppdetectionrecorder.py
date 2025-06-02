from __future__ import annotations
from multiprocessing.managers import DictProxy
import pickle
from time import time, sleep
from queue import Queue
import queue

from typing import Any, Optional

import pysagax.message.data_pb2 as proto_data
from pysagax.message.proto_stream_to_file import FileStreamer, modify_recording_path


from pysagax.common.loop import Loop


class PPDetectionRecorder(Loop):
    """
    Optionally saves the Measurement packets without the spectrum data to files.
    """

    def __init__(
        self,
        detection_recording_path: str | None = None,
        max_recording_length: float = 0,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._queue_in: Optional[Queue] = None

        self._detection_recording_path: str | None = detection_recording_path
        self._file_streamer: FileStreamer | None = None  # for recording detections

        self._latest_telemetry_proxy: Optional[DictProxy] = None
        self._latest_se_state: Optional[str] = None  # obtained from latest telemetry
        self._recording_start_time: float = 0

        # timeout for starting a new recording file
        # if non-positive -> the program will not split the recording files
        self._max_recording_length: float = max_recording_length

    def __call__(
        self,
        queue_in: Queue[Any],
        latest_telemetry_proxy: Optional[DictProxy] = None,
        *args,
        **kwargs,
    ) -> None:
        self._queue_in = queue_in

        self._latest_telemetry_proxy = latest_telemetry_proxy
        sleep(2)  # wait for the Telemetry module to initialize
        return super()._call(*args, **kwargs)

    def _get_current_se_state(self):
        """Read and parse the latest telemetry packet to extract ScanEngine state"""
        if (
            self._latest_telemetry_proxy is None
            or "Telemetry" not in self._latest_telemetry_proxy
        ):
            return "UNKNOWN"
        current_telemetry = proto_data.Telemetry()
        current_telemetry = pickle.loads(self._latest_telemetry_proxy["Telemetry"])
        full_state = current_telemetry.scanengine_state

        # Remove IDLE and IN_PROGRESS substates, as we don't care about them here.
        short_state = full_state.replace("_IDLE", "").replace("_IN_PROGRESS", "")
        return short_state

    def _file_streamer_setup(self) -> None:
        """
        Creates a new FileStreamer if needed:
            - at startup
            - after ScanEngine mode has changed
        """
        if self._detection_recording_path is None:
            return  # we don't want to record detections

        current_se_state = self._get_current_se_state()

        if (
            time() - self._recording_start_time < self._max_recording_length
            or self._max_recording_length <= 0
        ) and self._latest_se_state == current_se_state:
            # starting new file not needed
            return

        if self._file_streamer is not None:
            # close old file streamer
            self._file_streamer.close()
            self._file_streamer = None

        # Create new FileStreamer
        try:
            self._recording_start_time = time()
            self._latest_se_state = current_se_state

            new_path = modify_recording_path(
                self._detection_recording_path, self._latest_se_state
            )

            self._file_streamer = FileStreamer(new_path, "record")
            self._logger.info(f"Detection recording will be saved to '{new_path}'")
        except Exception as e:
            self._logger.error("Couldn't create detection recorder: ", e)
        # TODO: new FileStreamer at scan plan change

    def _record_packet(self, packet: proto_data.Measurement) -> None:
        """
        Records the detections if they need to be (recording path is set)
        """
        self._file_streamer_setup()
        if self._file_streamer is None:
            return

        try:
            del packet.data[:]  # Remove spectrums. We're not making spectrograms here.
            self._file_streamer.put(packet)
        except Exception as e:
            self._logger.error("Detection recording:", e)

    def _loop(self) -> None:
        assert self._queue_in is not None

        try:
            packet = self._queue_in.get(block=True, timeout=1)
            assert isinstance(packet, proto_data.Measurement)

            # saving post processing results to file
            self._record_packet(packet)

        except queue.Empty:
            pass
