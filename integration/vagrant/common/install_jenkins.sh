#!/bin/bash
# Installs Jenkins

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

wget -q -O - http://pkg.jenkins-ci.org/debian/jenkins-ci.org.key | sudo -E apt-key add -
sudo -E echo "deb http://pkg.jenkins-ci.org/debian binary/" > /etc/apt/sources.list.d/jenkins.list
sudo -E aptitude update
pkg_install jenkins
