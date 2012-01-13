#!/bin/bash

if [ $1 == "-v" ]
then
    USE_VENV=true
end
NOVA_SRC=../
export PYTHONPATH=$PYTHONPATH:$NOVASRC
if [ "$USE_VENV" == "True" ]; then
    export PYTHONPATH=$PYTHONPATH:$NOVASRC/.nova-venv/lib/python2.6/site-packages
fi
if [ -d $NOVACLIENTSRC ]
then
    echo Adding Nova Client.
    export PYTHONPATH=$PYTHONPATH:$NOVACLIENTSRC
fi
echo $PYTHONPATH
export VENV_DIR=.nemesis-venv
if [ "$USE_VENV" == "True" ]; then
    if [ -f .nemesis-venv/bin/nosetests ]
    then
    #        $VENV_DIR/bin/nosetests --verbose --with-id $arg
        $VENV_DIR/bin/python $INT_TEST_OPTIONS -B int_tests.py --verbose --verbose $*
    else
        echo Initialize venv for Nemesis by running "sudo python tools/install_venv.py"
    fi
fi
