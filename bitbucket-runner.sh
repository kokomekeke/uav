#!/bin/bash
set -euxo pipefail
PYENV_HOME=./.venv
LARGESHARE="/mnt/largeshare"
SETUP_DIST="./dist"
ARTIFACTS="./artifacts"
VCS_TAG=$(git rev-parse HEAD | head -c 12)

if [ -d $PYENV_HOME ]; then
    echo "no"
    rm -rf $PYENV_HOME
fi
if [ -d $SETUP_DIST ]; then
    rm -rf $SETUP_DIST
fi
mkdir -p $SETUP_DIST
if [ -d $ARTIFACTS ]; then
    rm -rf $ARTIFACTS
fi
python -m venv $PYENV_HOME
source $PYENV_HOME/bin/activate
$PYENV_HOME/bin/pip install -e .
$PYENV_HOME/bin/pip install .[test]
$PYENV_HOME/bin/pip install 'build<0.10.0'
# $PYENV_HOME/bin/pip install -r requirements.txt
$PYENV_HOME/bin/pytest
$PYENV_HOME/bin/python -m build
mkdir -p $ARTIFACTS
S_TARGET="$LARGESHARE/temp/pipelines/sgx-pc/$VCS_TAG"
cp ./dist/*.whl $ARTIFACTS
mkdir -p $S_TARGET
cp -r $ARTIFACTS/. $S_TARGET
