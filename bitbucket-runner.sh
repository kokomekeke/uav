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

$PYENV_HOME/bin/python -m pip install --upgrade pip
$PYENV_HOME/bin/python -m pip uninstall -y setuptools
$PYENV_HOME/bin/python -m pip install -U setuptools
$PYENV_HOME/bin/python -m pip install 'build<0.10.0'
$PYENV_HOME/bin/python -m pip install versioneer wheel
# $PYENV_HOME/bin/pip install -r requirements.txt
$PYENV_HOME/bin/python -m build --wheel --no-isolation
$PYENV_HOME/bin/python -m pip install $SETUP_DIST/*.whl
$PYENV_HOME/bin/python -m pip install black mypy pytest pytest-cov pytest-mock
$PYENV_HOME/bin/pytest
mkdir -p $ARTIFACTS
S_TARGET="$LARGESHARE/temp/pipelines/sgx-pc/$VCS_TAG"
if [[ -d $S_TARGET ]]; then
	rm -r $S_TARGET
fi
cp $SETUP_DIST/*.whl $ARTIFACTS
mkdir -p $S_TARGET
cp -r $ARTIFACTS/. $S_TARGET
