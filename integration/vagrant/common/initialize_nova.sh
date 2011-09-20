#!/bin/bash
# Builds packages.

# Host Environment Initializer - Nova Initializer
# This file is meant to be run in a VM or otherwise disposable environment.

source /vagrant-common/Utils.sh

exclaim Setting up SQL.

mysql_query () {
    mysql -u root -pnova -e $1
}


# Drop these in case this command is being run again.
mysql -u root -pnova -e "DROP DATABASE nova;"
mysql -u root -pnova -e "DROP DATABASE glance;"
mysql -u root -pnova -e "DROP DATABASE keystone;"
sudo rm -rf /var/lib/glance
sudo mkdir -p /var/lib/glance/images
sudo rm -rf /vz/template/cache/*
# Apparently this is no longer needed... ?
/vagrant-common/update_ovz_template2.sh

mysql -u root -pnova -e "CREATE USER 'nova'@'%';"
mysql -u root -pnova -e "CREATE DATABASE nova;"
mysql -u root -pnova -e "CREATE DATABASE glance;"
mysql -u root -pnova -e "CREATE DATABASE keystone;"
mysql -u root -pnova -e "UPDATE mysql.user SET Password=PASSWORD('novapass') WHERE User='nova';"
mysql -u root -pnova -e "GRANT ALL PRIVILEGES ON *.* TO 'nova'@'%' WITH GRANT OPTION;"
mysql -u root -pnova -e "DELETE FROM mysql.user WHERE User='root' AND Host!='localhost';"
mysql -u root -pnova -e "DELETE FROM mysql.user WHERE User='';"
mysql -u root -pnova -e "FLUSH PRIVILEGES;"

exclaim Initializing Nova database.

cat /vagrant-common/nova.conf.template > /home/vagrant/nova.conf
# Add the domain name, make it different each time
uuid | sed s/^/--dns_domain_name=/ | sed s/$/-dbaas-tests.com/  >> /home/vagrant/nova.conf
if [ -d /extra ]
then
    cat /extra/nova.conf >> /home/vagrant/nova.conf
fi


glance_manage () {
    echo glance-manage $@
    # Check if glance is package installed or not by
    # just checking if the 'known' glance-manage exists
    if [ -f /glance/bin/glance-manage ]
    then
        /glance/bin/glance-manage --config-file=/vagrant/glance-reg.conf $@
    else
        glance-manage --config-file=/vagrant/glance-reg.conf $@
    fi
}

nova_manage () {
    echo nova-manage $@
    /src/bin/nova-manage --flagfile=/home/vagrant/nova.conf $@
}

reddwarf_manage () {
    echo reddwarf-manage $@
    /src/bin/reddwarf-manage --sql_connection=mysql://nova:novapass@localhost/nova $@
}

keystone_manage () {
    echo keystone-manage $@
    sudo keystone-manage $@
}

cd ~/
glance_manage version_control
glance_manage db_sync

nova_manage db sync
nova_manage user admin admin admin admin
nova_manage user admin boss admin admin
nova_manage project create dbaas admin


reddwarf_manage db sync

# Keystone - Add a regular system admin
AUTH_TENANT="dbaas"
AUTH_USER="admin"
AUTH_PASSWORD="admin"
AUTH_ADMIN_ROLE="Admin"
keystone_manage tenant add $AUTH_TENANT
keystone_manage user add $AUTH_USER $AUTH_PASSWORD $AUTH_TENANT
keystone_manage role add $AUTH_ADMIN_ROLE
keystone_manage role grant $AUTH_ADMIN_ROLE $AUTH_USER
keystone_manage role grant $AUTH_ADMIN_ROLE $AUTH_USER $AUTH_TENANT

# Add "Boss"
keystone_manage user add Boss admin dbaas


AUTH_TENANT="dbaas"
AUTH_USER="admin"
AUTH_PASSWORD="admin"
AUTH_ADMIN_ROLE="Admin"
keystone_manage tenant add $AUTH_TENANT
keystone_manage user add $AUTH_USER $AUTH_PASSWORD $AUTH_TENANT
keystone_manage role add $AUTH_ADMIN_ROLE
keystone_manage role grant $AUTH_ADMIN_ROLE $AUTH_USER
keystone_manage role grant $AUTH_ADMIN_ROLE $AUTH_USER $AUTH_TENANT


SERVICE_ADMIN_USER="service-admin"
SERVICE_ADMIN_PASSWORD="serviceadmin"
SERVICE_ADMIN_ROLE="KeystoneServiceAdmin"
keystone_manage user add $SERVICE_ADMIN_USER $SERVICE_ADMIN_PASSWORD
keystone_manage role add $SERVICE_ADMIN_ROLE
keystone_manage role grant $SERVICE_ADMIN_ROLE $SERVICE_ADMIN_USER


SERVICE_REGION="ci"
REDDWARF_SERVICE_NAME="reddwarf"
NOVA_SERVICE_NAME="nova"
REDDWARF_SERVICE_URL="http://localhost:8775/v1.0"
NOVA_SERVICE_URL="http://localhost:8774/v1.1"
keystone_manage service add $REDDWARF_SERVICE_NAME
keystone_manage service add $NOVA_SERVICE_NAME
keystone_manage endpointTemplates add $SERVICE_REGION $REDDWARF_SERVICE_NAME $REDDWARF_SERVICE_URL $REDDWARF_SERVICE_URL $REDDWARF_SERVICE_URL 1 0
keystone_manage endpointTemplates add $SERVICE_REGION $NOVA_SERVICE_NAME $NOVA_SERVICE_URL $NOVA_SERVICE_URL $NOVA_SERVICE_URL 1 0
keystone_manage endpoint add $AUTH_TENANT 1
keystone_manage endpoint add $AUTH_TENANT 2

# Copy and update the paste.ini files
cp /src/etc/nova/api-paste_keystone.ini /home/vagrant
cp /src/etc/nova/reddwarf-api-paste.ini /home/vagrant

exclaim Starting tests...
cd /tests

# Make sure the domain name exists (must happen before the image is added)
cd /tests
sudo -E ADD_DOMAINS=True NOVASRC=/src /tests/run_tests_nv.sh --conf=/tests/vagrant/host/host.nemesis.conf --group=rsdns.domains


# Install glance_image if one isn't found.
if [ ! -f /var/lib/glance/1 ]
then
    echo "Installing Glance Image."
    cd /tests
    sudo -E INSTALL_GLANCE_IMAGE=True NOVASRC=/src /tests/run_tests_nv.sh --conf=/tests/vagrant/host/host.nemesis.conf --group=services.initialize.glance
fi


exclaim Setting up Networking

# This next value will be something like '10.0.0'
ip_startbr100=`ip_chunk br100 1`.`ip_chunk br100 2`.`ip_chunk br100 3`
ip_startbr200=`ip_chunk br200 1`.`ip_chunk br200 2`.`ip_chunk br200 3`

gateway_ip=`route -n|grep ^0.0.0.0|sed 's/ \+/ /g'|cut -d' ' -f2`
dns_ip=`grep -m1 nameserver /etc/resolv.conf |cut -d' ' -f2`

echo "--flat_network_dns=$dns_ip" >> /home/vagrant/nova.conf

# Can't figure out the CIDR rules, so I'm giving it 256 ips.
nova_manage network create --label=usernet --fixed_range_v4=$ip_startbr100.0/24 --num_networks=1 --network_size=256 --bridge=br100 --bridge_interface=eth0 --dns1=$dns_ip
nova_manage network create --label=infranet --fixed_range_v4=$ip_startbr200.0/24 --num_networks=1 --network_size=256 --bridge=br200 --bridge_interface=eth1 --dns1=$dns_ip 

# This for some reason is not being added, nor is it a option in nova manage.
# We NEED to get the project associated w/ the network and this is a nasty hack
# TODO(mbasnight) figure out why this doesnt pass a project but needs it set in the db
mysql -u root -pnova -e "update nova.networks set project_id = '$AUTH_TENANT';"
hostname=`hostname`

# Assume there is only one network and `update all rows.
mysql -u root -pnova -e "UPDATE nova.networks SET gateway='$gateway_ip';"
mysql -u root -pnova -e "UPDATE nova.networks SET host='$hostname';"

# Delete all extra IPs grabbed by Nova.
delete_extra_ips() {
    for (( x=0; x <= `ip_chunk $1 4`; x += 1))
    do
        mysql -u root -pnova -e "DELETE FROM nova.fixed_ips WHERE address='$2.$x';"
    done
}

delete_extra_ips br100 $ip_startbr100
delete_extra_ips br200 $ip_startbr200

# Remove all the devices on the Host
sudo iscsiadm -m node --logout

# Delete all of the volumes on the Volumes VM since the DB will now
# be out of sync.
ssh vagrant@33.33.33.10 "sudo /vagrant-common/delete_volumes.sh"

# Restart Rabbit MQ so all the old queues are cleared
sudo service rabbitmq-server restart

# Stop glance services
#sudo glance-api stop
#sudo glance-registry stop

# Remove vz private area
for i in `sudo vzlist --all --output ctid --no-header` ; do sudo vzctl stop $i && sudo vzctl destroy $i ; done
sudo rm -fr /var/lib/vz/private/*

# Just in case of failures return a-ok
exit 0
# TODO: It may be necessary to delete all other instances of this.

# TODO: Add the fake LVM stuff so nova volumes doesnt complain (see baz' wiki article)


