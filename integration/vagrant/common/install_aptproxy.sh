#!/bin/bash
# Installs an apt-proxy locally.

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

source Utils.sh

pkg_install apt-proxy

cp /vagrant-common/apt-proxy.conf /etc/apt-proxy/

service apt-proxy restart
