# This is meant to be called from the volume box.
if [ ! -f /vagrant-common/ssh/id_rsa ] || [ ! -f /vagrant-common/ssh/id_rsa.pub ]
then
    echo 'Missing ssh key. Use ssh-keygen to create key at /vagrant-common/ssh/ (leave options such as passphrase empty).'
    exit 1
fi
cp /vagrant-common/ssh/id_rsa.pub /home/vagrant/.ssh/id_rsa.pub
cp /vagrant-common/ssh/id_rsa /home/vagrant/.ssh/id_rsa
sudo mkdir /root/.ssh
sudo cp /vagrant-common/ssh/id_rsa.pub /root/.ssh/id_rsa.pub
sudo cp /vagrant-common/ssh/id_rsa.pub /root/.ssh/id_rsa
