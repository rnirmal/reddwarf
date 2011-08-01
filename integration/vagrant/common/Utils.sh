#!/bin/bash

exclaim () {
    echo "*******************************************************************************"
    echo "$@"
    echo "*******************************************************************************"
}

fail_if_exists () {
    if [ -d $1 ] || [ -f $1 ]
    then
        echo The Nova cert file or directory $1 already exists. Aborting.
        exit 1
    fi
}

ip_chunk() {
    # Given 1-4 returns a bit of where the ip range starts.
    # Full IP= `ip_chunk 1`.`ip_chunk 2`.`ip_chunk 3`.`ip_chunk 4`
    get_ip_for_device $1 | cut -d. -f$2
}

pkg_install () {
    echo Installing $@...
    sudo -E DEBIAN_FRONTEND=noninteractive apt-get -y --allow-unauthenticated install $@
}

pkg_remove () {
    echo Uninstalling $@...
    sudo -E DEBIAN_FRONTEND=noninteractive apt-get -y --allow-unauthenticated remove $@
}

get_ip_for_device() {
    ifconfig $1 | awk '/inet addr/{gsub(/addr:/,"");print $2}'
}
