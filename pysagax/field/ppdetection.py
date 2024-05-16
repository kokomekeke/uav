from __future__ import annotations
from multiprocessing.managers import ValueProxy
from queue import Queue
import queue
from datetime import datetime

from typing import Any, Optional

import numpy as np
import scipy

import pysagax.message.command_pb2 as proto_cmd
import pysagax.message.data_pb2 as proto_data
import pysagax.message.heading_pb2 as proto_heading
from google.protobuf.timestamp_pb2 import Timestamp

from pysagax.common.loop import Loop

from pysagax.util.protobuf_spectrum_utils import protobuf_spectrum_to_numpy
from pysagax.util.protobuf_spectrum_utils import create_spectrum_with_freq_dict


class DetectionAggregator:
    """
    Class for keeping track of past detections of the same signal and aggregation over time
    """

    def __init__(
        self, detection: proto_data.Detection, current_packet_time: int
    ) -> None:
        self._past_azimuths: list[float] = [detection.azimuth]
        self._past_elevations: list[float] = [detection.elevation]
        self._oldest_packet_time: int = current_packet_time

        self._mean_azimuth: Optional[float] = None
        self._mean_elevation: Optional[float] = None
        self._azimuth_deviation: Optional[float] = None
        self._elevation_deviation: Optional[float] = None

    def _generate_updated_packet(
        self, detection: proto_data.Detection
    ) -> proto_data.Detection:
        if self._mean_azimuth is not None:
            detection.mean_azimuth = self._mean_azimuth
        if self._mean_elevation is not None:
            detection.mean_elevation = self._mean_elevation
        if self._azimuth_deviation is not None:
            detection.deviation = self._azimuth_deviation

        return detection

    def update(
        self,
        detection: proto_data.Detection,
        current_packet_time: int,
        cutoff_time: int,
    ) -> proto_data.Detection:
        """
        Takes new detections. Aggregates them with the old ones
        if the oldest packet is older than the cutoff time.
        Returns an updated detection packet
        """
        self._oldest_packet_time = min(self._oldest_packet_time, current_packet_time)
        if self._oldest_packet_time < cutoff_time:
            self._aggregate()
            self._oldest_packet_time = current_packet_time

        self._past_azimuths.append(detection.azimuth)
        self._past_elevations.append(detection.elevation)

        return self._generate_updated_packet(detection)

    def _aggregate(self):
        """
        Updates mean_azimuth, mean_elevation and deviation, then clears the past results
        """
        # mean values
        self._mean_azimuth = scipy.stats.circmean(
            self._past_azimuths, high=np.pi, low=-np.pi
        )
        self._mean_elevation = scipy.stats.circmean(
            self._past_elevations, high=np.pi, low=-np.pi
        )

        # deviations
        self._azimuth_deviation = scipy.stats.circstd(
            self._past_azimuths, high=np.pi, low=-np.pi
        )
        self._elevation_deviation = scipy.stats.circstd(
            self._past_elevations, high=np.pi, low=-np.pi
        )

        self._past_azimuths = []
        self._past_elevations = []


class PPDetection(Loop):
    """
    Background process for ROI detection and data aggregation on measurement packets.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._queue_in: Optional[Queue] = None
        self._queue_out: Optional[Queue] = None
        self._conf_queue_in: Optional[Queue] = None
        self._conf_queue_out: Optional[Queue] = None
        self._se_queue_out: Optional[Queue] = None

        # storing current config
        self._current_config: proto_cmd.PostProcessingConfig = (
            proto_cmd.PostProcessingConfig()
        )

        # storing past detection values with event_ids as keys
        self._aggregators: dict[int, DetectionAggregator] = {}

    def __call__(
        self,
        queue_in: Queue[Any],
        queue_out: Queue[Any],
        conf_queue_in: Queue[Any],
        conf_queue_out: Queue[Any],
        se_queue_out: Queue[Any],
        *args,
        **kwargs,
    ) -> None:
        self._queue_in = queue_in
        self._queue_out = queue_out
        self._conf_queue_in = conf_queue_in
        self._conf_queue_out = conf_queue_out
        self._se_queue_out = se_queue_out
        return super()._call(*args, **kwargs)

    def _process_spectrum(
        self, packet: proto_data.Measurement
    ) -> dict[int, proto_data.Detection]:
        """Iterating over the spectrum with each element of the ROI mask"""

        # packet.detection should be empty, but let's keep the data if it isn't
        # detections: a dictionary of roi_id -> Detection
        detections = {d.event_id: d for d in packet.detection}

        magnitude_spectrums = [
            d
            for d in packet.data
            if d.spectrum_type == proto_data.Spectrum.SpectrumType.MAGNITUDE
        ]
        # can't do detection or SNR calculation without magnitude spectrum or roi masks
        if not len(magnitude_spectrums) or not len(self._current_config.roi):
            return detections
        spectrum = magnitude_spectrums[0]
        spectrum_with_freq = create_spectrum_with_freq_dict(spectrum)

        # run roi detection for each segment of the roi mask
        for roi in self._current_config.roi:
            # Separating spectrum to signal (inside the roi) and noise (outside the roi) bins
            roi_min = roi.center_frequency - roi.span / 2
            roi_max = roi.center_frequency + roi.span / 2
            signal_bins = {
                f: a
                for f, a in spectrum_with_freq.items()
                if roi_min <= f and f <= roi_max
            }
            noise_bins = {
                f: a
                for f, a in spectrum_with_freq.items()
                if not (roi_min < f and f < roi_max)
            }

            new_detections = self._detect_roi(signal_bins, noise_bins, roi)
            new_detections = self._calculate_snr(
                signal_bins, noise_bins, new_detections, roi
            )
            detections = detections | new_detections

        return detections

    def _detect_roi(
        self,
        signal_bins: dict[float, float | int],
        noise_bins: dict[float, float | int],
        roi: proto_cmd.ROIMask,
    ) -> dict[int, proto_data.Detection]:
        """
        Detecting signals that are more powerful than the ROI threshold.
        Returns a possibly empty list of detections with the following fields filled:
                event_id, roi_id, frequency, bandwidth, strength, azimuth, elevation, snr
        """
        # TODO: iterate over spectrum to find the frequencies that are stronger than the threshold
        # TODO: also find the bandwidth for those signals
        # TODO: get the corresponding azimuth and elevation
        #       (center frequency/strongest bin/avg over the signal's bandwidth)
        # TODO: calculate strength (in dBFS)

        # TODO: maybe keep track of detections over time (eg. by assigning a consistent event_id)
        #       simple event_id: the index of the bin for the center freq or
        #       look for existing event_ids that are very close/within the bandwidth to be consistent
        #       probably a more sophisticated event_id would be better in the longrun.

        return {}

    def _calculate_snr(
        self,
        signal_bins: dict[float, float | int],
        noise_bins: dict[float, float | int],
        detections: dict[int, proto_data.Detection],
    ) -> dict[int, proto_data.Detection]:
        """
        Rough SNR estimation function.
        Noise level: the average signal strength outside of the given ROI
        Signal level: amplitude of the signal given in the detection list
        Consider improving it. Here is a useful paper on the topic: https://spektroskopie.vdsastro.de/files/pdfs/snr.pdf
        """
        if len(noise_bins) == 0:
            return detections

        noise_db = sum(noise_bins.values()) / len(noise_bins)
        for event_id, detection in detections.items():
            signal_db = detection.strength
            snr = signal_db - noise_db
            detection.snr = snr if snr > 0 else 0
            detections[event_id] = detection

        return detections

    def _update_aggregated_results(
        self,
        detections: dict[int, proto_data.Detection],
        current_packet_time: Timestamp,
    ) -> dict[int, proto_data.Detection]:
        """
        Runs the detection aggregator for each detection found in the current measurement packet.
        Returns the results as a list of detections that is to be inserted in the measurement packet.
        """
        current_packet_time_float = current_packet_time.ToNanoseconds() / 1e9
        cutoff_time = current_packet_time_float - self._current_config.mean_window
        for event_id in detections.keys():
            if event_id in self._aggregators.keys():  # previously detected signal
                detections[event_id] = self._aggregators[event_id].update(
                    detections[event_id], current_packet_time_float, cutoff_time
                )
            else:  # newly detected signal -> create new aggregator
                self._aggregators[event_id] = DetectionAggregator(
                    detections[event_id], current_packet_time_float
                )

        # return the the updated results for the currently detected signals
        return detections

    def _loop(self) -> None:
        assert self._queue_in is not None
        assert self._queue_out is not None
        assert self._se_queue_out is not None
        assert self._conf_queue_in is not None
        assert self._conf_queue_out is not None

        # Hang until a new command is received
        try:
            conf_request = self._conf_queue_in.get(timeout=0, block=False)
            self._protobuf_to_log(conf_request)
            self._current_config = conf_request
            self._conf_queue_out.put(None)
        except queue.Empty:
            pass

        try:
            packet = self._queue_in.get(block=True, timeout=1)
            assert isinstance(packet, proto_data.Measurement)

            detections: dict[int, proto_data.Detection] = self._process_spectrum(packet)
            if self._current_config.mean_window > 0:
                detections = self._update_aggregated_results(detections, packet.time)
            del packet.detection[:]  # should be empty if ROI detection is moved from CS
            packet.detection.extend(detections.values())

            # TODO: occasionally remove very old detection aggregators

            self._logger.debug(
                f"PostProcessing/Detection finished on packet {packet.packet_id}"
            )
            self._queue_out.put(packet)
            self._se_queue_out.put(packet)

        except queue.Empty:
            pass
