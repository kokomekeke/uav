
import pysagax.message.command_pb2 as proto

cmd = proto.Command()
cmd.id = 1
cmd.instruction = proto.SOURCE_START
print(str(cmd.SerializeToString()))