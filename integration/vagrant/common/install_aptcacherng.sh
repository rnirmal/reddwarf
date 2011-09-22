#!/bin/bash
# Installs apt-cacher-ng locally.

source /vagrant-common/Utils.sh

pkg_install apt-cacher-ng

echo 'Acquire::http { Proxy "http://10.0.4.15:3142"; };' | sudo tee /etc/apt/apt.conf.d/01proxy
echo "BindAddress: 10.0.4.15" | sudo tee -a /etc/apt-cacher-ng/acng.conf
sudo service apt-cacher-ng restart
sudo apt-get update
