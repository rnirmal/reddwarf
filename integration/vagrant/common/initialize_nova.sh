# Host Environment Initializer - Nova Initializer
# This file is meant to be run in a VM or otherwise disposable environment.

fail_if_exists () {
    if [ -d $1 ] || [ -f $1 ]
    then
        echo The Nova cert file or directory $1 already exists. Aborting.
        exit 1
    fi
}

exclaim () {
    echo "*******************************************************************************"
    echo "$@"
    echo "*******************************************************************************"
}


exclaim Setting up SQL.

mysql_query () {
    mysql -u root -e $1
}


# Drop these in case this command is being run again.
mysql -u root -e "DROP DATABASE nova;"
mysql -u root -e "DROP DATABASE glance;"
rm -rf /home/vagrant/glance_repo
rm -rf /vz/template/cache/*
# Apparently this is no longer needed... ?
/vagrant-common/update_ovz_template2.sh

mysql -u root -e "CREATE USER 'nova'@'%';"
mysql -u root -e "CREATE DATABASE nova;"
mysql -u root -e "CREATE DATABASE glance;"
mysql -u root -e "UPDATE mysql.user SET Password=PASSWORD('novapass') WHERE User='nova';"
mysql -u root -e "GRANT ALL PRIVILEGES ON *.* TO 'nova'@'%' WITH GRANT OPTION;"
mysql -u root -e "DELETE FROM mysql.user WHERE User='root' AND Host!='localhost';"
mysql -u root -e "DELETE FROM mysql.user WHERE User='';"
mysql -u root -e "FLUSH PRIVILEGES;"

sudo sed -i.bak 's/^bind/#bind/g' /etc/mysql/my.cnf
# sudo cp /vagrant-common/mysql_my.cnf /etc/mysql/my.cnf
sudo service mysql restart

exclaim Initializing Nova database.

cat /vagrant-common/nova.conf.template > /home/vagrant/nova.conf


glance_manage () {
    echo glance-manage $@
    /glance/bin/glance-manage --sql-connection=mysql://nova:novapass@localhost/glance $@
}

nova_manage () {
    echo nova-manage $@
    /src/bin/nova-manage --flagfile=/home/vagrant/nova.conf $@
}

cd ~/
glance_manage version_control
glance_manage db_sync

cd ~/
nova_manage db sync
nova_manage user admin admin admin admin
nova_manage project create dbaas admin

exclaim Creating Nova certs.

# Setup the certs.
create_dir () {
    if [ -d $1 ]
    then
        echo $1 already exists.
    else
        mkdir $1
    fi
}



create_dir /src/nova/CA/private
# Entering the director seems to be required.
cd /src/nova/CA
./genrootca.sh
create_dir /src/nova/CA/newcerts


cd ~/
nova_manage project zipfile dbaas admin

exclaim Starting tests...
cd /tests

mkdir /home/vagrant/glance_repo

# Install glance_image if one isn't found.
if [ ! -f ~/glance_repo/1 ]
then
    echo "Installing Glance Image."
    cd /tests
    sudo -E INSTALL_GLANCE_IMAGE=True NOVASRC=/src /tests/run_tests_nv.sh --conf=/tests/vagrant/host/host.nemesis.conf --group=services.initialize.glance
fi


exclaim Setting up Networking

# Given 1-4 returns a bit of where the ip range starts.
ip_chunk() {
    ifconfig br100| grep 'inet addr:' | awk '{print $2} '| cut -d: -f2|cut -d. -f$@
}

# This next value will be something like '10.0.0'
ip_start123=`ip_chunk 1`.`ip_chunk 2`.`ip_chunk 3`

gateway_ip=`route -n|grep ^0.0.0.0|sed 's/ \+/ /g'|cut -d' ' -f2`
dns_ip=`grep -m1 nameserver /etc/resolv.conf |cut -d' ' -f2`

echo "--flat_network_dns=$dns_ip" >> /home/vagrant/nova.conf
#nova_manage network create 10.0.2.0/24 1 256

# Can't figure out the CIDR rules, so I'm giving it 256 ips.
nova_manage network create `ip_chunk 1`.`ip_chunk 2`.`ip_chunk 3`.0/24 1 256

# Assume there is only one network and `update all rows.
mysql -u root -e "UPDATE nova.networks SET gateway='$gateway_ip';"
mysql -u root -e "UPDATE nova.networks SET dns='$dns_ip';"


# Deletes a fixed ip (argument is the last number in an IP)
delete_fixed_ip() {
    mysql -u root -e "DELETE FROM nova.fixed_ips WHERE address='$ip_start123.$1';"
}

# Delete all extra IPs grabbed by Nova.
for (( x=0; x <= `ip_chunk 4`; x += 1))
do
    delete_fixed_ip $x
done


# TODO: It may be necessary to delete all other instances of this.

# TODO: Add the fake LVM stuff so nova volumes doesnt complain (see baz' wiki article)
