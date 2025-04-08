#!/bin/bash
# Requires protoc 

sources=(
    "pysagax/message/command.proto" 
    "pysagax/message/data.proto" 
    "pysagax/message/heading.proto" 
    "pysagax/message/flight_info.proto"
    "pysagax/message/altiss_intra_uav.proto"
)
target=$(dirname $(dirname $(dirname "${BASH_SOURCE[0]}")))  # project root dir
set -x
for i in "${sources[@]}"
do
    echo "Compiling $i"

    echo "  Running protoc"
    protoc --python_out=$target --mypy_out=$target  --proto_path=$target $target/$i

    # echo "  Running protoletariat"
    # protol --create-package --in-place --python-out=$target protoc --proto-path=$target $i
done
