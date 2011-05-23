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
#UGLY(hub-cap): Fixing the nova.sh to use sudo's env setting (-E)
# check to see if http_proxy is set http_proxy=$http_proxy bash hack
if [ -n "${http_proxy+x}" ]; then
  sed -i.bak 's/;http_proxy/http_proxy/g' /etc/apt-proxy/apt-proxy.conf
fi

service apt-proxy restart
