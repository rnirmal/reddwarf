#!/bin/bash
# Runs the host tests.
cd /tests
sudo -E NOVASRC=/src/nova /tests/run_tests_nv.sh --conf=/tests/vagrant/host/host.nemesis.conf --group=dbaas.guest
