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

exclaim "Building and installing packages."
if [ -f ~/dependencies_are_installed ]
then
    rm -rf /tmp/build
    mkdir /tmp/build
    dbaas_pkg_install_release_novaclient
    if [ $? -ne 0 ]; then exit 1; fi
    dbaas_pkg_install_nova
    if [ $? -ne 0 ]; then exit 1; fi
    dbaas_pkg_install_dbaasmycnf
    if [ $? -ne 0 ]; then exit 1; fi
    dbaas_pkg_install_firstboot
    if [ $? -ne 0 ]; then exit 1; fi
    dbaas_pkg_install_glance
    if [ $? -ne 0 ]; then exit 1; fi
    dbaas_pkg_setup_keystone
    if [ $? -ne 0 ]; then exit 1; fi
else
    echo Dependencies are not installed.
    exit 1
fi
