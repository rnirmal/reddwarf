
#export ROOT=$WORKSPACE/../..
#export GLANCESRC=$ROOT/glance
#export GLANCEIMAGES=/home/nova/glance_images
#export NOVASRC=$ROOT/bluedwarf

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

#vagrant destroy
#vagrant up
if [ $? -ne 0 ]
then 
echo "Error bringing up VM!"
exit 1
fi

bash ./run_cmd.sh sudo -E bash /vagrant/initialize.sh
if [ $? -ne 0 ]
then 
echo "Error initializing VM environment."
#vagrant halt
exit 1
fi

# At this point you could save the Vagrant Box if you wanted to...

bash ./run_cmd.sh sudo -E bash /vagrant/build.sh
if [ $? -ne 0 ]
then 
echo "Error building and installing packages."
#vagrant halt
exit 1
fi

bash ./run_cmd.sh sudo -E bash /vagrant-common/initialize_nova.sh
if [ $? -ne 0 ]
then 
echo "Error initializing nova."
#vagrant halt
exit 1
fi

bash ./run_cmd.sh sudo -E bash /vagrant/test.sh
if [ $? -ne 0 ]
then 
echo "Error running tests."
#vagrant halt
exit 1
fi
