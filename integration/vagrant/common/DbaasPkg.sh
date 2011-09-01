#!/bin/bash
# Handles building and installing our packages.

#on the container, in /etc/apt/sources.list
#deb http://10.0.2.15/ubuntu lucid main

source /vagrant-common/Utils.sh
source /vagrant-common/Exports.sh

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
        dbaas_trunk_install_glance
    fi

    sudo -E mkdir /glance_images/
    # Check to see if the glance images folder has files in it
    if [ `ls /glance_images/|wc -l` == '0' ]
    then
        # If there are no files then we should curl the ovz image to the glance images folder
        sudo -E curl http://c629296.r96.cf2.rackcdn.com/ubuntu-10.04-x86_64-openvz.tar.gz --output /glance_images/ubuntu-10.04-x86_64-openvz.tar.gz
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

dbaas_pkg_setup_keystone() {
    # Download keystone and setup
    sudo rm -rf /keystone
    sudo -E git clone https://github.com/openstack/keystone.git /keystone
    cd /keystone
    sudo git checkout -b stable $KEYSTONE_VERSION

    # Apply any patches if necessary
    sudo git am -3 /vagrant-common/patches/keystone/*

    # Install Dependenciens
    pkg_install python-eventlet python-lxml python-paste python-pastedeploy python-pastescript python-pysqlite2
    pkg_install python-sqlalchemy python-webob python-routes python-httplib2 python-memcache

    KEYSTONE_CONF="/etc/keystone/keystone.conf"
    sudo -E python setup.py install
    sudo -E mkdir -p /etc/keystone
    sudo -E mkdir -p /var/log/keystone
    sudo -E cp /vagrant/keystone.conf $KEYSTONE_CONF
}

dbaas_pkg_install_novaclient() {
    # Builds and installs the novaclient based on a config'd version
    pkg_remove python-novaclient
    sudo -E mkdir -p /tmp/build/
    sudo -E rm -fr /tmp/build/python-novaclient
    sudo -E rm -fr /tmp/build/python-novapkg
    # PYTHON_NOVACLIENT_VERSION is sourced from Exports
    sudo -E http_proxy=$http_proxy https_proxy=$https_proxy bzr clone lp:python-novaclient -r $PYTHON_NOVACLIENT_VERSION /tmp/build/python-novaclient
    sudo -E http_proxy=$http_proxy https_proxy=$https_proxy bzr checkout --lightweight lp:ubuntu/natty/python-novaclient /tmp/build/python-novapkg
    sudo -E mv /tmp/build/python-novapkg/debian /tmp/build/python-novaclient
    pkg_install cdbs python-mock
    cd /tmp/build/python-novaclient
    sudo -E sed -i.bak -e 's/ natty;/ lucid;/g' debian/changelog
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
    sudo -E rm -fr /etc/apt/sources.list.d/temp-local-ppa-lucid.list
    sudo -E apt-get update
}

dbaas_trunk_install_glance() {
    sudo -E add-apt-repository ppa:glance-core/trunk
    sudo -E apt-get update
    sudo -E apt-get install glance
    
    sudo -E service glance-registry stop
    sudo -E service glance-api stop
}

dbaas_new_install_glance() {
    # Builds and installs glance based on a config'd version
    pkg_remove glance
    pkg_remove python-glance
    sudo -E mkdir -p /tmp/build/
    sudo -E rm -fr /tmp/build/glance*
    sudo -E rm -fr /tmp/build/python-glance*
    # GLANCE_VERSION is sourced from Exports
    # sudo -E http_proxy=$http_proxy https_proxy=$https_proxy bzr clone lp:glance -r $GLANCE_VERSION /tmp/build/glance
    sudo -E git clone https://github.com/openstack/glance.git /tmp/build/glance
    cd /tmp/build/glance
    sudo git checkout -b stable $GLANCE_VERSION
    sudo -E http_proxy=$http_proxy https_proxy=$https_proxy bzr checkout --lightweight lp:~openstack-ubuntu-packagers/ubuntu/natty/glance/ubuntu /tmp/build/glancepkg
    sudo -E mv /tmp/build/glancepkg/debian /tmp/build/glance
    pkg_install cdbs python-mock

    sudo -E sed -i.bak -e 's/ natty;/ lucid;/g' debian/changelog
    # for some reason glance needs swift core to build
    add-apt-repository ppa:swift-core/trunk
    sudo -E apt-get update
    pkg_install python-swift
    if [ ! -f /tmp/build/glance/etc/glance.conf.sample ]
    then
        echo " " | sudo -E tee /tmp/build/glance/etc/glance.conf.sample
    fi
    #Stop the tests from running in the build since they are FLAKY
    echo "" | sudo -E tee run_tests.sh > /dev/null
    sudo -E DEB_BUILD_OPTIONS=nocheck,nodocs dpkg-buildpackage -rfakeroot -b -uc -us
    pkg_remove python-swift
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid glance
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid python-glance
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid python-glance-doc
    cd /tmp/build
    sudo -E reprepro --ignore=wrongdistribution -Vb /var/www/ubuntu/ include lucid glance*.changes
    # Add the local apt repo temporarily to install the built glance
    echo "deb http://0.0.0.0/ubuntu lucid main" | sudo -E tee /etc/apt/sources.list.d/temp-local-ppa-lucid.list > /dev/null
    echo "Package: glance
Pin: origin 0.0.0.0
Pin-Priority: 700

Package: python-glance
Pin: origin 0.0.0.0
Pin-Priority: 700" | sudo -E tee /etc/apt/preferences.d/temp-local-ppa-pin > /dev/null
    sudo -E apt-get update
    # Based on the pin this will install the glance we just built
    pkg_install glance
    # now clean up that mess so it doesnt pollute into any other installations
    sudo -E rm -fr /etc/apt/preferences.d/temp-local-ppa-pin
    sudo -E rm -fr /etc/apt/sources.list.d/temp-local-ppa-lucid.list
    sudo -E apt-get update
    
    #Now that its installed lets change the db for it and stop the services
    sudo -E service glance-registry stop
    sudo -E service glance-api stop
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
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-compute-kvm
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-compute-lxc
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-compute-uml
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-compute-xen
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-doc
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-dns
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-guest
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-network
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-objectstore
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-scheduler
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-volume
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid nova-vncproxy
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid reddwarf-api
    sudo -E reprepro -Vb /var/www/ubuntu/ remove lucid python-nova


    echo Installing Nova packages into the local repo.
    cd /tmp/build
    sudo -E reprepro --ignore=wrongdistribution -Vb /var/www/ubuntu/ include lucid nova_2012.12~`echo $gitversion`_amd64.changes
    sudo service glance-api stop
    sudo service glance-registry stop
    echo "Finished installing nova"
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
