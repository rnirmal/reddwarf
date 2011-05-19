#!/bin/bash
# Initializes the Host VM.  Meant to be called un a bare-bones environment.

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

if [ -f ~/dependencies_are_installed ]
then
    echo Dependencies are already installed.
else
    exclaim 'Installing Dependencies...'
    sudo usermod -g root vagrant
    sudo -E bash /vagrant-common/install_dependencies.sh
    if [ $? -ne 0 ]
    then
        echo "An error occured installing dependencies."
        exit 1
    fi

    sudo -E bash /vagrant-common/install_apt_repo.sh
    if [ $? -ne 0 ]
    then
        echo "An error occured installing the repo."
        exit 1
    fi

    sudo -E bash /vagrant-common/install_aptproxy.sh
    if [ $? -ne 0 ]
    then
        echo "An error occured installing the aptproxy."
        exit 1
    fi

    pkg_install python-sphinx python-cheetah python-pastedeploy python-migrate python-netaddr python-lockfile

    cp /etc/hosts ~/hosts_tmp
    echo '127.0.0.1    apt.rackspace.com' >> ~/hosts_tmp
    echo '127.0.0.1    ppa.rackspace.com' >> ~/hosts_tmp
    sudo -E cp ~/hosts_tmp /etc/hosts

    #sudo -E bash /vagrant-common/initialize_nova.sh
    #if [ $? -ne 0 ]
    #then
    #    echo "An error occured initializing nova."
    #    exit 1
    #fi

    echo "Dependencies installed at `date`." >> ~/dependencies_are_installed

fi



