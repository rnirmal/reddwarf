#!/bin/bash
vagrant_init_ssh_info() {
    # Argument 1 - The name of the VM to SSH.
     # If the SSH info isn't defined, figure it out here.
    if [ -z "${vcmd_port}" ]
    then
        vcmd_port=`vagrant ssh_config $1 | grep Port | cut -c 8-`
    fi
    if [ -z "${vcmd_host}" ]
    then
        vcmd_host=`vagrant ssh_config $1 | grep HostName | cut -c 12-`
    fi
    if [ -z "${vcmd_idfile}" ]
    then
        vcmd_idfile=`vagrant ssh_config $1 | grep IdentityFile | cut -c 16-`
    fi
    if [ -z "${vcmd_user}" ]
    then
        vcmd_user=`vagrant ssh_config $1 | grep User | cut -c 8-`
    fi
}

vagrant_clear_ssh_key() {
    # Argument 1 - The name of the VM to SSH.
    # Clears the key so you can SSH to vagrant without the man-in-the-middle warning.
    vagrant_init_ssh_info $1
    ssh-keygen -R [$vcmd_host]:$vcmd_port
}

vagrant_cmd() {
    # Argument 1 - The name of the VM to SSH.
    # Runs a command via SSH against the vagrant instance.
    vagrant_init_ssh_info $1
    shift
    #ssh vagrant@$vcmd_host -p $vcmd_port -i "$vcmd_idfile" -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no "$@"
    ssh vagrant@$vcmd_host -p $vcmd_port -i "$vcmd_idfile" -o NoHostAuthenticationForLocalhost=yes "$@"
}
