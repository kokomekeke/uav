# Compilation
In order to work properly with relative imports, .proto files should be compiled first with protoc, then protoletariat (available through pip)

From sgx-pc root:
    protoc --python_out=./pysagax/message --proto_path=./message ./message/data.proto ./message/command.proto

    # protol --create-package --in-place --python-out ./pysagax/message protoc --proto-path=./message ./message/data.proto ./message/command.proto