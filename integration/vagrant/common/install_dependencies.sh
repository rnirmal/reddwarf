#!/bin/bash
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

# Setup up the Diable release ppa
sudo add-apt-repository ppa:openstack-release/2011.3/ubuntu
sudo -E apt-get update

pkg_install python-nova iptables ebtables screen curl rabbitmq-server
# Removing the nova trunk ppa that nova.sh adds, we need to be using the diable release ppa instead
sudo rm /etc/apt/sources.list.d/nova-core-trunk*

exclaim Installing additional Nova dependencies.

pkg_install mysql-server-5.1
pkg_install python-mysqldb
pkg_install python-paramiko
pkg_install uuid

# Install open-iscsi and update the config with the defaults
pkg_install open-iscsi

# Update the conf file
ISCSID_CONF=/etc/iscsi/iscsid.conf
sed -i 's/node.startup = manual/node.startup = automatic/' $ISCSID_CONF
sed -i 's/#node.session.auth.authmethod = CHAP/node.session.auth.authmethod = CHAP/' $ISCSID_CONF
sed -i 's/#node.session.auth.username = username/node.session.auth.username = username/' $ISCSID_CONF
sed -i 's/#node.session.auth.password = password/node.session.auth.password = password1234/' $ISCSID_CONF
sed -i 's/#discovery.sendtargets.auth.authmethod = CHAP/discovery.sendtargets.auth.authmethod = CHAP/' $ISCSID_CONF
sed -i 's/#discovery.sendtargets.auth.username = username/discovery.sendtargets.auth.username = username/' $ISCSID_CONF
sed -i 's/#discovery.sendtargets.auth.password = password/discovery.sendtargets.auth.password = password1234/' $ISCSID_CONF


# Restart the iscsi initiator
sudo /etc/init.d/open-iscsi restart

# Update services to listen only on br200 the infranet
br200_ip=`get_ip_for_device br200`

# Set Rabbitmq to listen on br100 only
sudo cat > /etc/rabbitmq/rabbitmq.config <<EOF
[
    {rabbit, [{tcp_listeners, [{"$br200_ip", 5672}]}]}
].
EOF
sudo service rabbitmq-server restart

# Set Mysql (Nova DB) to listen on br100 only
sudo sed -i "s/^bind-address[ \t]*= 127.0.0.1/bind-address\t\t = $br200_ip/g" /etc/mysql/my.cnf
sudo service mysql restart
