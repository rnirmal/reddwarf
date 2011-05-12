# Host Environment Initializer - Dependency Installer
# This file is meant to be run in a VM or otherwise disposable environment.
# It installs all the dependencies needed by Nova.

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


exclaim () {
    echo "*******************************************************************************"
    echo "$@"
    echo "*******************************************************************************"
}



pkg_install python-software-properties

exclaim Installing Nova dependencies.
cd /src/contrib
sudo ./nova.sh install

#TODO: Make this optional - its only there for OpenVZ environments.
exclaim Destroying virbr0.
pkg_remove user-mode-linux kvm libvirt-bin
sudo apt-get -y --allow-unauthenticated autoremove

sudo ifconfig virbr0 down
sudo brctl delbr virbr0


exclaim Installing additional Nova dependencies.

pkg_install mysql-server-5.1
pkg_install python-mysqldb

