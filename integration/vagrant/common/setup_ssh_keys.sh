#!/bin/bash

sudo -E http_proxy=$http_proxy https_proxy=$https_proxy apt-get install -y --force-yes expect
# Setup the keys for the vagrant user
if [ ! -f /home/vagrant/.ssh/id_rsa.pub ]; then
    ssh-keygen -q -t rsa -N "" -f /home/vagrant/.ssh/id_rsa
    sudo ssh-keygen -q -t rsa -N "" -f /root/.ssh/id_rsa
fi

# Copy the public keys to the volume server
/vagrant-common/sshcopy.exp /home/vagrant/.ssh/id_rsa.pub
sudo /vagrant-common/sshcopy.exp /root/.ssh/id_rsa.pub
