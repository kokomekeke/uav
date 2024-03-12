"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_sym_db = _symbol_database.Default()
from google.protobuf import timestamp_pb2 as google_dot_protobuf_dot_timestamp__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\ndata.proto\x1a\x1fgoogle/protobuf/timestamp.proto"\x9b\x04\n\tTelemetry\x12(\n\x04time\x18\x01 \x01(\x0b2\x1a.google.protobuf.Timestamp\x12\x11\n\tstream_id\x18\x02 \x01(\x07\x12%\n\x08hardware\x18\x05 \x01(\x0b2\x13.Telemetry.Hardware\x12!\n\x06source\x18\t \x01(\x0b2\x11.Telemetry.Source\x12\'\n\trecording\x18\n \x01(\x0b2\x14.Telemetry.Recording\x1aF\n\x08Hardware\x12\x11\n\tcpu_usage\x18\x01 \x01(\x02\x12\x12\n\ndisk_usage\x18\x02 \x01(\x03\x12\x13\n\x0btemperature\x18\x03 \x01(\x02\x1a\x86\x01\n\x06Source\x12(\n\x06status\x18\x03 \x01(\x0e2\x18.Telemetry.Source.Status\x12\x10\n\x08position\x18\x05 \x01(\x04\x12\x0e\n\x06length\x18\x06 \x01(\x04"0\n\x06Status\x12\x0c\n\x08DISABLED\x10\x00\x12\x0b\n\x07ENABLED\x10\x01\x12\x0b\n\x07RUNNING\x10\x02\x1a\x8c\x01\n\tRecording\x12+\n\x06status\x18\x01 \x01(\x0e2\x1b.Telemetry.Recording.Status\x12\x10\n\x08filename\x18\x02 \x01(\t\x12\x0e\n\x06length\x18\x03 \x01(\x04"0\n\x06Status\x12\x0c\n\x08DISABLED\x10\x00\x12\x0b\n\x07ENABLED\x10\x01\x12\x0b\n\x07RUNNING\x10\x02"\xa9\x01\n\tDetection\x12\x10\n\x08event_id\x18\x01 \x01(\r\x12\x0e\n\x06roi_id\x18\x06 \x01(\r\x12\x11\n\tfrequency\x18\x07 \x01(\x02\x12\x11\n\tbandwidth\x18\x08 \x01(\x02\x12\x10\n\x08strength\x18\t \x01(\x02\x12\x0f\n\x07azimuth\x18\n \x01(\x02\x12\x11\n\televation\x18\x0b \x01(\x02\x12\x0b\n\x03snr\x18\x0c \x01(\x02\x12\x11\n\tdeviation\x18\r \x01(\x02"\xeb\x01\n\x08Spectrum\x12\x12\n\nchannel_id\x18\x01 \x01(\x05\x12-\n\rspectrum_type\x18\x02 \x01(\x0e2\x16.Spectrum.SpectrumType\x12%\n\tdata_type\x18\x03 \x01(\x0e2\x12.Spectrum.DataType\x12\x0c\n\x04data\x18\x05 \x01(\x0c"9\n\x0cSpectrumType\x12\r\n\tMAGNITUDE\x10\x00\x12\x0b\n\x07AZIMUTH\x10\x01\x12\r\n\tELEVATION\x10\x02",\n\x08DataType\x12\t\n\x05INT16\x10\x00\x12\x08\n\x04INT8\x10\x01\x12\x0b\n\x07FLOAT32\x10\x05"\x80\x02\n\x0bMeasurement\x12(\n\x04time\x18\x01 \x01(\x0b2\x1a.google.protobuf.Timestamp\x12\x11\n\tstream_id\x18\x02 \x01(\r\x12\x11\n\tconfig_id\x18\x03 \x01(\r\x12\x11\n\tpacket_id\x18\x05 \x01(\x04\x12\x10\n\x08position\x18\x06 \x01(\x04\x12\x0f\n\x07heading\x18\x07 \x01(\x02\x12\x12\n\nquaternion\x18\x08 \x03(\x02\x12\x10\n\x08overflow\x18\t \x01(\x08\x12\r\n\x05peaks\x18\n \x03(\x05\x12\x17\n\x04data\x18\r \x03(\x0b2\t.Spectrum\x12\x1d\n\tdetection\x18\x11 \x03(\x0b2\n.Detection"\xdc\x01\n\x05Event\x12(\n\x04time\x18\x01 \x01(\x0b2\x1a.google.protobuf.Timestamp\x12\x11\n\tstream_id\x18\x02 \x01(\r\x12\x10\n\x08event_id\x18\x05 \x01(\r\x12\x11\n\tfrequency\x18\x06 \x01(\x02\x12\x10\n\x08strength\x18\x07 \x01(\x02\x12\x0b\n\x03lob\x18\x08 \x01(\x02\x12\x11\n\tcertainty\x18\t \x01(\x02\x12\x10\n\x08duration\x18\n \x01(\x02\x12-\n\tdetection\x18\x0b \x01(\x0b2\x1a.google.protobuf.Timestamp"\x96\x01\n\x10OperationalError\x12(\n\x04time\x18\x01 \x01(\x0b2\x1a.google.protobuf.Timestamp\x12)\n\x04type\x18\x02 \x01(\x0e2\x1b.OperationalError.ErrorType\x12\x13\n\x0bdescription\x18\x05 \x01(\t"\x18\n\tErrorType\x12\x0b\n\x07UNKNOWN\x10\x00"\xf9\x01\n\x06Packet\x12 \n\x04type\x18\x01 \x01(\x0e2\x12.Packet.PacketType\x12#\n\x0bmeasurement\x18\x05 \x01(\x0b2\x0c.MeasurementH\x00\x12\x1f\n\ttelemetry\x18\x06 \x01(\x0b2\n.TelemetryH\x00\x12\x17\n\x05event\x18\x07 \x01(\x0b2\x06.EventH\x00\x12"\n\x05error\x18\r \x01(\x0b2\x11.OperationalErrorH\x00"B\n\nPacketType\x12\x0f\n\x0bMEASUREMENT\x10\x00\x12\r\n\tTELEMETRY\x10\x01\x12\t\n\x05EVENT\x10\x02\x12\t\n\x05ERROR\x10\x08B\x06\n\x04datab\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'data_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_TELEMETRY']._serialized_start = 48
    _globals['_TELEMETRY']._serialized_end = 587
    _globals['_TELEMETRY_HARDWARE']._serialized_start = 237
    _globals['_TELEMETRY_HARDWARE']._serialized_end = 307
    _globals['_TELEMETRY_SOURCE']._serialized_start = 310
    _globals['_TELEMETRY_SOURCE']._serialized_end = 444
    _globals['_TELEMETRY_SOURCE_STATUS']._serialized_start = 396
    _globals['_TELEMETRY_SOURCE_STATUS']._serialized_end = 444
    _globals['_TELEMETRY_RECORDING']._serialized_start = 447
    _globals['_TELEMETRY_RECORDING']._serialized_end = 587
    _globals['_TELEMETRY_RECORDING_STATUS']._serialized_start = 396
    _globals['_TELEMETRY_RECORDING_STATUS']._serialized_end = 444
    _globals['_DETECTION']._serialized_start = 590
    _globals['_DETECTION']._serialized_end = 759
    _globals['_SPECTRUM']._serialized_start = 762
    _globals['_SPECTRUM']._serialized_end = 997
    _globals['_SPECTRUM_SPECTRUMTYPE']._serialized_start = 894
    _globals['_SPECTRUM_SPECTRUMTYPE']._serialized_end = 951
    _globals['_SPECTRUM_DATATYPE']._serialized_start = 953
    _globals['_SPECTRUM_DATATYPE']._serialized_end = 997
    _globals['_MEASUREMENT']._serialized_start = 1000
    _globals['_MEASUREMENT']._serialized_end = 1256
    _globals['_EVENT']._serialized_start = 1259
    _globals['_EVENT']._serialized_end = 1479
    _globals['_OPERATIONALERROR']._serialized_start = 1482
    _globals['_OPERATIONALERROR']._serialized_end = 1632
    _globals['_OPERATIONALERROR_ERRORTYPE']._serialized_start = 1608
    _globals['_OPERATIONALERROR_ERRORTYPE']._serialized_end = 1632
    _globals['_PACKET']._serialized_start = 1635
    _globals['_PACKET']._serialized_end = 1884
    _globals['_PACKET_PACKETTYPE']._serialized_start = 1810
    _globals['_PACKET_PACKETTYPE']._serialized_end = 1876