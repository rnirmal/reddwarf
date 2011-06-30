#!/bin/bash
# Called on the volumes VM

echo "Deleting volumes."
sudo service iscsitarget restart
sudo rm -rf /san/*
echo "Finished deleting volumes."
