#!/bin/bash
# Requires protoc and protoletariat

sources=("command.proto" "data.proto")
target=$(dirname "${BASH_SOURCE[0]}")

for i in "${sources[@]}"
do
    echo "Compiling $i"

    echo "  Running protoc"
    protoc --proto_path=$target --python_out=$target $i

    echo "  Running protoletariat"
    protol --create-package --in-place --python-out=$target protoc --proto-path=$target $i
done