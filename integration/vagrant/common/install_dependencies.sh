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
#UGLY(hub-cap): Fixing the nova.sh to use sudo's env setting (-E)
# check to see if http_proxy is set http_proxy=$http_proxy bash hack
if [ -n "${http_proxy+x}" ]; then
    exclaim Setting up proxy hotfix.
    PROXY_STR="http_proxy=$http_proxy https_proxy=$https_proxy"
    #escape out the /. chars that are present for the sed strin
    PROXY_STR=$(echo $PROXY_STR|sed 's/\([\/\.]\)/\\\1/g')
    SED_STR="s/sudo /sudo -E $PROXY_STR /g"
    sed -i.bak -e "$SED_STR" ./nova.sh
    SED_STR="s/wget /$PROXY_STR wget /g"
    sed -i.bak.delete -e "$SED_STR" ./nova.sh
fi
sudo -E http_proxy=$http_proxy https_proxy=$https_proxy bash ./nova.sh install
if [ -n "${http_proxy+x}" ]; then
    exclaim Reverting proxy hotfix.
    mv ./nova.sh.bak ./nova.sh
    rm ./nova.sh.bak.delete
fi

#TODO: Make this optional - its only there for OpenVZ environments.
exclaim Destroying virbr0.
pkg_remove user-mode-linux kvm libvirt-bin
sudo -E apt-get -y --allow-unauthenticated autoremove

sudo -E ifconfig virbr0 down
sudo -E brctl delbr virbr0


exclaim Installing additional Nova dependencies.

pkg_install mysql-server-5.1
pkg_install python-mysqldb

