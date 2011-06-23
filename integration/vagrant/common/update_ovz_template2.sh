#!/bin/bash
# Initialize directories
echo Creating OVZ template work directories...
rm -rf ~/temp_ovz
rm -rf ~/glance_images

mkdir ~/temp_ovz
mkdir ~/glance_images
cd ~/temp_ovz
cp /glance_images/ubuntu-10.04-x86_64-openvz.tar.gz ~/glance_images/ubuntu-10.04-x86_64-openvz.tar.gz
