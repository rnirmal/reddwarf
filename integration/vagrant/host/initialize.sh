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

# Remove ip routing from br200
sudo ip route del default via 10.0.4.2

if [ -f ~/dependencies_are_installed ]
then
    echo Dependencies are already installed.
else
    exclaim 'Installing SSH key.'
    /vagrant-common/setup_ssh_keys.sh

    exclaim 'Installing Dependencies...'
    sudo usermod -g root vagrant
    sudo -E http_proxy=$http_proxy https_proxy=$https_proxy bash /vagrant-common/install_dependencies.sh
    if [ $? -ne 0 ]
    then
        echo "An error occured installing dependencies."
        exit 1
    fi

    sudo -E http_proxy=$http_proxy https_proxy=$https_proxy bash /vagrant-common/install_apt_repo.sh
    if [ $? -ne 0 ]
    then
        echo "An error occured installing the repo."
        exit 1
    fi

    sudo -E http_proxy=$http_proxy https_proxy=$https_proxy bash /vagrant-common/install_aptproxy.sh
    if [ $? -ne 0 ]
    then
        echo "An error occured installing the aptproxy."
        exit 1
    fi

    pkg_install python-sphinx python-cheetah python-pastedeploy python-migrate python-netaddr python-lockfile python-pip

    # The default version of pip Ubuntu installs is old.
    sudo pip install --upgrade pip
    #sudo pip install proboscis==1.0.1
    sudo pip install http://pypi.python.org/packages/source/p/proboscis/proboscis-1.1.1.tar.gz

    cp /etc/hosts ~/hosts_tmp
    echo '127.0.0.1    apt.rackspace.com' >> ~/hosts_tmp
    echo '127.0.0.1    ppa.rackspace.com' >> ~/hosts_tmp
    sudo -E cp ~/hosts_tmp /etc/hosts

    echo "Dependencies installed at `date`." >> ~/dependencies_are_installed

fi



