from __future__ import annotations
import numpy as np
import pysagax.message.data_pb2 as proto_data
import pysagax.message.command_pb2 as proto_cmd

from typing import ValuesView, Literal, Optional

PROTOBUF_NUMPY_TYPE_MAPPING: dict[proto_data.Spectrum.DataType.ValueType, np.dtype] = {
    proto_data.Spectrum.DataType.INT16: np.dtype(np.int16),
    proto_data.Spectrum.DataType.INT8: np.dtype(np.int8),
    proto_data.Spectrum.DataType.FLOAT16: np.dtype(np.float16),
    proto_data.Spectrum.DataType.FLOAT32: np.dtype(np.float32),
}


def protobuf_spectrum_to_numpy(spectrum: proto_data.Spectrum) -> np.ndarray:
    """
    Decoding a single spectrum data: returns the Spectrum.data as a numpy array.
    """
    np_data_type: np.dtype = PROTOBUF_NUMPY_TYPE_MAPPING[spectrum.data_type]
    spectrum_data = np.frombuffer(spectrum.data, np_data_type)
    return spectrum_data


def convert_iterable_to_spectrum_data(
    array: np.ndarray | list | ValuesView,
    dtype: proto_data.Spectrum.DataType.ValueType = proto_data.Spectrum.DataType.FLOAT32,
) -> bytes:
    """
    Converts numpy array, list or dict_values
    to bytes that can be added to proto_data.Spectrum.data.
    """
    array_np = np.array(array)
    # Changing float nan, inf and -inf values to integers
    if dtype in [proto_data.Spectrum.DataType.INT8, proto_data.Spectrum.DataType.INT16]:
        # numpy can't cast infinity to integer, so we change those to the maximum possible value
        np.clip(
            array_np,
            a_min=np.iinfo(PROTOBUF_NUMPY_TYPE_MAPPING[dtype]).min,
            a_max=np.iinfo(PROTOBUF_NUMPY_TYPE_MAPPING[dtype]).max,
            out=array_np,
        )
    return np.fromiter(array_np, PROTOBUF_NUMPY_TYPE_MAPPING[dtype]).tobytes()


def cast_spectrum_data_type(
    spectrum: proto_data.Spectrum,
    dtype: proto_data.Spectrum.DataType.ValueType,
    inplace: bool = False,
) -> Optional[proto_data.Spectrum]:
    """
    Converts the data field of a protobuf Spectrum message to the desired DataType.
    If inplace is True, the given spectrum is modified.
    If inplace is False, the given spectrum is unchanged, and a different spectrum message is returned
    """
    if inplace:
        working_spectrum = spectrum
    else:
        working_spectrum = proto_data.Spectrum()
        working_spectrum.CopyFrom(spectrum)

    if working_spectrum.data_type != dtype:
        # Don't do these steps if they're unnecessary
        data_np = protobuf_spectrum_to_numpy(spectrum)
        working_spectrum.data = convert_iterable_to_spectrum_data(data_np, dtype)
        working_spectrum.data_type = dtype

    if not inplace:
        return working_spectrum


def cast_all_spectrums_in_measurement(
    measurement: proto_data.Measurement,
    dtype=proto_data.Spectrum.DataType.ValueType,
    inplace: bool = False,
) -> Optional[proto_data.Measurement]:
    """
    Converts all the spectrums contained in a protbuf Measurement message to the desired DataType.
    If inplace is True, the given measurement is modified.
    If inplace is False, the given measurement is unchanged, and a new measurement packet is returned.
    """
    if inplace:
        working_measurement = measurement
    else:
        working_measurement = proto_data.Measurement()
        working_measurement.CopyFrom(measurement)
    for i in range(len(working_measurement.data)):
        cast_spectrum_data_type(working_measurement.data[i], dtype, inplace=True)
    if not inplace:
        return working_measurement


class Spectrum:
    """
    Class for efficiently handling spectrum data. Its main functionalities are:
        - Accessing spectrum bins by providing their frequency.
        - Accessing region of interest: slicing the spectrum by providing the low and high cutoff frequencies or a ROI mask

    Can be constructed from:
        - from numpy array (along with f_center and span)
        - proto_data.Spectrum object

    Objects of this class can be used with the indexing and slicing operator.
    The given values are treated as frequencies.
        Examples:
        >>> spectrum = Spectrum(data=[1,2,5,4,3], f_center=10, span=5)
        >>> spectrum[11]
        4
        >>> spectrum[11.4]
        4
        >>> spectrum[10:12]
        Spectrum{'data': array([5, 4, 3]), 'f_center': 11.0, 'span': 2.0}
        >>> roi = proto_cmd.ROIMask(center_frequency=8, span=3)
        >>> spectrum[roi]
        Spectrum{'data': array([1, 2]), 'f_center': 8.5, 'span': 1.0}

    Spectrum objects can be iterated over, the returned Iterator contains (frequency, value) pairs
        Example:
        >>> for bin_frequency, bin_value in spectrum:

    Objects of this class can be used with the numpy API. This is implemented by the __array__() method.
        Examples:
        >>> spectrum = Spectrum([1,2,5,4,3], f_center=10, span=5)
        >>> numpy.max(spectrum)
        5
        >>> numpy.argmax(spectrum)
        2
        >>> spectrum + numpy.array(10)
        array([11, 12, 15, 15, 13])

    """

    def __init__(self, data: np.ndarray | list, f_center: float, span: float) -> None:
        assert len(data)  # The class currently cant handle spectrums with 0 bins

        self.data = np.array(data)
        self.f_center = f_center
        self.span = span

        if len(self.data) == 1:
            # These values make sure that get_index_by_freq returns 0 for any frequency within the range of the spectrum if it only has 1 bin.
            self.f_start = self.f_center
            self.f_stop = self.f_center
            self.delta_f = self.span
        else:
            self.f_start = self.f_center - self.span / 2
            self.f_stop = self.f_center + self.span / 2
            self.delta_f = self.span / (len(self.data) - 1)

    @classmethod
    def from_proto_spectrum(cls, proto_spectrum: proto_data.Spectrum) -> Spectrum:
        """Creates Spectrum object from a protobuf message"""
        data = protobuf_spectrum_to_numpy(proto_spectrum)
        f_center = proto_spectrum.center_frequency
        span = proto_spectrum.bandwidth
        return Spectrum(data, f_center, span)

    def apply_roi(
        self, roi: proto_cmd.ROIMask, return_noise_bins: bool = False
    ) -> Spectrum | tuple[Spectrum, np.ndarray]:
        """
        Returns a spectrum which only cover the intersection of the Spectrum and the provided ROI mask. Throws an exception if the ROI and the Spectrum doesn't intersect

        Returns:
            If return_noise_bins is False: a Spectrum object
            If return_noise_bins is True: a tuple of a Spectrum object and an array containing the elements of self.data that were not included in the Spectrum object
        """
        roi_f_start = roi.center_frequency - roi.span / 2
        roi_f_stop = roi.center_frequency + roi.span / 2
        return self._get_spectrum_from_freq_range(
            roi_f_start, roi_f_stop, return_noise_bins
        )

    def _get_spectrum_from_freq_range(
        self,
        roi_f_start: Optional[float] = None,
        roi_f_stop: Optional[float] = None,
        return_noise_bins: bool = False,
    ) -> Spectrum | tuple[Spectrum, np.ndarray]:
        """
        Returns a spectrum which only cover the intersection of the Spectrum and the provided frequency range. Throws an exception if they don't intersect

        Args:
            roi_f_start: the lower frequency limit of the returned Spectrum
            roi_f_stop: the lower frequency limit of the returned Spectrum
            return_noise_bins: if true the method also returns the bins that were outside of the given frequency range

        Returns:
            If return_noise_bins is False: a Spectrum object
            If return_noise_bins is True: a tuple of a Spectrum object and an array containing the elements of self.data that were not included in the Spectrum object
        """
        # start and stop frequencies for the intersection of the ROI and spectrum:
        slice_f_start = (
            max(roi_f_start, self.f_start) if roi_f_start is not None else self.f_start
        )
        slice_f_stop = (
            min(roi_f_stop, self.f_stop) if roi_f_stop is not None else self.f_stop
        )
        if slice_f_start > slice_f_stop:
            raise IndexError("Supplied ROI is outside of the spectrum")

        # get the corresponding indices:
        start_index = self.get_index_from_freq(slice_f_start, rounding_mode="ceil")
        stop_index = self.get_index_from_freq(slice_f_stop, rounding_mode="floor")

        if start_index > stop_index:
            raise IndexError("Supplied ROI is narrower the the width of a single bin.")

        sliced_data = self.data[start_index : stop_index + 1]

        # Making sure the returned spectrum has exactly the same bin frequencies as the original:
        actual_slice_f_start = self.get_freq_from_index(start_index)
        actual_slice_f_stop = self.get_freq_from_index(stop_index)
        slice_center = (actual_slice_f_start + actual_slice_f_stop) / 2
        slice_span = actual_slice_f_stop - actual_slice_f_start
        if slice_span == 0:
            # the zoomed spectrum contains only 1 bin -> set span to bin width
            slice_span = self.delta_f

        spectrum = Spectrum(sliced_data, slice_center, slice_span)
        if return_noise_bins:
            noise_bins = np.concatenate(
                (self.data[:start_index], self.data[stop_index + 1 :])
            )
            return spectrum, noise_bins
        return spectrum

    def get_freq_from_index(self, index: int) -> float:
        """Returns the bin frequency for the given bin index"""
        # start + index * step = frequency
        if index < 0 or len(self.data) <= index:
            raise IndexError("index is out of range")
        return self.f_start + index * self.delta_f

    def get_index_from_freq(
        self,
        frequency: float,
        rounding_mode: Literal["round", "ceil", "floor"] = "round",
    ) -> int:
        """
        Returns the bin index for the given bin frequency.

        Rounding mode (used in Spectrum.get_spectrum_from_freq_range()):
            -round: the returned index is the closest bin to the given frequency
            -ceil: the closest index that's higher than the given frequency
            -floor: the closest index that's lower than the given frequency

        """
        assert len(self.data) > 0

        # start + index * step = frequency
        index = (frequency - self.f_start) / self.delta_f
        match rounding_mode:
            case "round":
                index = int(round(index))
            case "ceil":
                index = int(np.ceil(index))
            case "floor":
                index = int(np.floor(index))

        if index < 0 or len(self.data) <= index:
            raise ValueError(
                f"requested frequency ({frequency}) is outside of Spectrum object's range (f_center={self.f_center}, span={self.span})"
            )
        return index

    def get_value_from_freq(self, frequency: float) -> float | int:
        """
        Returns the value of the bin closest to the given frequency
        You can use the indexing operator instead of this method:
        >>> spectrum[frequency]
        """
        index = self.get_index_from_freq(frequency)
        return self.data[index]

    def get_value_from_index(self, index: int) -> float | int:
        """Returns the value of the bin with the given index"""
        return self.data[index]

    def __array__(self, dtype=None):
        """
        Providing an interface for the numpy API.
        Documentation: https://numpy.org/doc/stable/user/basics.dispatch.html
        """
        return np.array(self.data, dtype=dtype)

    def __getitem__(self, value):
        """
        Overloading slicing and indexing operators. See the class docstring for examples.
        """
        if isinstance(value, slice):
            if value.step is not None:
                raise IndexError("Spectrum slicing does not support step size.")
            return self._get_spectrum_from_freq_range(value.start, value.stop)
        elif isinstance(value, (int, float)):
            return self.get_value_from_freq(value)
        elif isinstance(value, proto_cmd.ROIMask):
            return self.apply_roi(value)
        raise IndexError("")

    def __iter__(self):
        """Returns an iterator for (frequency, value) pairs"""
        freqs = np.linspace(self.f_start, self.f_stop, len(self.data))
        return zip(freqs, self.data)
