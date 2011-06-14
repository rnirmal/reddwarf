# Called on the volumes VM

echo Deleting volumes.
for i in {1..100}
do
   sudo ietadm --op delete --tid=$i
done
sudo rm -rf /san/*
echo Finished deleting volumes. Please ignore any error messages you might have seen above...