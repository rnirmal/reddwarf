#!/bin/bash
# This is meant to be called from the volume box.

# Use the given key as our public key as well.
sudo bash /vagrant-common/ssh/add_key_to_host.sh

# Make the host authorized to log in
cat /vagrant-common/ssh/id_rsa.pub >> /home/vagrant/.ssh/authorized_keys
