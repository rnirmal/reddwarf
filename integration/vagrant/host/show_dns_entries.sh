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


cd /src
export PYTHONPATH=$PYTHONPATH:/src
python integration/show_dns_entries.py --flagfile=/home/vagrant/nova.conf