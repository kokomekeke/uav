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

from pysagax.util.protobuf_spectrum_utils import Spectrum
from pysagax.util.roi_mask_from_json import roi_mask_from_json
from pysagax.util.queue_put import queue_put


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

    def __init__(self, default_roi_mask: str = "", *args, **kwargs) -> None:
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

        self._default_roi_mask: str = default_roi_mask  # path of json roi mask
        if self._default_roi_mask:
            self._current_config.roi.extend(roi_mask_from_json(self._default_roi_mask))
            self._logger.info(f"Initialized with {self._current_config}")

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

    def _get_spectrum_by_type(
        self,
        packet: proto_data.Measurement,
        spectrum_type: proto_data.Spectrum.SpectrumType,
    ) -> Optional[Spectrum]:
        """
        Returns the first spectrum of a given type in the packet in as a Spectrum object.
        Returns None if no spectrum of the given type was in the packet
        """
        spectrums = [d for d in packet.data if d.spectrum_type == spectrum_type]
        spectrum = None
        try:
            if len(spectrums):
                spectrum = Spectrum.from_proto_spectrum(spectrums[0])
        except:
            self._logger.critical(
                f"Spectrum packet with spectrum_type as {proto_data.Spectrum.SpectrumType.Name(spectrum_type)} can't be decoded."
            )
        return spectrum

    def _process_spectrum(
        self, packet: proto_data.Measurement
    ) -> dict[int, proto_data.Detection]:
        """Iterating over the spectrum with each element of the ROI mask"""

        # packet.detection should be empty, but let's keep the data if it isn't
        # detections: a dictionary of roi_id -> Detection
        detections = {d.event_id: d for d in packet.detection}

        magnitude_spectrum = self._get_spectrum_by_type(
            packet, proto_data.Spectrum.SpectrumType.MAGNITUDE
        )
        azimuth_spectrum = self._get_spectrum_by_type(
            packet, proto_data.Spectrum.SpectrumType.AZIMUTH
        )
        elevation_spectrum = self._get_spectrum_by_type(
            packet, proto_data.Spectrum.SpectrumType.ELEVATION
        )

        # can't do detection or SNR calculation without magnitude spectrum or roi masks
        if magnitude_spectrum is None or not len(self._current_config.roi):
            return detections

        # run roi detection for each segment of the roi mask
        for roi in self._current_config.roi:
            # Separating spectrum to signal (inside the roi) and noise (outside the roi) bins
            try:
                roi_spectrum, noise_bins = magnitude_spectrum.apply_roi(
                    roi, return_noise_bins=True
                )
                roi_azimuth_spectrum = azimuth_spectrum.apply_roi(roi)
                roi_elevation_spectrum = elevation_spectrum.apply_roi(roi)
            except IndexError as e:
                # The intersection of the ROI and the spectrum contains no bins
                self._logger.debug(f"{e}")
                continue
            new_detections = self._detect_roi(
                roi_spectrum, noise_bins, roi, roi_azimuth_spectrum, roi_elevation_spectrum
            )
            new_detections = self._calculate_snr(
                roi_spectrum, noise_bins, new_detections
            )
            detections = detections | new_detections

        return detections

    def _detect_roi(
        self,
        signal_bins: Spectrum,
        noise_bins: np.ndarray[float | int],
        roi: proto_cmd.ROIMask,
        signal_azimuth_bins: Optional[Spectrum],
        signal_elevation_bins: Optional[Spectrum],
    ) -> dict[int, proto_data.Detection]:
        """
        Detecting signals that are more powerful than the ROI threshold.
        Returns a possibly empty list of detections with the following fields filled:
                event_id, roi_id, frequency, bandwidth, strength, azimuth, elevation, snr
        """
        # finding the peak of the signal
        peak_index = np.argmax(signal_bins)
        peak_freq = signal_bins.get_freq_from_index(peak_index)
        peak_amplitude = signal_bins[peak_freq]

        if peak_amplitude < roi.threshold:
            # No signal detected
            return {}

        d = proto_data.Detection()
        d.roi_id = roi.roi_id
        d.frequency = peak_freq
        d.bandwidth  # TODO
        d.strength = peak_amplitude

        # TODO: calculate azimuth and elevation using average weighted with bin amplitude
        if signal_azimuth_bins is not None:
            try: 
                azimuth_detections = np.array(signal_azimuth_bins)[np.array(signal_bins) >= roi.threshold] #TODO move filter to a variable
                d.azimuth = scipy.stats.circmean(azimuth_detections, high=np.pi, low=-np.pi )
            except:
                self._logger.critical("Can't detect azimuth")
        else:
            self._logger.debug("Azimuth spectrum not provided by CoreService")

        if signal_elevation_bins is not None:
            try: 
                elevation_detections = np.array(signal_elevation_bins)[np.array(signal_bins) >= roi.threshold] #TODO move filter to a variable
                d.elevation = scipy.stats.circmean(elevation_detections, high=np.pi, low=-np.pi )
            except:
                self._logger.critical("Can't detect elevation")
        else:
            self._logger.debug("Elevation spectrum not provided by CoreService")
        return {roi.roi_id: d}

    def _calculate_snr(
        self,
        signal_bins: Spectrum,
        noise_bins: np.ndarray[float | int],
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

        noise_db = noise_bins.mean()
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
            self._current_config = conf_request.config.pp
            if len(self._current_config.roi) == 0 and self._default_roi_mask:
                # use defaults if incoming instruction didn't have roi mask defined
                self._current_config.roi.extend(
                    roi_mask_from_json(self._default_roi_mask)
                )
                self._logger.info(
                    f"No ROImask defined in Config message. Returning to default ROImask."
                )
            response = proto_cmd.Response(config=conf_request.config)
            self._conf_queue_out.put(response)  # should use util.queue_put?
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

            self._logger.trace(
                f"PostProcessing/Detection finished on packet {packet.packet_id}"
            )
            queue_put(
                self._queue_out, packet, 0, logger=self._logger, message="Queue out"
            )
            queue_put(self._se_queue_out, packet, 0) # No logging since SE only takes packeges in scanning mode
        except queue.Empty:
            pass
