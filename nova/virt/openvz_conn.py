# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 OpenStack LLC.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
A driver specific to OpenVz as the support for Ovz in libvirt
is sketchy at best.
"""

import os
import socket
from nova import db
from nova import exception
from nova import flags
from nova import log as logging
from nova import utils
from nova import context
from nova.auth import manager
from nova.network import linux_net
from nova.compute import power_state
from nova.compute import instance_types
from nova.exception import ProcessExecutionError
from nova.virt import images
from nova.virt import driver

FLAGS = flags.FLAGS
flags.DEFINE_string('ovz_template_path',
                    '/var/lib/vz/template/cache',
                    'Path to use for local storage of OVz templates')
flags.DEFINE_string('ovz_ve_private_dir',
                    '/var/lib/vz/private',
                    'Path where VEs will get placed')
flags.DEFINE_string('ovz_ve_root_dir',
                    '/var/lib/vz/root',
                    'Path where the VEs root is')
flags.DEFINE_string('ovz_ve_host_mount_dir',
                    '/mnt',
                    'Path where outside mounts go')
flags.DEFINE_string('ovz_image_template_dir',
                    '/var/lib/vz/template/cache',
                    'Path where OpenVZ images are')
flags.DEFINE_string('ovz_config_dir',
                    '/etc/vz/conf',
                    'Where the OpenVZ configs are stored')
flags.DEFINE_string('ovz_bridge_device',
                    'br100',
                    'Bridge device to map veth devices to')
flags.DEFINE_string('ovz_network_template',
                    utils.abspath('virt/openvz_interfaces.template'),
                    'OpenVz network interface template file')
flags.DEFINE_bool('ovz_use_cpuunit',
                  True,
                  'Use OpenVz cpuunits for guaranteed minimums')
flags.DEFINE_bool('ovz_use_cpulimit',
                  True,
                  'Use OpenVz cpulimit for maximum cpu limits')
flags.DEFINE_bool('ovz_use_cpus',
                  True,
                  'Use OpenVz cpus for max cpus available to the container')
flags.DEFINE_bool('ovz_use_ioprio',
                  True,
                  'Use IO fair scheduling')
flags.DEFINE_integer('ovz_ioprio_limit',
                     7,
                     'Limit for IO priority weighting')
flags.DEFINE_bool('ovz_disk_space_oversub',
                  True,
                  'Allow over subscription of local disk')
flags.DEFINE_float('ovz_disk_space_oversub_percent',
                   1.10,
                   'Local disk over subscription percentage')
flags.DEFINE_string('ovz_disk_space_increment',
                    'G',
                    'Disk subscription increment')
flags.DEFINE_bool('ovz_use_disk_quotas',
                  True,
                  'Use disk quotas to contain disk usage')

LOG = logging.getLogger('nova.virt.openvz')


def get_connection(read_only):
    return OpenVzConnection(read_only)


class OpenVzConnection(driver.ComputeDriver):
    def __init__(self, read_only):
        self.utility = {
                'CTIDS': {},
                'TOTAL': 0,
                'UNITS': 0,
                'MEMORY_MB': 0,
                'CPULIMIT': 0
            }
        self.read_only = read_only
        LOG.debug("__init__ complete in OpenVzConnection")

    @classmethod
    def instance(cls):
        if not hasattr(cls, '_instance'):
            cls._instance = cls()
        return cls._instance

    def init_host(self, host=socket.gethostname()):
        """
        Initialize anything that is necessary for the driver to function,
        including catching up with currently running VE's on the given host.
        """
        ctxt = context.get_admin_context()

        LOG.debug('Hostname: %s' % (host,))
        LOG.debug('Instances: %s' % (db.instance_get_all_by_host(ctxt, host)))

        for instance in db.instance_get_all_by_host(ctxt, host):
            try:
                LOG.debug('Checking state of %s' % instance['name'])
                state = self.get_info(instance['name'])['state']
            except exception.NotFound:
                state = power_state.SHUTOFF

            LOG.debug('Current state of %s was %s.' %
                      (instance['name'], state))
            db.instance_set_state(ctxt, instance['id'], state)

            if state == power_state.SHUTOFF:
                db.instance_destroy(ctxt, instance['id'])

            if state != power_state.RUNNING:
                continue

        LOG.debug("Determining the computing power of the host")

        self._get_cpuunits_capability()
        self._get_cpulimit()
        self._get_memory()

        LOG.debug("init_host complete in OpenVzConnection")

    def list_instances(self):
        """
        Return the names of all the instances known to the container
        layer, as a list.
        """
        try:
            out, err = utils.execute(
                'sudo', 'vzlist', '--all', '--no-header', '--output', 'ctid')
            if err:
                LOG.error(err)
        except ProcessExecutionError:
            raise exception.Error('Failed to list VZs')

        ctids = []
        for line in out.splitlines():
            ctid = line.split()[0]
            ctids.append(ctid)

        return ctids

    def list_instances_detail(self):
        """
        Satisfy the requirement for this method in the manager codebase.
        This fascilitates the regular status polls that happen within the
        manager code.
        """

        # TODO(imsplitbit): need to ask around if this is the best way to do
        # this.  This causes some redundant vzlist commands as get_info is run
        # on every item returned from this command but it didn't make sense
        # to re-implement get_info as get_info_all.
        infos = []
        try:
            # get a list of CT names which will be nova friendly.
            # NOTE: This can be an issue if nova decides to change
            # the format of names.  We would need to have a migration process
            # to change the names in the name field of the CTs.
            out, err = utils.execute('sudo', 'vzlist', '--all', '-o',
                                     'name', '-H')
            if err:
                LOG.error(err)
        except ProcessExecutionError as err:
            LOG.error(err)
            raise exception.Error('Problem listing Vzs')

        for name in out.splitlines():
            name = name.split()[0]
            status = self.get_info(name)
            infos.append(driver.InstanceInfo(name, status['state']))

        return infos

    def spawn(self, context, instance, network_info=None,
              block_device_mapping=None):
        """
        Create a new virtual environment on the container platform.

        The given parameter is an instance of nova.compute.service.Instance.
        This function should use the data there to guide the creation of
        the new instance.

        The work will be done asynchronously.  This function returns a
        task that allows the caller to detect when it is complete.

        Once this successfully completes, the instance should be
        running (power_state.RUNNING).

        If this fails, any partial instance should be completely
        cleaned up, and the container platform should be in the state
        that it was before this call began.
        """

        # Update state to inform the nova stack that the VE is launching
        db.instance_set_state(context,
                              instance['id'],
                              power_state.NOSTATE,
                              'launching')
        LOG.debug('instance %s: is launching' % instance['name'])

        # Get current usages and resource availablity.
        self._get_cpuunits_usage()

        # Go through the steps of creating a container
        # TODO(imsplitbit): Need to add conditionals around this stuff to make
        # it more durable during failure. And roll back changes made leading
        # up to the error.
        self._cache_image(context, instance)
        self._create_vz(instance)
        self._set_vz_os_hint(instance)
        self._configure_vz(instance)
        self._set_name(instance)
        self._setup_networks(instance, network_info)
        self._set_hostname(instance)
        self._set_vmguarpages(instance)
        self._set_privvmpages(instance)
        self._attach_volumes(instance)

        if FLAGS.ovz_use_cpuunit:
            self._set_cpuunits(instance)
        if FLAGS.ovz_use_cpulimit:
            self._set_cpulimit(instance)
        if FLAGS.ovz_use_cpus:
            self._set_cpus(instance)
        if FLAGS.ovz_use_ioprio:
            self._set_ioprio(instance)
        if FLAGS.ovz_use_disk_quotas:
            self._set_diskspace(instance)

        self._start(instance)
        self._initial_secure_host(instance)
        self._gratuitous_arp_all_addresses(instance, network_info)

        # Begin making our looping async call
        timer = utils.LoopingCall(f=None)

        # I stole this from the libvirt driver but it is appropriate to
        # have this looping timer call so that if a VE doesn't start right
        # away we can defer all of this.
        def _wait_for_boot():
            try:
                state = self.get_info(instance['name'])['state']
                db.instance_set_state(context,
                                      instance['id'], state)
                if state == power_state.RUNNING:
                    LOG.debug('instance %s: booted' % instance['name'])
                    timer.stop()

            except:
                LOG.exception('instance %s: failed to boot' %
                              instance['name'])
                db.instance_set_state(context,
                                      instance['id'],
                                      power_state.SHUTDOWN)
                timer.stop()

        timer.f = _wait_for_boot
        return timer.start(interval=0.5, now=True)

    def _create_vz(self, instance, ostemplate='ubuntu'):
        """
        Attempt to load the image from openvz's image cache, upon failure
        cache the image and then retry the load.
        """

        # TODO(imsplitbit): This needs to set an os template for the image
        # as well as an actual OS template for OpenVZ to know what config
        # scripts to use.  This can be problematic because there is no concept
        # of OS name, it is arbitrary so we will need to find a way to
        # correlate this to what type of disto the image actually is because
        # this is the clue for openvz's utility scripts.  For now we will have
        # to set it to 'ubuntu'

        # This will actually drop the os from the local image cache
        try:
            out, err = utils.execute('sudo', 'vzctl', 'create', instance['id'],
                                     '--ostemplate', instance['image_ref'])
            LOG.debug(out)
            if err:
                LOG.error(err)
        except exception.ProcessExecutionError as err:
            LOG.error(err)
            raise exception.Error('Failed creating VE %s from image cache' %
                                  instance['id'])
        return True

    def _set_vz_os_hint(self, instance, ostemplate='ubuntu'):
        # This sets the distro hint for OpenVZ to later use for the setting
        # of resolver, hostname and the like
        try:
            out, err = utils.execute('sudo', 'vzctl', 'set', instance['id'],
                                     '--save', '--ostemplate', ostemplate)
            LOG.debug(out)
            if err:
                LOG.error(err)
        except exception.ProcessExecutionError as err:
            LOG.error(err)
            raise exception.Error('Unable to set ostemplate to \'%s\' for %s' %
                                  (ostemplate, instance['id']))

    def _cache_image(self, context, instance):
        """
        Create the disk image for the virtual environment.
        """

        image_name = '%s.tar.gz' % instance['image_ref']
        full_image_path = '%s/%s' % (FLAGS.ovz_image_template_dir, image_name)

        if not os.path.exists(full_image_path):
            # These objects are required to retrieve images from the object
            # store. This is known only to work with glance so far but as I
            # understand it. glance's interface matches that of the other
            # object stores.
            user = manager.AuthManager().get_user(instance['user_id'])
            project = manager.AuthManager().get_project(instance['project_id'])

            # Grab image and place it in the image cache
            images.fetch(context, instance['image_ref'], full_image_path, user,
                         project)
            return True
        else:
            return False

    def _configure_vz(self, instance, config='basic'):
        """
        This adds the container root into the vz meta data so that
        OpenVz acknowledges it as a container.  Punting to a basic
        config for now.
        """
        try:
            # Set the base config for the VE, this currently defaults to the
            # basic config.
            # TODO(imsplitbit): add guest flavor support here
            out, err = utils.execute('sudo', 'vzctl', 'set', instance['id'],
                                     '--save', '--applyconfig', config)
            LOG.debug(out)
            if err:
                LOG.error(err)

        except ProcessExecutionError:
            raise exception.Error('Failed to add %s to OpenVz'
                                  % instance['id'])

    def _start(self, instance):
        """
        Method to start the instance, I don't believe there is a nova-ism
        for starting so I am wrapping it under the private namespace and
        will call it from expected methods.  i.e. resume
        """
        try:
            # Attempt to start the VE.
            # NOTE: The VE will throw a warning that the hostname is invalid
            # if it isn't valid.  This is logged in LOG.error and is not
            # an indication of failure.
            out, err = utils.execute('sudo', 'vzctl', 'start', instance['id'])
            LOG.debug(out)
            if err:
                LOG.error(err)
        except ProcessExecutionError as err:
            LOG.error(err)
            raise exception.Error('Failed to start %d' % instance['id'])

        # Set instance state as RUNNING
        db.instance_set_state(context.get_admin_context(),
                              instance['id'],
                              power_state.RUNNING)
        return True

    def _stop(self, instance):
        """
        Method to stop the instance.  This doesn't seem to be a nova-ism but
        it is for openvz so I am wrapping it under the private namespace and
        will call it from expected methods.  i.e. pause
        """
        try:
            out, err = utils.execute('sudo', 'vzctl', 'stop', instance['id'])
            LOG.debug(out)
            if err:
                LOG.error(err)
        except ProcessExecutionError:
            raise exception.Error('Failed to stop %s' % instance['id'])

        # Update instance state
        try:
            db.instance_set_state(context.get_admin_context(), instance['id'],
                                  power_state.SHUTDOWN)
        except exception.DBError as err:
            LOG.error(err)
            raise exception.Error('Failed to update db for %s'
                                  % instance['id'])

    def _setup_networks(self, instance, network_info):
        """Setup all the provided networks

        Add the specified network interfaces.
        Assign ips for those interfaces and bridge them.
        Add nameserver information for all the interfaces
        """
        for eth_id, network in enumerate(network_info):
            bridge = network[0]["bridge"]
            netif = network[0]["bridge_interface"] \
                        if "bridge_interface" in network[0] \
                        else "eth%s" % eth_id
            ip = network[1]["ips"][0]["ip"]
            netmask = network[1]["ips"][0]["netmask"]
            gateway = network[1]["gateway"]
            dns = network[1]["dns"][0]

            self._add_netif(instance, netif=netif, bridge=bridge)
            self._add_ip(instance, ip, netmask, gateway, netif=netif)
            self._set_nameserver(instance, dns)

    def _add_netif(self, instance, netif="eth0",
                   host_if=False,
                   bridge=FLAGS.ovz_bridge_device):
        """
        This is more of a work around to add the eth devs
        the way OpenVZ wants them. Currently only bridged networking
        is supported in this driver.
        """
        # TODO(imsplitbit): fix this to be nova-ish i.e. async
        try:
            # Command necessary to create a bridge networking setup.
            # right now this is the only supported networking model
            # in the openvz connector.
            if not host_if:
                host_if = 'veth%s.%s' % (instance['id'], netif)

            out, err = utils.execute('sudo', 'vzctl', 'set', instance['id'],
                                     '--save', '--netif_add',
                                     '%s,,%s,,%s' % (netif, host_if, bridge))
            LOG.debug(out)
            if err:
                LOG.error(err)

        except ProcessExecutionError:
            raise exception.Error(
                    'Error adding network device to container %s' %
                    instance['id'])

    def _add_ip(self, instance, ip, netmask, gateway, netif='eth0',
                if_file='etc/network/interfaces'):
        """
        Add an ip to the container
        """
        net_path = '%s/%s' % (FLAGS.ovz_ve_private_dir, instance['id'])
        if_file_path = net_path + '/' + if_file

        try:
            os.chdir(net_path)
            with open(FLAGS.ovz_network_template) as fh:
                network_file = fh.read() % {'gateway_dev': netif,
                                            'address': ip,
                                            'netmask': netmask,
                                            'gateway': gateway}

            # TODO(imsplitbit): Find a way to write to this file without
            # mangling the perms.
            utils.execute('sudo', 'chmod', '666', if_file_path)
            fh = open(if_file_path, 'a')
            fh.write(network_file)
            fh.close()
            utils.execute('sudo', 'chmod', '644', if_file_path)

        except Exception as err:
            LOG.error(err)
            raise exception.Error('Error adding IP')

    def _gratuitous_arp_all_addresses(self, instance, network_info):
        """
        Iterate through all addresses assigned to the container and send
        a gratuitous arp over it's interface to make sure arp caches have
        the proper mac address.
        """
        #TODO(imsplitbit): refactor all networking stuff into a class/object
        for network in network_info:
            bridge_info = network[0]
            LOG.debug('bridge interface: %s' %
                      (bridge_info['bridge_interface'],))
            LOG.debug('bridge: %s' % (bridge_info['bridge'],))
            LOG.debug('address block: %s' % (bridge_info['cidr']))
            address_info = network[1]
            LOG.debug('network label: %s' % (address_info['label']))
            for address in address_info['ips']:
                LOG.debug('Address enabled: %s' % (address['enabled'],))
                LOG.debug('Address enabled type: %s' %
                          (type(address['enabled'],)))
                if address['enabled'] == u'1':
                    LOG.debug('Address: %s' % (address['ip'],))
                    LOG.debug('Running _send_garp(%s, %s, %s)' %
                              (instance['id'], address['ip'],
                               bridge_info['bridge_interface']))
                    self._send_garp(instance['id'], address['ip'],
                                    bridge_info['bridge_interface'])

    def _send_garp(self, instance_id, ip_address, interface):
        """
        I exist because it is possible in nova to have a recently released
        ip address given to a new container.  We need to send a gratuitous arp
        on each interface for the address assigned.
        """
        # TODO(imsplitbit): refactor all networking stuff into a class/object
        try:
            LOG.debug('Sending a gratuitous arp for %s over %s' %
                      (ip_address, interface))
            out, err = utils.execute('sudo', 'vzctl', 'exec', instance_id,
                                     'arping', '-c', '5', '-w', '5', '-U', '-I',
                                     interface, ip_address)
            LOG.debug(out)
            LOG.debug('Gratuitous arp sent for %s over %s' %
                      (ip_address, interface))
            if err:
                LOG.error(err)
        except ProcessExecutionError as err:
            LOG.error(err)
            LOG.error('Failed arping through VE')

    def _set_nameserver(self, instance, dns):
        """
        Get the nameserver for the assigned network and set it using
        OpenVz's tools.
        """
        try:
            out, err = utils.execute('sudo', 'vzctl', 'set', instance['id'],
                                     '--save', '--nameserver', dns)
            LOG.debug(out)
            if err:
                LOG.error(err)
        except Exception as err:
            LOG.error(err)
            raise exception.Error('Unable to set nameserver for %s' %
            instance['id'])

    def _set_hostname(self, instance, hostname=None):
        if not hostname:
            hostname = instance['hostname']

        try:
            out, err = utils.execute('sudo', 'vzctl', 'set', instance['id'],
                                     '--save', '--hostname', hostname)
            LOG.debug(out)
            if err:
                LOG.error(err)
        except ProcessExecutionError:
            raise exception.Error('Cannot set the hostname on %s' %
                                  instance['id'])

    def _set_name(self, instance):
        # This stores the nova 'name' of an instance in the name field for
        # openvz.  This is done to facilitate the get_info method which only
        # accepts an instance name.
        try:
            out, err = utils.execute('sudo', 'vzctl', 'set', instance['id'],
                                     '--save', '--name', instance['name'])
            LOG.debug(out)
            if err:
                LOG.error(err)

        except Exception as err:
            LOG.error(err)
            raise exception.Error('Unable to save metadata for %s' %
                                  instance['id'])

    def _find_by_name(self, instance_name):
        # The required method get_info only accepts a name so we need a way
        # to correlate name and id without maintaining another state/meta db
        try:
            out, err = utils.execute('sudo', 'vzlist', '-H', '--all',
                                     '--name', instance_name)
            LOG.debug(out)
            if err:
                LOG.error(err)
        except Exception as err:
            LOG.error(err)
            raise exception.NotFound('Unable to load metadata for %s' %
                                  instance_name)

        # Break the output into usable chunks
        out = out.split()
        return {'name': out[4], 'id': out[0], 'state': out[2]}

    def _access_control(self, instance, host, mask=32, port=None,
                        protocol='tcp', access_type='allow'):
        """
        Does what it says.  Use this to interface with the
        linux_net.iptables_manager to allow/deny access to a host
        or network
        """

        if access_type == 'allow':
            access_type = 'ACCEPT'
        elif access_type == 'deny':
            access_type = 'REJECT'
        else:
            LOG.error('Invalid access_type: %s' % access_type)
            raise exception.Error('Invalid access_type: %s' % access_type)

        if port == None:
            port = ''
        else:
            port = '--dport %s' % (port,)

        # Create our table instance
        tables = [
                linux_net.iptables_manager.ipv4['filter'],
                linux_net.iptables_manager.ipv6['filter']
        ]

        rule = '-s %s/%s -p %s %s -j %s' % \
               (host, mask, protocol, port, access_type)

        for table in tables:
            table.add_rule(instance['name'], rule)

        # Apply the rules
        linux_net.iptables_manager.apply()

    def _initial_secure_host(self, instance, ports=None):
        """
        Lock down the host in it's default state
        """

        # TODO(tim.simpson) This hangs if the "lock_path" FLAG value refers to
        #                   a directory which can't be locked.  It'd be nice
        #                   if we could somehow detect that and raise an error
        #                   instead.

        # Create our table instance and add our chains for the instance
        table_ipv4 = linux_net.iptables_manager.ipv4['filter']
        table_ipv6 = linux_net.iptables_manager.ipv6['filter']
        table_ipv4.add_chain(instance['name'])
        table_ipv6.add_chain(instance['name'])

        # As of right now there is no API call to manage security
        # so there are no rules applied, this really is just a pass.
        # The thought here is to allow us to pass a list of ports
        # that should be globally open and lock down the rest but
        # cannot implement this until the API passes a security
        # context object down to us.

        # Apply the rules
        linux_net.iptables_manager.apply()

    def _set_vmguarpages(self, instance):
        """
        Set the vmguarpages attribute for a container.  This number represents
        the number of 4k blocks that are guaranteed to the container.
        """
        vmguarpages = self._calc_pages(instance)

        try:
            out, err =  utils.execute('sudo', 'vzctl', 'set', instance['id'],
                                      '--save', '--vmguarpages', vmguarpages)
            LOG.debug(out)
            if err:
                LOG.error(err)
        except ProcessExecutionError as err:
            LOG.error(err)
            raise exception.Error("Cannot set vmguarpages for %s" %
                                  instance['id'])

    def _set_privvmpages(self, instance):
        """
        Set the privvmpages attribute for a container.  This represents the
        memory allocation limit.  Think of this as a bursting limit.  For now
        We are setting to the same as vmguarpages but in the future this can be
        used to thin provision a box.
        """
        privvmpages = self._calc_pages(instance)

        try:
            out, err = utils.execute('sudo', 'vzctl', 'set', instance['id'],
                                     '--save', '--privvmpages', privvmpages)
            LOG.debug(out)
            if err:
                LOG.error(err)
        except ProcessExecutionError as err:
            LOG.error(err)
            raise exception.Error("Cannot set privvmpages for %s" %
                                  instance['id'])

    def _set_cpuunits(self, instance, units=None):
        """
        Set the cpuunits setting for the container.  This is an integer
        representing the number of cpu fair scheduling counters that the
        container has access to during one complete cycle.
        """
        if not units:
            LOG.debug("Reported cpuunits %s" % self.utility['UNITS'])
            LOG.debug("Reported percent of resource: %s" %
                      self._percent_of_resource(instance))
            units = int(self.utility['UNITS'] *
                        self._percent_of_resource(instance))
            # TODO(imsplitbit): This needs to be adjusted to not allow
            # subscription of more than available cpuunits.  For now we
            # won't let the obvious case of a container getting more than
            # the maximum cpuunits for the host.
            if units > self.utility['UNITS']:
                units = self.utility['UNITS']

        try:
            out, err = utils.execute('sudo', 'vzctl', 'set', instance['id'],
                                     '--save', '--cpuunits', units)
            LOG.debug(out)
            if err:
                LOG.error(err)
        except ProcessExecutionError as err:
            LOG.error(err)
            raise exception.Error('Cannot set cpuunits for %s' %
                                  (instance['id'],))

    def _set_cpulimit(self, instance, cpulimit=None):
        """
        This is a number in % equal to the amount of cpu processing power
        the container gets.  NOTE: 100% is 1 logical cpu so if you have 12
        cores with hyperthreading enabled then 100% of the whole host machine
        would be 2400% or --cpulimit 2400.
        """

        if not cpulimit:
            cpulimit = int(self.utility['CPULIMIT'] *
                           self._percent_of_resource(instance))
            # TODO(imsplitbit): Need to fix this so that we don't alocate
            # more than the current available resource limits.  This shouldn't
            # happen except in test cases but we should still protect
            # ourselves from it.  For now we just won't let it go higher
            # than the maximum cpulimit for the host on any one container.
            if cpulimit > self.utility['CPULIMIT']:
                cpulimit = self.utility['CPULIMIT']

        try:
            out, err = utils.execute('sudo', 'vzctl', 'set', instance['id'],
                                     '--save', '--cpulimit', cpulimit)
            LOG.debug(out)
            if err:
                LOG.error(err)
        except ProcessExecutionError as err:
            LOG.error(err)
            raise exception.Error('Unable to set cpulimit for %s' %
                                  (instance['id'],))

    def _set_cpus(self, instance, cpus=None, multiplier=2):
        """
        The number of logical cpus that are made available to the container.
        """
        if not cpus:
            inst_typ = instance_types.get_instance_type(
                instance['instance_type_id']
            )
            cpus = int(inst_typ['vcpus']) * multiplier
            # TODO(imsplitbit): We need to fix this to not allow allocation of
            # more than the maximum allowed cpus on the host.
            if cpus > (self.utility['CPULIMIT'] / 100):
                cpus = self.utility['CPULIMIT'] / 100

        try:
            out, err = utils.execute('sudo', 'vzctl', 'set', instance['id'],
                                     '--save', '--cpus', cpus)
            LOG.debug(out)
            if err:
                LOG.error(err)
        except ProcessExecutionError as err:
            LOG.error(err)
            raise exception.Error('Unable to set cpus for %s' %
                                  (instance['id'],))

    def _set_ioprio(self, instance, ioprio=None):
        """
        Set the IO priority setting for a given container.  This is represented
        by an integer between 0 and 7.  If no priority is given one will be
        automatically calculated based on the percentage of allocated memory
        for the container.
        """
        if not ioprio:
            ioprio = int(self._percent_of_resource(instance) * float(
                FLAGS.ovz_ioprio_limit))

        try:
            out, err = utils.execute('sudo', 'vzctl', 'set', instance['id'],
                                     '--save', '--ioprio', ioprio)
            LOG.debug(out)
            if err:
                LOG.error(err)
        except ProcessExecutionError as err:
            LOG.error(err)
            raise exception.Error('Unable to set IO priority for %s' % (
                instance['id'],))

    def _set_diskspace(self, instance, soft=None, hard=None):
        """
        Implement OpenVz disk quotas for local disk space usage.
        This method takes a soft and hard limit.  This is also the amount
        of diskspace that is reported by system tools such as du and df inside
        the container.  If no argument is given then one will be calculated
        based on the values in the instance_types table within the database.
        """
        instance_type = instance_types.get_instance_type(
            instance['instance_type_id'])

        if not soft:
            soft = int(instance_type['local_gb'])

        if not hard:
            hard = int(instance_type['local_gb'] *
                       FLAGS.ovz_disk_space_oversub_percent)

        # Now set the increment of the limit.  I do this here so that I don't
        # have to do this in every line above.
        soft = '%s%s' % (soft, FLAGS.ovz_disk_space_increment)
        hard = '%s%s' % (hard, FLAGS.ovz_disk_space_increment)

        try:
            out, err = utils.execute('sudo', 'vzctl', 'set', instance['id'],
                                     '--save', '--diskspace', '%s:%s' %
                                                              (soft, hard))
            LOG.debug(out)
            if err:
                LOG.error(err)
        except ProcessExecutionError as err:
            LOG.error(err)
            raise exception.Error('Error setting diskspace quota for %s' %
                                  (instance['id'],))

    def snapshot(self, instance, name):
        """
        Snapshots the specified instance.

        The given parameter is an instance of nova.compute.service.Instance,
        and so the instance is being specified as instance.name.

        The second parameter is the name of the snapshot.

        The work will be done asynchronously.  This function returns a
        task that allows the caller to detect when it is complete.
        """
        # TODO(imsplitbit): Need to implement vzdump
        pass

    def reboot(self, instance):
        """
        Reboot the specified instance.

        The given parameter is an instance of nova.compute.service.Instance,
        and so the instance is being specified as instance.name.

        The work will be done asynchronously.  This function returns a
        task that allows the caller to detect when it is complete.
        """
        try:
            out, err = utils.execute('sudo', 'vzctl', 'restart',
                                     instance['id'])
            LOG.debug(out)
            if err:
                LOG.error(err)
        except ProcessExecutionError:
            raise exception.Error('Failed to restart container: %d' %
                                  instance['id'])

    def set_admin_password(self, instance, new_pass):
        """
        Set the root password on the specified instance.

        The first parameter is an instance of nova.compute.service.Instance,
        and so the instance is being specified as instance.name. The second
        parameter is the value of the new password.

        The work will be done asynchronously.  This function returns a
        task that allows the caller to detect when it is complete.
        """
        pass

    def rescue(self, instance):
        """
        Rescue the specified instance.
        """
        pass

    def unrescue(self, instance):
        """
        Unrescue the specified instance.
        """
        pass

    def pause(self, instance, callback):
        """
        Pause the specified instance.
        """
        self._stop(instance)

    def unpause(self, instance, callback):
        """
        Unpause the specified instance.
        """
        self._start(instance)

    def suspend(self, instance, callback):
        """
        suspend the specified instance
        """
        self._stop(instance)

    def resume(self, instance, callback):
        """
        resume the specified instance
        """
        self._start(instance)

    def destroy(self, instance, network_info=None):
        """
        Destroy (shutdown and delete) the specified instance.

        The given parameter is an instance of nova.compute.service.Instance,
        and so the instance is being specified as instance.name.

        The work will be done asynchronously.  This function returns a
        task that allows the caller to detect when it is complete.
        """
        # TODO(imsplitbit): This needs to check the state of the VE
        # and if it isn't stopped it needs to stop it first.  This is
        # an openvz limitation that needs to be worked around.
        # For now we will assume it needs to be stopped prior to destroying it.
        self._stop(instance)

        try:
            out, err = utils.execute('sudo', 'vzctl', 'destroy',
                                     instance['id'])
            LOG.debug(out)
            if err:
                LOG.error(err)
        except ProcessExecutionError:
            raise exception.Error('Error destroying %d' % instance['id'])

    def _attach_volumes(self, instance):
        """
        Iterate through all volumes and attach them all.  This is just a helper
        method for self.spawn so that all volumes in the db get added to a
        container before it gets started.

        This will only attach volumes that have a filesystem uuid.  This is
        a limitation that is currently imposed by nova not storing the device
        name in the volumes table so we have no point of reference for which
        device goes where.
        """
        if instance['volumes']:
            for volume in instance['volumes']:
                if volume['uuid']:
                    self.attach_volume(instance['name'], None,
                                       volume['mountpoint'])

    def attach_volume(self, instance_name, device_path, mountpoint):
        """Attach the disk at device_path to the instance at mountpoint"""

        # Find the actual instance ref so we can see if it has a Reddwarf
        # friendly volume.  i.e. a formatted filesystem with UUID attribute
        # set.
        meta = self._find_by_name(instance_name)
        instance = db.instance_get(context.get_admin_context(), meta['id'])

        # Set volumes to none to account for the case that no volume is found
        volumes = None
        if instance['volumes']:
            for vol in instance['volumes']:
                if vol['mountpoint'] == mountpoint and vol['uuid']:
                    # Volume has a UUID so do all the mount magic using the
                    # UUID instead of the device name.
                    volumes = OVZVolumes(instance['id'], mountpoint, None,
                                         vol['uuid'])
                    LOG.debug('Adding volume %s to %s' %
                                (vol['uuid'], instance['id']))
                elif vol['mountpoint'] == mountpoint and device_path:
                    volumes = OVZVolumes(instance['id'], mountpoint,
                                         device_path, None)
                    LOG.debug('Adding volume %s to %s' %
                                (device_path, instance['id']))
        # If volumes is None we have problems.
        if volumes is None:
            LOG.error('No volume in the db for this instance')
            LOG.error('Instance: %s' % (instance_name,))
            LOG.error('Device: %s' % (device_path,))
            LOG.error('Mount: %s' % (mountpoint,))
            raise exception.Error('No volume in the db for this instance')
        else:
            # Run all the magic to make the mounts happen
            volumes.setup()
            volumes.attach()
            volumes.write_and_close()

    def detach_volume(self, instance_name, mountpoint):
        """Detach the disk attached to the instance at mountpoint"""

        # Find the instance ref so we can pass it to the
        # _mount_script_modify method.
        meta = self._find_by_name(instance_name)
        instance = db.instance_get(context.get_admin_context(), meta['id'])
        self._mount_script_modify(instance, None, None, mountpoint, 'del')
        volumes = OVZVolumes(instance['id'], mountpoint, None, None)
        volumes.setup()
        volumes.detach()
        volumes.write_and_close()

    def get_info(self, instance_name):
        """
        Get a block of information about the given instance.  This is returned
        as a dictionary containing 'state': The power_state of the instance,
        'max_mem': The maximum memory for the instance, in KiB, 'mem': The
        current memory the instance has, in KiB, 'num_cpu': The current number
        of virtual CPUs the instance has, 'cpu_time': The total CPU time used
        by the instance, in nanoseconds.

        This method should raise exception.NotFound if the hypervisor has no
        knowledge of the instance
        """
        try:
            meta = self._find_by_name(instance_name)
            instance = db.instance_get(context.get_admin_context(), meta['id'])
        except exception.NotFound as err:
            LOG.error(err)
            LOG.error('Instance %s Not Found' % instance_name)
            raise exception.NotFound('Instance %s Not Found' % instance_name)

        # Store the assumed state as the default
        state = instance['state']

        LOG.debug('Instance %s is in state %s' %
                  (instance['id'], instance['state']))

        if instance['state'] != power_state.NOSTATE:
            # NOTE(imsplitbit): This is not ideal but it looks like nova uses
            # codes returned from libvirt and xen which don't correlate to
            # the status returned from OpenVZ which is either 'running' or
            # 'stopped'.  There is some contention on how to handle systems
            # that were shutdown intentially however I am defaulting to the
            # nova expected behavior.
            if meta['state'] == 'running':
                state = power_state.RUNNING
            elif meta['state'] == None or meta['state'] == '-':
                state = power_state.NOSTATE
            else:
                state = power_state.SHUTDOWN

        # TODO(imsplitbit): Need to add all metrics to this dict.
        return {'state': state,
                'max_mem': 0,
                'mem': 0,
                'num_cpu': 0,
                'cpu_time': 0}

    def get_diagnostics(self, instance_name):
        pass

    def list_disks(self, instance_name):
        """
        Return the IDs of all the virtual disks attached to the specified
        instance, as a list.  These IDs are opaque to the caller (they are
        only useful for giving back to this layer as a parameter to
        disk_stats).  These IDs only need to be unique for a given instance.

        Note that this function takes an instance ID, not a
        compute.service.Instance, so that it can be called by compute.monitor.
        """
        return ['A_DISK']

    def list_interfaces(self, instance_name):
        """
        Return the IDs of all the virtual network interfaces attached to the
        specified instance, as a list.  These IDs are opaque to the caller
        (they are only useful for giving back to this layer as a parameter to
        interface_stats).  These IDs only need to be unique for a given
        instance.

        Note that this function takes an instance ID, not a
        compute.service.Instance, so that it can be called by compute.monitor.
        """
        return ['A_VIF']

    def block_stats(self, instance_name, disk_id):
        """
        Return performance counters associated with the given disk_id on the
        given instance_name.  These are returned as [rd_req, rd_bytes, wr_req,
        wr_bytes, errs], where rd indicates read, wr indicates write, req is
        the total number of I/O requests made, bytes is the total number of
        bytes transferred, and errs is the number of requests held up due to a
        full pipeline.

        All counters are long integers.

        This method is optional.  On some platforms (e.g. XenAPI) performance
        statistics can be retrieved directly in aggregate form, without Nova
        having to do the aggregation.  On those platforms, this method is
        unused.

        Note that this function takes an instance ID, not a
        compute.service.Instance, so that it can be called by compute.monitor.
        """
        return [0L, 0L, 0L, 0L, null]

    def interface_stats(self, instance_name, iface_id):
        """
        Return performance counters associated with the given iface_id on the
        given instance_id.  These are returned as [rx_bytes, rx_packets,
        rx_errs, rx_drop, tx_bytes, tx_packets, tx_errs, tx_drop], where rx
        indicates receive, tx indicates transmit, bytes and packets indicate
        the total number of bytes or packets transferred, and errs and dropped
        is the total number of packets failed / dropped.

        All counters are long integers.

        This method is optional.  On some platforms (e.g. XenAPI) performance
        statistics can be retrieved directly in aggregate form, without Nova
        having to do the aggregation.  On those platforms, this method is
        unused.

        Note that this function takes an instance ID, not a
        compute.service.Instance, so that it can be called by compute.monitor.
        """
        return [0L, 0L, 0L, 0L, 0L, 0L, 0L, 0L]

    def get_console_output(self, instance):
        return 'FAKE CONSOLE OUTPUT'

    def get_ajax_console(self, instance):
        return 'http://fakeajaxconsole.com/?token=FAKETOKEN'

    def get_console_pool_info(self, console_type):
        return  {'address': '127.0.0.1',
                 'username': 'fakeuser',
                 'password': 'fakepassword'}

    def refresh_security_group_rules(self, security_group_id):
        """This method is called after a change to security groups.

        All security groups and their associated rules live in the datastore,
        and calling this method should apply the updated rules to instances
        running the specified security group.

        An error should be raised if the operation cannot complete.

        """
        return True

    def refresh_security_group_members(self, security_group_id):
        """This method is called when a security group is added to an instance.

        This message is sent to the virtualization drivers on hosts that are
        running an instance that belongs to a security group that has a rule
        that references the security group identified by `security_group_id`.
        It is the responsiblity of this method to make sure any rules
        that authorize traffic flow with members of the security group are
        updated and any new members can communicate, and any removed members
        cannot.

        Scenario:
            * we are running on host 'H0' and we have an instance 'i-0'.
            * instance 'i-0' is a member of security group 'speaks-b'
            * group 'speaks-b' has an ingress rule that authorizes group 'b'
            * another host 'H1' runs an instance 'i-1'
            * instance 'i-1' is a member of security group 'b'

            When 'i-1' launches or terminates we will recieve the message
            to update members of group 'b', at which time we will make
            any changes needed to the rules for instance 'i-0' to allow
            or deny traffic coming from 'i-1', depending on if it is being
            added or removed from the group.

        In this scenario, 'i-1' could just as easily have been running on our
        host 'H0' and this method would still have been called.  The point was
        that this method isn't called on the host where instances of that
        group are running (as is the case with
        :method:`refresh_security_group_rules`) but is called where references
        are made to authorizing those instances.

        An error should be raised if the operation cannot complete.

        """
        return True

    def update_available_resource(self, ctxt, host):
        """
        Added because now nova requires this method
        """
        return

    def _calc_pages(self, instance, block_size=4096):
        """
        Returns the number of pages for a given size of storage/memory
        """
        instance_type = instance_types.get_instance_type(
            instance['instance_type_id'])
        return ((int(instance_type['memory_mb']) * 1024) * 1024) / block_size

    def _percent_of_resource(self, instance):
        """
        In order to evenly distribute resources this method will calculate a
        multiplier based on memory consumption for the allocated container and
        the overall host memory. This can then be applied to the cpuunits in
        self.utility to be passed as an argument to the self._set_cpuunits
        method to limit cpu usage of the container to an accurate percentage of
        the host.  This is only done on self.spawn so that later, should
        someone choose to do so, they can adjust the container's cpu usage
        up or down.
        """
        instance_type = instance_types.get_instance_type(
            instance['instance_type_id'])
        cont_mem_mb = float(instance_type['memory_mb']) / \
                      float(self.utility['MEMORY_MB'])

        # We shouldn't ever have more than 100% but if for some unforseen
        # reason we do, lets limit it to 1 to make all of the other
        # calculations come out clean.
        if cont_mem_mb > 1:
            LOG.error('_percent_of_resource came up with more than 100%')
            return 1
        else:
            return cont_mem_mb

    def _get_memory(self):
        """
        Gets the overall memory capacity of the host machine to be able to
        accurately compute how many cpuunits a container should get.  This is
        Linux specific code but because OpenVz only runs on linux this really
        isn't a problem.
        """
        try:
            out, err = utils.execute('sudo', 'cat', '/proc/meminfo')
            LOG.debug(out)
            if err:
                LOG.error(err)
            for line in out.splitlines():
                line = line.split()
                if line[0] == 'MemTotal:':
                    LOG.debug('Total memory for host %s MB' % (line[1],))
                    self.utility['MEMORY_MB'] = int(line[1]) / 1024
            return True

        except ProcessExecutionError as err:
            LOG.error('Cannot get memory info for host')
            LOG.error(err)
            raise exception.Error('Cannot get memory info for host')

    def _get_cpulimit(self):
        """
        Fetch the total possible cpu processing limit in percentage to be
        divided up across all containers.  This is expressed in percentage
        being added up by logical processor.  If there are 24 logical
        processors then the total cpulimit for the host node will be
        2400.
        """
        proc_count = 0
        try:
            out, err = utils.execute('sudo', 'cat', '/proc/cpuinfo')
            LOG.debug(out)
            if err:
                LOG.error(err)

            for line in out.splitlines():
                line = line.split()
                if len(line) > 0:
                    if line[0] == 'processor':
                        proc_count += 1

            self.utility['CPULIMIT'] = proc_count * 100
            return True

        except ProcessExecutionError as err:
            LOG.error('Cannot get host node cpulimit')
            LOG.error(err)
            raise exception.Error(err)

    def _get_cpuunits_capability(self):
        """
        Use openvz tools to discover the total processing capability of the
        host node.  This is done using the vzcpucheck utility.
        """
        try:
            out, err = utils.execute('sudo', 'vzcpucheck')
            LOG.debug(out)
            if err:
                LOG.error(err)

            for line in out.splitlines():
                line = line.split()
                if len(line) > 0:
                    if line[0] == 'Power':
                        LOG.debug('Power of host: %s' % (line[4],))
                        self.utility['UNITS'] = int(line[4])

        except ProcessExecutionError as err:
            LOG.error(err)
            raise exception.Error('Problem getting cpuunits for host')

    def _get_cpuunits_usage(self):
        """
        Use openvz tools to discover the total used processing power. This is
        done using the vzcpucheck -v command.
        """
        try:
            out, err = utils.execute('sudo', 'vzcpucheck', '-v')
            LOG.debug(out)
            if err:
                LOG.error(err)

            for line in out.splitlines():
                line = line.split()
                if len(line) > 0:
                    if line[0] == 'Current':
                        LOG.debug('Current usage of host: %s' % (line[3],))
                        self.utility['TOTAL'] = int(line[3])
                    elif line[0].isdigit():
                        LOG.debug('Usage for CTID %s: %s' % (line[0], line[1]))
                        self.utility['CTIDS'][line[0]] = line[1]

        except ProcessExecutionError as err:
            LOG.error(err)
            raise exception.Error('Problem getting cpuunits for host')

        return True


class OVZFile(object):
    """
    This is a generic file class for wrapping up standard file operations that
    may need to run on files associated with OpenVz
    """
    def __init__(self, filename):
        self.filename = filename
        self.contents = []

    def read(self):
        """
        Open the file for reading only and read it's contents into the instance
        attribute self.contents
        """
        try:
            with open(self.filename, 'r') as fh:
                self.contents = fh.readlines()
        except Exception as err:
            LOG.error(err)
            raise exception.Error('Failed to read %s' % (self.filename,))

    def write(self):
        """
        Because self.contents may or may not get manipulated throughout the
        process, this is a method used to dump the contents of self.contents
        back into the file that this object represents.
        """
        try:
            with open(self.filename, 'w') as fh:
                fh.writelines('\n'.join(self.contents) + '\n')
        except Exception as err:
            LOG.error(err)
            raise exception.Error('Failed to write %s' % (self.filename,))

    def touch(self):
        """
        There are certain conditions where we create an OVZFile object but that
        file may or may not exist and this provides us with a way to create
        that file if it doesn't exist.
        """
        self.make_path()
        try:
            out, err = utils.execute('sudo', 'touch', self.filename)
            LOG.debug(out)
            if err:
                LOG.error(err)
        except ProcessExecutionError as err:
            LOG.error(err)
            raise exception.Error('Failed to touch %s' % (self.filename,))

    def append(self, contents):
        """
        Add the argument contents to the end of self.contents
        """
        if isinstance(contents, str):
            contents = [contents]
        self.contents = self.contents + contents

    def prepend(self, contents):
        """
        Add the argument contents to the beginning of self.contents
        """
        if isinstance(contents, str):
            contents = [contents]
        self.contents = contents + self.contents

    def delete(self, contents):
        """
        Delete the argument contents from self.contents if they exist.
        """
        if isinstance(contents, list):
            for line in contents:
                self.remove_line(line)
        else:
            self.remove_line(contents)

    def remove_line(self, line):
        """
        Simple helper method to actually do the removal of a line from an array
        """
        if line in self.contents:
            self.contents.remove(line)

    def set_permissions(self, permissions):
        """
        Because nova runs as an unprivileged user we need a way to mangle
        permissions on files that may be owned by root for manipulation
        """
        try:
            out, err = utils.execute('sudo', 'chmod', permissions,
                                     self.filename)
            LOG.debug(out)
            if err:
                LOG.error(err)
        except exception.Error as err:
            LOG.error(err)
            raise exception.Error('Unable to set permissions on %s'
                                  % (self.filename,))

    def make_path(self, path=None):
        """
        Helper method for an OVZFile object to be able to create the path for
        self.filename if it doesn't exist before running touch()
        """
        if not path:
            path = self.filename
        basedir = os.path.dirname(path)
        self.make_dir(basedir)

    @staticmethod
    def make_dir(path):
        """
        This is the method that actually creates directories. This is used by
        make_path and can be called directly as a utility to create
        directories.
        """
        try:
            if not os.path.exists(path):
                LOG.debug('Path %s doesnt exist, creating now' % (path,))
                out, err = utils.execute('sudo', 'mkdir', '-p', path)
                LOG.debug(out)
                if err:
                    LOG.error(err)
            else:
                LOG.debug('Path %s exists, skipping' % (path,))
        except ProcessExecutionError as err:
            LOG.error(err)
            raise exception.Error('Unable to make %s' % (path,))


class OVZMounts(OVZFile):
    """
    OVZMounts is a sub-class of OVZFile that applies mount/umount file specific
    operations to the object.
    """
    def __init__(self, filename, mount, instance_id, device=None, uuid=None):
        super(OVZMounts, self).__init__(filename)
        self.device = device
        self.uuid = uuid

        # Generate the mountpoint paths
        self.container_mount = '%s/%s/%s' % \
                       (FLAGS.ovz_ve_private_dir, instance_id, mount)
        self.container_root_mount = '%s/%s/%s' % \
                            (FLAGS.ovz_ve_root_dir, instance_id, mount)
        self.host_mount = '%s/%s/%s' % \
                        (FLAGS.ovz_ve_host_mount_dir, instance_id, mount)
        # Fix mounts to remove duplicate slashes
        self.container_mount = os.path.abspath(self.container_mount)
        self.container_root_mount = os.path.abspath(self.container_root_mount)
        self.host_mount = os.path.abspath(self.host_mount)

    def format(self):
        """
        OpenVz mount and umount files must be properly formatted scripts.  I
        prepend the proper shell script header to the files
        """
        if len(self.contents) > 0:
            if not self.contents[0] == '#!/bin/sh':
                self.prepend('#!/bin/sh')
        else:
            self.prepend('#!/bin/sh')


class OVZMountFile(OVZMounts):
    """
    methods used to specifically interact with the /etc/vz/conf/CTID.mount file
    that handles all mounted filesystems for containers.
    """
    def host_mount_line(self):
        """
        OpenVz is unlike most hypervisors in that it cannot actually do
        anything with raw devices. When migrating containers from host to host
        you are not guaranteed to have the same device name on each host so we
        need a conditional that generates a mount line that can use a UUID
        attribute that can be added to a filesystem which allows us to be
        device name agnostic.
        """
        #TODO(imsplitbit): Add LABEL= to allow for disk labels as well
        if self.device:
            mount_line = 'mount %s %s' % (self.device, self.host_mount)
        elif self.uuid:
            mount_line = 'mount UUID=%s %s' % (self.uuid, self.host_mount)
        else:
            LOG.error('No device or uuid given')
            raise exception.Error('No device or uuid given')
        return mount_line

    def container_mount_line(self):
        """
        Generate a mount line that will allow OpenVz to mount a filesystem
        within the container's root filesystem.  This is done with the bind
        mount feature and is the prescribed method for OpenVz
        """
        return 'mount --bind %s %s' % \
               (self.host_mount, self.container_root_mount)

    def delete_mounts(self):
        """
        When detaching a volume from a container we need to also remove the
        mount statements from the CTID.mount file.
        """
        self.delete(self.host_mount_line())
        self.delete(self.container_mount_line())

    def add_container_mount_line(self):
        """
        Add the generated container mount line to the CTID.mount script
        """
        self.append(self.container_mount_line())

    def add_host_mount_line(self):
        """
        Add the generated host mount line to the CTID.mount script
        """
        self.append(self.host_mount_line())

    def make_host_mount_point(self):
        """
        Create the host mount point if it doesn't exist.  This is required
        to allow for container startup.
        """
        self.make_dir(self.host_mount)

    def make_container_mount_point(self):
        """
        Create the container private mount point if it doesn't exist.  This is
        required to happen before the container starts so that when it chroots
        in /vz/root/CTID the path will exist to match container_root_mount
        """
        self.make_dir(self.container_mount)

    def make_container_root_mount_point(self):
        """
        Unused at the moment but exists in case we reach a condition that the
        container starts and somehow make_container_mount_point didn't get run.
        """
        # TODO(imsplitbit): Look for areas this can be used.  Right now the
        # process is very prescibed so it doesn't appear necessary just yet.
        # We will need this in the future when we do more dynamic operations.
        self.make_dir(self.container_root_mount)


class OVZUmountFile(OVZMounts):
    """
    methods to be used for manipulating the CTID.umount files
    """
    def host_umount_line(self):
        """
        Generate a umount line to compliment the host mount line added for the
        filesystem in OVZMountFile
        """
        return self._umount_line(self.host_mount)

    def container_umount_line(self):
        """
        Generate a umount line to compliment the container mount line added for
        the filesystem in OVZMountFile
        """
        return self._umount_line(self.container_root_mount)

    @staticmethod
    def _umount_line(mount):
        """
        Helper method to assemble a umount line for CTID.umount.  This uses
        lazy and force to unmount the filesystem because in the condition that
        you are detaching a volume it is assumed that a potentially dirty
        filesystem isn't a concern and in the case that the container is just
        stopped the filesystem will already have all descriptors closed so the
        lazy forced unmount has no adverse affect.
        """
        return 'umount -l -f %s' % (mount,)

    def add_host_umount_line(self):
        """
        Add the host umount line to the CTID.umount file
        """
        self.append(self.host_umount_line())

    def add_container_umount_line(self):
        """
        Add the container umount line to the CTID.umount file
        """
        self.append(self.container_umount_line())

    def delete_umounts(self):
        """
        In the case that we need to detach a volume from a container we need to
        remove the umount lines from the file object's contents.
        """
        self.delete(self.container_umount_line())
        self.delete(self.host_umount_line())

    def unmount_all(self):
        """
        Wrapper for unmounting both the container mounted filesystem and the
        original host mounted filesystem
        """
        # Unmount the container mount
        self.unmount(self.container_umount_line())

        # Now unmount the host mount
        self.unmount(self.host_umount_line)

    @staticmethod
    def unmount(mount_line):
        """
        Helper method to use nova commandline utilities to unmount the
        filesystem given as an argument.
        """
        try:
            out, err = utils.execute(mount_line.split())
            LOG.debug(out)
            if err:
                LOG.error(err)
        except ProcessExecutionError as err:
            LOG.error(err)
            raise exception.Error('Failed to umount: "%s"' % (mount_line,))


class OVZVolumes(object):
    """
    This Class is a helper class to manage the mount and umount files
    for a given container.
    """
    def __init__(self, instance_id, mount, dev=None, uuid=None):
        self.instance_id = instance_id
        self.mountpoint = mount
        self.device = dev
        self.uuid = uuid
        self.mountfile = '%s/%s.mount' % (FLAGS.ovz_config_dir,
                                          self.instance_id)
        self.umountfile = '%s/%s.umount' % (FLAGS.ovz_config_dir,
                                            self.instance_id)
        self.mountfile = os.path.abspath(self.mountfile)
        self.umountfile = os.path.abspath(self.umountfile)

    def setup(self):
        """
        Prep the paths and files for manipulation.
        """
        # Create the file objects
        self.mountfh = OVZMountFile(self.mountfile, self.mountpoint,
                                    self.instance_id, self.device, self.uuid)
        self.umountfh = OVZUmountFile(self.umountfile, self.mountpoint,
                                      self.instance_id, self.device, self.uuid)

        # Create the files if they don't exist
        self.mountfh.touch()
        self.umountfh.touch()

        # Fix the permissions on the files to allow this script to edit them
        self.mountfh.set_permissions(777)
        self.umountfh.set_permissions(777)

        # Now open the mount/umount files and read their contents
        self.mountfh.read()
        self.umountfh.read()

        # Fixup the mount and umount files to have proper shell script
        # header otherwise it will be rejected by vzctl
        self.mountfh.format()
        self.umountfh.format()

    def attach(self):
        # Create the mount point on the host node
        self.mountfh.make_host_mount_point()
        # Create a mount point for the device inside the root of the container
        self.mountfh.make_container_mount_point()

        # Add the host and container mount lines to the mount script
        self.mountfh.add_host_mount_line()
        self.mountfh.add_container_mount_line()

        # Add umount lines to the umount script
        self.umountfh.add_container_umount_line()
        self.umountfh.add_host_umount_line()

    def detach(self):
        # Unmount the storage if possible
        self.umountfh.unmount_all()

        # If the lines of the mount and unmount statements are in the
        # container mount and umount files, remove them.
        self.mountfh.delete_mounts()
        self.umountfh.delete_umounts()

    def write_and_close(self):
        # Reopen the files and write the contents to them
        self.mountfh.write()
        self.umountfh.write()

        # Finish by setting the permissions back to more secure permissions
        self.mountfh.set_permissions(755)
        self.umountfh.set_permissions(755)
