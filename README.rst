=====================================================
Reddwarf (Database As A Service)
=====================================================

-------
Preface
-------

Reddwarf is extending the OpenStack Nova to enable Database as a
Service.

Get more information and get involved with the OpenStack community.

* http://openstack.org/
* http://openstack.org/community/
* https://github.com/openstack/nova

-----------------------------
Getting Started
-----------------------------

The information below is set to be run on a VM. Inside this folder
is a file called 'VagrantFile'. This is a script that runs with Vagrant
(http://www.vagrantup.com) and VirtualBox (http://www.virtualbox.org/).

#. Create a new Folder::

    [nix:~]$ mkdir ~/dev
    [nix:~]$ cd ~/dev

#. (Requried) Download the openvz glance image from::

    [nix:~/dev]$ mkdir ~/dev/glanceimg
    [nix:~/dev]$ cd ~/dev/glanceimg
    [nix:~/dev/glanceimg]$ wget http://c629296.r96.cf2.rackcdn.com/ubuntu-10.04-x86_64-openvz.tar.gz

#. (Optional) Install bzr if not already installed::

    [nix:~]$ cd ~/dev
    [linux:~/dev]$ sudo apt-get install bzr     (install ubuntu)
    [mac:~/dev]$ sudo port install bzr          (install mac via macports)
    [mac:~/dev]$ brew install bzr               (install mac via homebrew)

#. (Optional) Check out the latest Glance source::

    [nix:~/dev]$ bzr branch lp:glance

#. (Required) Define the environment variables to the path to launchpad trunk
   of glance (the bzr checkout folder) and the glance images (path to directory 
   of ubuntu-10.04-x86_64-openvz.tar.gz)::

    [nix:~/dev]$ echo "export GLANCESRC=~/dev/glance" >> ~/.bashrc
    [nix:~/dev]$ echo "export GLANCEIMAGES=~/dev/glanceimg" >> ~/.bashrc
    [nix:~/dev]$ . ~/.bashrc

#. Fresh check out from github.::

    [nix:~/dev]$ git clone git://github.com/rackspace/reddwarf.git

#. (Optional) If you want to get the latest changes from the git repository
   on github.com::

    [nix:~/dev]$ cd ~/dev/reddwarf
    [nix:~/dev/reddwarf]$ git pull

#. Enter the directory reddwarf/integration/vagrant/host::

    [nix:~/dev]$ cd reddwarf/integration/vagrant/host

#. Startup the Virtual Machine with Vagrant::

    [nix:~/dev/reddwarf/integration/vagrant/host]$ vagrant up

*Note: There is a known bug with Vagrant and the first time you do the
'vagrant up' the downloads work correctly but when starting up the machines
there are problems. To resolve this issue just run the follow commands::

    [nix:~/dev/reddwarf/integration/vagrant/host]$ vagrant destroy
    [nix:~/dev/reddwarf/integration/vagrant/host]$ vagrant up
    
Command Downloads the necessary files and starts up a Virtual Box image to
start using.

-----------
Quick Setup
-----------

#. On your host machine (i.e. do NOT use vagrant ssh to enter it)::

    [nix:~/dev/reddwarf/integration/vagrant/host]$ ./run_ci.sh

This automates all the manual steps below in order.

1. initialize
2. build
3. setup nova
4. run tests

---------------------
Manual Setup Reddwarf
---------------------

#. This will ssh in to the virtual machine::

    [nix:~/dev/reddwarf/integration/vagrant/host]$ vagrant ssh host

#. This is the home location of all the phases of the integration testing::

    [vagrant:~]$ cd /vagrant

#. This will be sure the environment has all the required dependencies installed::

    [vagrant:/vagrant]$ /vagrant/initialize.sh

    OR

    [vagrant:~]$ cd /vagrant
    [vagrant:/vagrant]$ ./initialize.sh

#. This will build all the packages required to start and run nova. This
   includes the guest-agent package that will run on the containers that listens
   for events from the API::

    [vagrant:~]$ /vagrant/build.sh

    OR

    [vagrant:/vagrant]$ ./build.sh

#. This will clean and prepare the environment to start running nova as a
   clean setup::

    [vagrant:~]$ /vagrant-common/initialize-nova.sh

----------------
Testing Reddwarf
----------------

This is the integration tests for reddwarf that will run a plethora of tests
and be sure that everything is setup and working correctly.::

    [vagrant:/vagrant]$ ./test.sh

This is the integration test for the volume specific code path. This will test
the configuration and connections of the SAN.::

    [vagrant:/vagrant]$ ./test.sh --group=nova.volumes.driver

Using this test.sh script you can choose to select your own path that you
would like the tests to run via the flag --group=name.of.group.to.run.tests

----------------------------------
Starting Up Reddwarf/Nova Manually
----------------------------------

Bring up Reddwarf/Nova in wait mode::

    [vagrant:/vagrant]$ SERVICE_WAIT=True ./test.sh --group=start_and_wait

Some startup scripts below ...
https://github.com/cp16net/reddwarf-helpers

----------------------------------------
Example Calls/Utilties for Reddwarf/Nova
----------------------------------------

#. Open up a new terminal and goto directory vagrant host directory::

    [nix:~]$ cd ~/devreddwarf/integration/vagrant/host

#. SSH into the host::

    [nix:~]$ vagrant ssh host

#. Go to the source bin directory::

    [vagrant:~]$ cd /src/bin

#. Run reddwarf-cli::

    [vagrant:/src/bin]$ ./reddwarf-cli

#. Authenticate::

    [vagrant:/src/bin]$ ./reddwarf-cli auth login admin admin

#. Create a container::

    [vagrant:/src/bin]$ ./reddwarf-cli create dbcontainer dbcontainer 1 flavors/1
    [vagrant:/src/bin]$ ./reddwarf-cli list dbcontainers
    [vagrant:/src/bin]$ sudo vzlist
    [vagrant:/src/bin]$ sudo vzctl enter 1

#. Create database::

    [vagrant:/src/bin]$ ./reddwarf-cli create database 1 testdb

#. Create a user::

    [vagrant:/src/bin]$ ./reddwarf-cli create user 1 testuser testpass testdb

#. Login to mysql::

    [vagrant:/src/bin]$ mysql -u testuser -ptestpass -h <ipaddress>

