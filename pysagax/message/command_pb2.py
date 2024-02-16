"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_sym_db = _symbol_database.Default()
from google.protobuf import timestamp_pb2 as google_dot_protobuf_dot_timestamp__pb2
from . import data_pb2 as data__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\rcommand.proto\x1a\x1fgoogle/protobuf/timestamp.proto\x1a\ndata.proto"S\n\x07ROIMask\x12\x0e\n\x06roi_id\x18\x01 \x01(\x05\x12\x18\n\x10center_frequency\x18\x05 \x01(\x02\x12\x0c\n\x04span\x18\x06 \x01(\x02\x12\x10\n\x08treshold\x18\x07 \x01(\x02"x\n\x07Heading\x12\x0c\n\x04type\x18\x01 \x01(\t\x12,\n\nparameters\x18\x02 \x03(\x0b2\x18.Heading.ParametersEntry\x1a1\n\x0fParametersEntry\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t:\x028\x01"\xb5\x02\n\x06Config\x12\x11\n\tconfig_id\x18\x01 \x01(\r\x12\x18\n\x10center_frequency\x18\x05 \x01(\x02\x12\x0f\n\x07iq_rate\x18\x06 \x01(\r\x12\x16\n\x0eplayback_speed\x18\x07 \x01(\x02\x12\x11\n\tbin_count\x18\x08 \x01(\x04\x12\x14\n\x0cburst_stride\x18\t \x01(\x04\x12\x14\n\x0cchannel_gain\x18\n \x03(\x05\x12\x13\n\x0bsource_path\x18\x11 \x01(\t\x12\x1a\n\x04type\x18\x12 \x01(\x0e2\x0c.Config.Type\x12\x15\n\x03roi\x18\x15 \x03(\x0b2\x08.ROIMask\x12\x19\n\x07heading\x18\x19 \x01(\x0b2\x08.Heading\x12\x13\n\x0bmean_window\x18\x1d \x01(\x02"\x1e\n\x04Type\x12\x08\n\x04LIVE\x10\x00\x12\x0c\n\x08RECORDED\x10\x01"\x82\x02\n\nSystemInfo\x12&\n\x08hardware\x18\x01 \x01(\x0b2\x14.SystemInfo.Hardware\x12&\n\x08software\x18\x02 \x01(\x0b2\x14.SystemInfo.Software\x12\x1a\n\x08headings\x18\x03 \x03(\x0b2\x08.Heading\x12\x1f\n\x06radios\x18\x04 \x03(\x0b2\x0f.SystemInfo.SDR\x1a\x18\n\x08Hardware\x12\x0c\n\x04disk\x18\x01 \x01(\x03\x1a7\n\x08Software\x12\x12\n\ncs_version\x18\x01 \x01(\t\x12\x17\n\x0fpysagax_version\x18\x02 \x01(\t\x1a\x14\n\x03SDR\x12\r\n\x05model\x18\x01 \x01(\t"\xe3\x01\n\x0cStreamTarget\x12\n\n\x02id\x18\x01 \x01(\x05\x12(\n\x05level\x18\x02 \x01(\x0e2\x19.StreamTarget.StreamLevel\x12\x0f\n\x07address\x18\x05 \x01(\t\x12\x0c\n\x04port\x18\x06 \x01(\x05\x12\x19\n\x11heartbeat_timeout\x18\t \x01(\x05\x12\x19\n\x11telemetry_timeout\x18\n \x01(\x05"H\n\x0bStreamLevel\x12\r\n\tHEARTBEAT\x10\x00\x12\r\n\tTELEMETRY\x10\x01\x12\r\n\tDETECTION\x10\x02\x12\x0c\n\x08SPECTRUM\x10\x03"\x8e\x01\n\x0cCommandError\x12(\n\x04time\x18\x01 \x01(\x0b2\x1a.google.protobuf.Timestamp\x12%\n\x04type\x18\x02 \x01(\x0e2\x17.CommandError.ErrorType\x12\x13\n\x0bdescription\x18\x05 \x01(\t"\x18\n\tErrorType\x12\x0b\n\x07UNKNOWN\x10\x00"\xaa\x01\n\x07Command\x12\n\n\x02id\x18\x01 \x01(\x05\x12!\n\x0binstruction\x18\x02 \x01(\x0e2\x0c.Instruction\x12\x13\n\tping_data\x18\x05 \x01(\tH\x00\x12\x19\n\x06config\x18\x06 \x01(\x0b2\x07.ConfigH\x00\x12\x12\n\x08position\x18\x07 \x01(\x04H\x00\x12\x1f\n\x06target\x18\x08 \x01(\x0b2\r.StreamTargetH\x00B\x0b\n\tparameter"\xf4\x01\n\x08Response\x12\n\n\x02id\x18\x01 \x01(\x05\x12!\n\x0binstruction\x18\x02 \x01(\x0e2\x0c.Instruction\x12\x1c\n\x05error\x18\x03 \x01(\x0b2\r.CommandError\x12\x11\n\x07success\x18\x05 \x01(\x08H\x00\x12\x13\n\tping_data\x18\x06 \x01(\tH\x00\x12\x19\n\x06config\x18\x07 \x01(\x0b2\x07.ConfigH\x00\x12\x1f\n\ttelemetry\x18\x08 \x01(\x0b2\n.TelemetryH\x00\x12\x1b\n\x04info\x18\t \x01(\x0b2\x0b.SystemInfoH\x00\x12\x12\n\x08position\x18\n \x01(\x04H\x00B\x06\n\x04data*\x9f\x02\n\x0bInstruction\x12\x08\n\x04PING\x10\x00\x12\n\n\x06CONFIG\x10\x01\x12\r\n\tTELEMETRY\x10\x02\x12\x08\n\x04INFO\x10\x03\x12\x0c\n\x08CS_START\x10\t\x12\x0b\n\x07CS_STOP\x10\n\x12\x0e\n\nCS_RESTART\x10\x0b\x12\x0b\n\x07CS_PING\x10\x0c\x12\x10\n\x0cSOURCE_START\x10\r\x12\x0f\n\x0bSOURCE_STOP\x10\x0e\x12\x0c\n\x08POSITION\x10\x0f\x12\r\n\tREC_START\x10\x11\x12\x0c\n\x08REC_STOP\x10\x12\x12\x11\n\rHEADING_START\x10\x15\x12\x10\n\x0cHEADING_STOP\x10\x16\x12\x13\n\x0fHEADING_RESTART\x10\x17\x12\x10\n\x0cSTREAM_START\x10\x19\x12\x0f\n\x0bSTREAM_STOP\x10\x1ab\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'command_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_HEADING_PARAMETERSENTRY']._loaded_options = None
    _globals['_HEADING_PARAMETERSENTRY']._serialized_options = b'8\x01'
    _globals['_INSTRUCTION']._serialized_start = 1638
    _globals['_INSTRUCTION']._serialized_end = 1925
    _globals['_ROIMASK']._serialized_start = 62
    _globals['_ROIMASK']._serialized_end = 145
    _globals['_HEADING']._serialized_start = 147
    _globals['_HEADING']._serialized_end = 267
    _globals['_HEADING_PARAMETERSENTRY']._serialized_start = 218
    _globals['_HEADING_PARAMETERSENTRY']._serialized_end = 267
    _globals['_CONFIG']._serialized_start = 270
    _globals['_CONFIG']._serialized_end = 579
    _globals['_CONFIG_TYPE']._serialized_start = 549
    _globals['_CONFIG_TYPE']._serialized_end = 579
    _globals['_SYSTEMINFO']._serialized_start = 582
    _globals['_SYSTEMINFO']._serialized_end = 840
    _globals['_SYSTEMINFO_HARDWARE']._serialized_start = 737
    _globals['_SYSTEMINFO_HARDWARE']._serialized_end = 761
    _globals['_SYSTEMINFO_SOFTWARE']._serialized_start = 763
    _globals['_SYSTEMINFO_SOFTWARE']._serialized_end = 818
    _globals['_SYSTEMINFO_SDR']._serialized_start = 820
    _globals['_SYSTEMINFO_SDR']._serialized_end = 840
    _globals['_STREAMTARGET']._serialized_start = 843
    _globals['_STREAMTARGET']._serialized_end = 1070
    _globals['_STREAMTARGET_STREAMLEVEL']._serialized_start = 998
    _globals['_STREAMTARGET_STREAMLEVEL']._serialized_end = 1070
    _globals['_COMMANDERROR']._serialized_start = 1073
    _globals['_COMMANDERROR']._serialized_end = 1215
    _globals['_COMMANDERROR_ERRORTYPE']._serialized_start = 1191
    _globals['_COMMANDERROR_ERRORTYPE']._serialized_end = 1215
    _globals['_COMMAND']._serialized_start = 1218
    _globals['_COMMAND']._serialized_end = 1388
    _globals['_RESPONSE']._serialized_start = 1391
    _globals['_RESPONSE']._serialized_end = 1635