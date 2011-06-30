#!/bin/bash
# Runs the host tests.
cd /src
# sudo find -name "*.pyc" -delete

cd /tests
sudo -E NOVASRC=/src /tests/run_tests_nv.sh --conf=/tests/vagrant/host/host.nemesis.conf --group=nova.volumes.driver
