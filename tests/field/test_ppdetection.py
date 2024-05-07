import pytest
from pytest_mock import mocker
from pysagax.field.ppdetection import DetectionAggregator, PPDetection
import pysagax.message.data_pb2 as proto_data
import pysagax.message.command_pb2 as proto_cmd
import copy

from pysagax.util.protobuf_spectrum_to_numpy import protobuf_spectrum_to_numpy
from pysagax.util.mat import normalize_angle
import numpy as np


class TestDetectionAggregation:
    @pytest.mark.parametrize(
        ["azimuth", "elevation", "t0"], [(1, 2, 3), (2, 3, 4), (-1, -2, 120)]
    )
    def test_detection_aggregator_init(self, azimuth, elevation, t0):
        """Testing the initialization of a DetectionAggregator object"""

        # Make the detection packet
        d0 = proto_data.Detection(azimuth=azimuth, elevation=elevation)

        # init the detection aggregator
        da = DetectionAggregator(d0, t0)

        assert da._mean_azimuth is None
        assert da._mean_elevation is None
        assert da._azimuth_deviation is None
        assert da._elevation_deviation is None

        assert azimuth in da._past_azimuths
        assert elevation in da._past_elevations
        assert t0 == da._oldest_packet_time

    @pytest.fixture()
    def make_detection_packets(self, request):
        """
        Makes a list of detection packets from a list of azimuth and elevation values
        Parameters in request (only the azimuth list is required):
            azimuths: list[float]
            elevations: list[float] = None
            is_degrees: bool = True
        """
        azimuths = request.param[0]
        elevations = request.param[1] if len(request.param) > 1 else None
        is_degrees = request.param[2] if len(request.param) > 2 else True
        packets = []
        if is_degrees:
            conversion_factor = np.pi / 180
        else:
            conversion_factor = 1
        for i in range(len(azimuths)):
            p = proto_data.Detection(azimuth=azimuths[i] * conversion_factor)
            if elevations is not None:
                p.elevation = elevations[i] * conversion_factor
            packets.append(p)
        return packets

    @pytest.mark.parametrize(
        ["make_detection_packets", "expected_results"],
        # make_detection_packets: list of azimuths, optional list of elevations, optional is_degrees
        # expected results: tuple of (mean_azimuth, mean_elevation, azimuth_deviation, elevation_deviation)
        [
            [[[359, 1]], (0, None, 1, None)],
            [[[179, -179]], (180, None, 1, None)],
            [[[-90, 180, 90]], (180, None, 84.92975211833138, None)],
            [[[359 + 5 * 360, 1 - 4 * 360]], (0, None, 1, None)],
            # Lots of values and also elevation angles
            [
                [[a - 72 for a in range(91)], [e / 100 for e in range(91)]],
                (45 - 72, 0.45, 26.5540228, 0.26267878685696366),
            ],
        ],
        indirect=["make_detection_packets"],
    )
    def test_circular_averaging(self, make_detection_packets, expected_results):
        """Testing DetectionAggregator's circular mean and deviation calculations"""
        detection_packets = make_detection_packets
        # initialize the aggregator with the first packet
        da = DetectionAggregator(detection_packets.pop(0), current_packet_time=1)

        # update the aggregator with all the remaining packets
        for p in detection_packets:
            da.update(p, current_packet_time=1, cutoff_time=0)

        # Since cutoff_time was less than oldest_packet time, no aggregations should've happened:
        assert da._mean_azimuth is None
        assert da._mean_elevation is None
        assert da._azimuth_deviation is None
        assert da._elevation_deviation is None

        # Pass a new packet with cutoff timestamp that triggers aggregation
        da.update(proto_data.Detection(), current_packet_time=10, cutoff_time=5)

        aggregation_results = [
            da._mean_azimuth,
            da._mean_elevation,
            da._azimuth_deviation,
            da._elevation_deviation,
        ]
        # Check the results
        for expected, actual in zip(expected_results, aggregation_results):
            if expected is not None:
                expected_radians = expected * np.pi / 180
                error = normalize_angle(actual - expected_radians)
                assert abs(error) < 1e-6
            else:
                assert actual == 0


class TestCalculateSNR:
    @pytest.fixture(scope="function")
    def make_snr_test_cases(self, request):
        """
        Fuction that returns the predefined spectrum, detection packet and roi packets.
        This way the parametrize decorator only has to contain the id of these objects
        for readability and reusability.

        Parameters for this fixture:
            spectrum_no: int,
            detections_no: int,
            roi_center: float,
            roi_span: float,
            spectrum_center_freq=15, (optional)
            spectrum_bandwidth=10,   (optional)
        """

        spectrum_no = request.param[0]
        detections_no = request.param[1]
        roi_center = request.param[2]
        roi_span = request.param[3]
        if len(request.param) == 6:
            spectrum_center_freq = request.param[4]
            spectrum_bandwidth = request.param[5]
        else:
            spectrum_center_freq = 15
            spectrum_bandwidth = 10

        # Predefined spectrums. List of amplitudes for each bin in dB
        spectrums = {
            0: [1, 1, 1, 1, 50, 100, 0, 1, 1, 1, 1],
            1: [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            2: [0, 2, 0, 2, 100, 100, 100, 2, 0, 1, 1],
            3: [-100, -90, -80, -70, -20, -50, -20, -70, -80, -90, -100],
            4: [-20, -30, 20, 100, 20, -20, -30],  # 7 bins, mixed positive & negative
            5: [-40, -50, -60, -20, -10, -20, -10, -20, -20, -10, -10],
        }

        # Make a Measurement packet with a(n empty) Magnitude spectrum
        #     (No need to generate binary data from our spectrum as the
        #     protobuf_spectrum_to_numpy is mocked in the test functions)
        packet = proto_data.Measurement()
        packet.data.append(
            proto_data.Spectrum(
                center_frequency=spectrum_center_freq,
                bandwidth=spectrum_bandwidth,
                spectrum_type=proto_data.Spectrum.SpectrumType.MAGNITUDE,
            )
        )

        # Predefined Detections
        # Each element is a simulated output of the ROI detecting algorithm
        # namely a dictionary of event_id -> Detection packet
        # Strength is in dB
        detections = {
            # Single signal detected in a ROI window
            0: {
                0: proto_data.Detection(strength=100),
            },
            1: {
                0: proto_data.Detection(strength=1),
            },
            # Multiple signals detected in a single ROI:
            2: {
                0: proto_data.Detection(strength=100),
                1: proto_data.Detection(strength=50),
            },
            3: {
                0: proto_data.Detection(strength=100),
                1: proto_data.Detection(strength=1),
            },
            # Negative values:
            4: {
                0: proto_data.Detection(strength=-50),
            },
            5: {
                0: proto_data.Detection(strength=-50),
                1: proto_data.Detection(strength=-20),
            },
        }

        roi = proto_cmd.ROIMask(center_frequency=roi_center, span=roi_span + 1e-6)

        return {
            "spectrum_numpy": np.array(spectrums[spectrum_no]),
            "packet": packet,
            "detections": detections[detections_no],
            "roi": roi,
        }

    def arrange_and_act_calculate_snr(
        self, measurement, spectrum, detections, roi, mocker
    ):

        original_detections = copy.deepcopy(detections)  # save the original detections

        # mocking protobuf_spectrum_to_numpy
        mocker.patch(
            "pysagax.field.ppdetection.protobuf_spectrum_to_numpy",
            return_value=spectrum,
        )

        pp = PPDetection()
        returned_detections = pp._calculate_snr(measurement, detections, roi)

        return original_detections, returned_detections

    @pytest.mark.parametrize(
        ["make_snr_test_cases", "expected"],
        [
            # [make_snr_test_cases, expected], where params for make_snr_test_cases is a list of:
            #   spectrum_no, detections_no, roi_center, roi_span, optional: spectrum_center_freq=15, spectrum_bandwidth=10
            #   and expected is a list of expected snr values for each detection packet
            # Single detection from ROI:
            [[0, 0, 15, 2], [99]],
            [[1, 0, 5, 2], [99]],  # roi outside of spectrum // shouldn't happen
            [[1, 1, 15, 2], [0]],
            [[2, 0, 15, 2], [99]],
            # Multiple detections from single ROI:
            [[0, 2, 15, 2], [99, 49]],
            [[0, 3, 15, 2], [99, 0]],
            # Negative amplitudes
            [[3, 4, 15, 2], [35]],
            [[3, 5, 15, 2], [35, 65]],
            [[3, 5, 15, 4], [40, 70]],  # different ROI definion changes the noise lvl
            # Mixed positive and negative values
            [[4, 0, 15, 2, 15, 6], [125]],
            # Peak smaller than noise:
            [[5, 4, 11, 2], [0]],
            [[5, 4, 10, 4], [0]],  # roi and spectrum data partially aligned
        ],
        indirect=["make_snr_test_cases"],  # passing the parameters to a fixture
    )
    def test_calculate_snr(self, make_snr_test_cases, expected, mocker):
        spectrum_numpy = make_snr_test_cases["spectrum_numpy"]
        packet = make_snr_test_cases["packet"]
        detections = make_snr_test_cases["detections"]
        roi = make_snr_test_cases["roi"]

        original_detections, returned_detections = self.arrange_and_act_calculate_snr(
            packet, spectrum_numpy, detections, roi, mocker
        )
        if not isinstance(expected, list):
            expected = [expected]
        for i in range(len(expected)):
            assert returned_detections[i].snr == expected[i]

        # the key shouldn't change but values should change for the detection dict
        assert original_detections.keys() == returned_detections.keys()
        if 0 not in expected: 
            # 0 is the default value for protobuf float fields. 
            # If the correct SNR is not 0 then packets must have changed
            assert original_detections != returned_detections

    @pytest.mark.parametrize(
        "make_snr_test_cases",
        [
            # spectrum_no, detections_no, roi_center, roi_span, optional: spectrum_center_freq=15, spectrum_bandwidth=10
            # Single detection from ROI:
            [0, 0, 15, 2],
            [0, 0, 5, 2],  # roi outside of spectrum // shouldn't happen
            [0, 1, 15, 2],
            # Multiple detections from single ROI:
            [0, 2, 15, 2],
            [0, 3, 15, 2],
        ],
        indirect=["make_snr_test_cases"],  # passing the parameters to a fixture
    )
    def test_calculate_snr_no_spectrum(self, make_snr_test_cases, mocker):
        """
        Tests when calculate_snr doesn't receive a magnitude spectrum with the measurement packet.
        In this case the function should return early with the unchanged detection dictionary
        """
        spectrum_numpy = None
        packet = proto_data.Measurement()
        detections = make_snr_test_cases["detections"]
        roi = make_snr_test_cases["roi"]

        original_detections, returned_detections = self.arrange_and_act_calculate_snr(
            packet, spectrum_numpy, detections, roi, mocker
        )

        # the returned dictionary shouldn't be changed
        assert original_detections == returned_detections

    @pytest.mark.parametrize(
        "make_snr_test_cases",
        [
            # spectrum_no, detections_no, roi_center, roi_span, optional: spectrum_center_freq=15, spectrum_bandwidth=10
            # Single detection from ROI
            [0, 0, 15, 20],
            [1, 0, 5, 200],  # roi outside of spectrum // shouldn't happen
            [1, 1, 15, 10],
            [2, 0, 15, 20],
            # Multiple detections from single ROI:
            [0, 2, 15, 20],
            [0, 3, 5, 200],
        ],
        indirect=["make_snr_test_cases"],  # passing the parameters to a fixture
    )
    def test_calculate_snr_no_noise_bins(self, make_snr_test_cases, mocker):
        """
        When the ROI bandwidth covers the entire spectrum, the algorithm can't calculate ROI,
        so the detection packets should remain unchanged
        """
        spectrum_numpy = make_snr_test_cases["spectrum_numpy"]
        packet = make_snr_test_cases["packet"]
        detections = make_snr_test_cases["detections"]
        roi = make_snr_test_cases["roi"]

        original_detections, returned_detections = self.arrange_and_act_calculate_snr(
            packet, spectrum_numpy, detections, roi, mocker
        )

        # the returned dictionary shouldn't be changed
        assert original_detections == returned_detections
