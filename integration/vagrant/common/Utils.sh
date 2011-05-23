
exclaim () {
    echo "*******************************************************************************"
    echo "$@"
    echo "*******************************************************************************"
}

ip_chunk() {
    # Given 1-4 returns a bit of where the ip range starts.
    # Full IP= `ip_chunk 1`.`ip_chunk 2`.`ip_chunk 3`.`ip_chunk 4`
    ifconfig br100| grep 'inet addr:' | awk '{print $2} '| cut -d: -f2|cut -d. -f$@
}

pkg_install () {
    echo Installing $@...
    sudo -E DEBIAN_FRONTEND=noninteractive apt-get -y --allow-unauthenticated install $@
}

pkg_remove () {
    echo Uninstalling $@...
    sudo -E DEBIAN_FRONTEND=noninteractive apt-get -y --allow-unauthenticated remove $@
}
