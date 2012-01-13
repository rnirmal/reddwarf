#!/bin/bash

self="${0#./}"
base="${self%/*}"
current=`pwd`
if [ "$base" = "$self" ] ; then
    home=$current
elif [[ $base =~ ^/ ]]; then
    home="$base"
else
    home="$current/$base"
fi
cd $home
if [ -d $NOVASRC ]
then
    export PYTHONPATH=$PYTHONPATH:$NOVASRC
    #export PYTHONPATH=$PYTHONPATH:$NOVASRC/.nova-venv/lib/python2.6/site-packages
    if [ -d $NOVACLIENTSRC ]
    then
        echo Adding Nova Client.
        export PYTHONPATH=$PYTHONPATH:$NOVACLIENTSRC
    fi
    echo $PYTHONPATH
    export VENV_DIR=.nemesis-venv
    #        $VENV_DIR/bin/nosetests --verbose --with-id $arg
    python $INT_TEST_OPTIONS -B int_tests.py --verbose --verbose $*
else
    echo Please set NOVASRC to a Nova source tree.
fi


