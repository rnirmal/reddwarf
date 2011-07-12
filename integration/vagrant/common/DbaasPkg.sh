#!/bin/bash
# Handles building and installing our packages.

#on the container, in /etc/apt/sources.list
#deb http://10.0.2.15/ubuntu lucid main

source /vagrant-common/Utils.sh

dbaas_pkg_create_tmpbuild() {
    if [ -d /tmp/build ]
    then
        echo /tmp/build already exists.
    else
        sudo -E mkdir /tmp/build
    fi
}


dbaas_pkg_install_dbaasmycnf() {
    # Builds and installs dbaasmycnf package.

    dbaas_pkg_create_tmpbuild
    sudo -E cp -R /src/dbaas-mycnf /tmp/build/dbaas
    cd /tmp/build/dbaas
    sudo -E ./dbaas-mycnf/builddeb.sh
    #remove the old version in case this is a 2nd run
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid dbaas-mycnf
    sudo -E reprepro --ignore=wrongdistribution -Vb /var/www/ubuntu/ includedeb lucid dbaas-mycnf/*.deb
}

dbaas_pkg_install_firstboot() {
    # Builds and installs firstboot package.

    dbaas_pkg_create_tmpbuild
    sudo -E cp -R /src/firstboot /tmp/build/dbaas
    cd /tmp/build/dbaas
    sudo -E ./firstboot/builddeb.sh
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid firstboot
    sudo -E reprepro --ignore=wrongdistribution -Vb /var/www/ubuntu/ includedeb lucid firstboot/*.deb
}

dbaas_pkg_install_glance() {
    # Check if glance is package installed or not by
    # just checking if the 'known' glance setup.py exists.
    if [ -d /glance -a -f /glance/setup.py ]
    then
        dbaas_old_install_glance
    else
        # add the trunk ppa and install it
        sudo -E add-apt-repository ppa:glance-core/trunk
        sudo -E apt-get update
        pkg_install glance
        sudo sed -i 's/sql_connection = sqlite:\/\/\/\/var\/lib\/glance\/glance.sqlite/sql_connection = mysql:\/\/nova:novapass@localhost\/glance/g' /etc/glance/glance-registry.conf
        sudo -E service glance-registry restart
        sudo -E service glance-api restart
    fi

    mkdir -p /glance_images/
    # Check to see if the glance images folder has files in it
    if [ `ls /glance_images/|wc -l` == '0' ]
    then
        # If there are no files then we should curl the ovz image to the glance images folder
        curl http://c629296.r96.cf2.rackcdn.com/ubuntu-10.04-x86_64-openvz.tar.gz --output /glance_images/ubuntu-10.04-x86_64-openvz.tar.gz
    fi
}

dbaas_old_install_glance() {
    # The old way of installing glance
    sudo rm -rf ~/glance
    sudo cp -rf /glance ~/glance
    if [ $? -ne 0 ]
    then
        echo "Failure to copy glance to temporary location."
        exit 1
    fi
    cd ~/glance
    sudo python setup.py install
    if [ $? -ne 0 ]
    then
        echo "Failure to install glance."
        exit 1
    fi
}

dbaas_pkg_install_novaclient() {
    # Builds and installs the novaclient based on a config'd version
    pkg_remove python-novaclient
    sudo -E mkdir -p /tmp/build/
    sudo -E rm -fr /tmp/build/python-novaclient
    sudo -E rm -fr /tmp/build/python-novapkg
    # PYTHON_NOVACLIENT_VERSION is sourced from Utils
    sudo -E http_proxy=$http_proxy https_proxy=$https_proxy bzr clone lp:python-novaclient -r $PYTHON_NOVACLIENT_VERSION /tmp/build/python-novaclient
    sudo -E http_proxy=$http_proxy https_proxy=$https_proxy bzr checkout --lightweight lp:ubuntu/natty/python-novaclient /tmp/build/python-novapkg
    sudo -E mv /tmp/build/python-novapkg/debian /tmp/build/python-novaclient
    pkg_install cdbs python-mock
    cd /tmp/build/python-novaclient
    sed -i.bak -e 's/ natty;/ lucid;/g' debian/changelog
    sudo -E DEB_BUILD_OPTIONS=nocheck,nodocs dpkg-buildpackage -rfakeroot -b -uc -us
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid python-novaclient
    cd /tmp/build
    sudo -E reprepro --ignore=wrongdistribution -Vb /var/www/ubuntu/ include lucid python-novaclient_2.4-0ubuntu1_amd64.changes
    # Add the local apt repo temporarily to install the built novaclient
    echo "deb http://0.0.0.0/ubuntu lucid main" | sudo -E tee /etc/apt/sources.list.d/temp-local-ppa-lucid.list > /dev/null
    echo "Package: python-novaclient
Pin: origin 0.0.0.0
Pin-Priority: 700" | sudo -E tee /etc/apt/preferences.d/temp-local-ppa-pin > /dev/null
    sudo -E apt-get update
    # Based on the pin this will install the novaclient we just built
    pkg_install python-novaclient
    # now clean up that mess so it doesnt pollute into any other installations
    sudo -E rm -fr /etc/apt/preferences.d/temp-local-ppa-pin
    sudo -E rm -fr /tmp/build/python-nova*
    sudo -E rm -fr /etc/apt/sources.list.d/temp-local-ppa-lucid.list
    sudo -E apt-get update
}

dbaas_pkg_install_nova() {
    # Builds and installs all of the stuff for Nova.

    dbaas_pkg_create_tmpbuild

    echo Building Nova packages...
    sudo -E http_proxy=$http_proxy https_proxy=$https_proxy bash /vagrant-common/nova_builddeb.sh
    if [ $? -ne 0 ]
    then
        echo "Failure to build Nova package."
        exit 1
    fi

    gitversion=`cat /tmp/build/dbaas/_version.txt`

    echo Removing old versions of the packages in case this is a 2nd run.
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-ajax-console-proxy
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-api
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-common
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-compute
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-doc
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-dns
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-guest
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-instancemonitor
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-network
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-objectstore
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-scheduler
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-volume
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid reddwarf-api
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid python-nova


    echo Installing Nova packages into the local repo.
    cd /tmp/build
    sudo -E reprepro --ignore=wrongdistribution -Vb /var/www/ubuntu/ include lucid nova_`echo $gitversion`_amd64.changes
}

dbaas_pkg_install_rsdns() {
    if [ -d /rsdns ]
    then
        echo Installing RS DNS.
        sudo rm -rf ~/rsdns
        echo Creating temporary copy.
        sudo cp -rf /rsdns ~/rsdns
        if [ $? -ne 0 ]
        then
            echo "Could not copy RSDNS directory to temporary local location."
            exit 1
        fi
        echo Installing RSDNS.
        cd /home/vagrant/rsdns
        sudo python setup.py install
        if [ $? -ne 0 ]
        then
            echo "Failure to install RSDNS."
            exit 1
        fi
        echo Installed successfully.
    else
        echo "Not installing RS DNS because it wasn't found."
    fi
}

dbaas_pkg_upload_release() {
    # Installs the release. Assumes the /tmp/build stuff is already done and exists
    cd /tmp/build/dbaas
    gitversion=`cat /tmp/build/dbaas/_version.txt`
    output=`grep 'BEGIN PGP SIGNED MESSAGE' /tmp/build/nova_${gitversion}_amd64.changes|wc -l`
    if [ $output == 0 ]
    then
      echo "signing packages"
      sudo -E debsign /tmp/build/nova_`echo $gitversion`_amd64.changes
    fi
    sudo -E dupload -f --to nova /tmp/build/nova_`echo $gitversion`_amd64.changes
}
