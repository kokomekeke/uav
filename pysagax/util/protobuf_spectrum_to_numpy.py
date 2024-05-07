import numpy as np
import pysagax.message.data_pb2 as proto_data

PROTOBUF_NUMPY_TYPE_MAPPING: dict[proto_data.Spectrum.DataType.ValueType, np.dtype] = {
    proto_data.Spectrum.DataType.INT16: np.dtype(np.int16),
    proto_data.Spectrum.DataType.INT8: np.dtype(np.int8),
    proto_data.Spectrum.DataType.FLOAT32: np.dtype(np.float32),
}


def protobuf_spectrum_to_numpy(spectrum: proto_data.Spectrum) -> np.ndarray:
    """
    Decoding a single spectrum data: returns the Spectrum.data as a numpy array.
    """
    np_data_type: np.dtype = PROTOBUF_NUMPY_TYPE_MAPPING[spectrum.data_type]
    spectrum_data = np.frombuffer(spectrum.data, np_data_type)
    return spectrum_data
