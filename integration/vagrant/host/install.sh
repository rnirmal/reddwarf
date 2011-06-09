#!/bin/bash
# Builds packages.

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

source /vagrant-common/DbaasPkg.sh
source /vagrant-common/Utils.sh

exclaim "Deploying already built packages."
if [ -f ~/dependencies_are_installed ]
then
    dbaas_pkg_upload_release
    if [ $? -ne 0 ]; then exit 1; fi
else
    echo Dependencies are not installed.
    exit 1
fi
