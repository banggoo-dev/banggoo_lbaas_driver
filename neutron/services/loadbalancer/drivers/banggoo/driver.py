import bg_conf
from oslo.config import cfg

from neutron.api.v2 import attributes
from neutron.db.loadbalancer import loadbalancer_db
from neutron.openstack.common import log as logging
from neutron.plugins.common import constants
from neutron.services.loadbalancer.drivers import abstract_driver
from neutron.services.loadbalancer.drivers.banggoo import bg_client
from neutron.common import exceptions as qexception
from neutron.extensions import loadbalancer

LOG = logging.getLogger(__name__)

VIPS_RESOURCE = 'vips'
VIP_RESOURCE = 'vip'
POOLS_RESOURCE = 'pools'
POOL_RESOURCE = 'pool'
POOLMEMBERS_RESOURCE = 'members'
POOLMEMBER_RESOURCE = 'member'
MONITORS_RESOURCE = 'healthmonitors'
MONITOR_RESOURCE = 'healthmonitor'
POOLSTATS_RESOURCE = 'statistics'
PROV_SEGMT_ID = 'provider:segmentation_id'
PROV_NET_TYPE = 'provider:network_type'
DRIVER_NAME = 'banggoo'

BG_CONF = bg_conf.cfgparse()

driver_opts = [
    cfg.StrOpt('adc_address',
               default=BG_CONF.get('adc_address'),
               help=_('IP address of vDirect server.')),
    cfg.StrOpt('adc_user',
               default=BG_CONF.get('adc_user'),
               help=_('vDirect user name.')),
    cfg.StrOpt('adc_password',
               default=BG_CONF.get('adc_password'),
               help=_('vDirect user password.')),
]

cfg.CONF.register_opts(driver_opts, "banggoo")


class PoolParaError(qexception.NeutronException):
    message = _("Parameter error.")


class BanggooLoadBalancerDriver(abstract_driver.LoadBalancerAbstractDriver):

    """Banggoo LBaaS Plugin driver class."""

    def __init__(self, plugin):
        self.plugin = plugin
        ip = cfg.CONF.banggoo.adc_address
        username = cfg.CONF.banggoo.adc_user
        password = cfg.CONF.banggoo.adc_password
        LOG.error("ip=%s user=%s password=%s" % (cfg.CONF.banggoo.values(), username,password))
        self.client = bg_client.BGClient(ip, username, password)

    def create_vip(self, context, vip):
        """Create a vip on a Banggoo device."""
        network_info = self._get_vip_network_info(context, vip)
        bg_vip = self._prepare_vip_for_creation(vip)
        bg_vip = dict(bg_vip.items() + network_info.items())
        msg = _("Banggoo driver vip creation: %s") % repr(bg_vip)
        LOG.debug(msg)
        status = constants.ACTIVE
        try:
            self.client.create_resource(context.tenant_id, VIPS_RESOURCE,
                                        VIP_RESOURCE, bg_vip)
        except bg_client.BGException:
            status = constants.ERROR
            self.plugin._delete_db_vip(context, vip['id'])
            raise PoolParaError

        self.plugin.update_status(context, loadbalancer_db.Vip, vip["id"],
                                  status)

    def update_vip(self, context, old_vip, vip):
        """Update a vip on a Banggoo device."""
        update_vip = self._prepare_vip_for_update(vip)
        resource_path = "%s/%s" % (VIPS_RESOURCE, vip["id"])
        msg = (_("Banggoo driver vip %(vip_id)s update: %(vip_obj)s") %
               {"vip_id": vip["id"], "vip_obj": repr(vip)})
        LOG.debug(msg)
        status = constants.ACTIVE
        try:
            self.client.update_resource(context.tenant_id, resource_path,
                                        VIP_RESOURCE, update_vip)
        except bg_client.BGException:
            status = constants.ERROR
            raise PoolParaError
        self.plugin.update_status(context, loadbalancer_db.Vip, old_vip["id"],
                                  status)

    def delete_vip(self, context, vip):
        """Delete a vip on a Banggoo device."""
        resource_path = "%s/%s" % (VIPS_RESOURCE, vip["id"])
        msg = _("Banggoo driver vip removal: %s") % vip["id"]
        LOG.debug(msg)
        try:
            self.client.remove_resource(context.tenant_id, resource_path)
            self.plugin._delete_db_vip(context, vip['id'])
        except bg_client.BGException:
            self.plugin.update_status(context, loadbalancer_db.Vip,
                                      vip["id"],
                                      constants.ERROR)
            raise PoolParaError

    def create_pool(self, context, pool):
        """Create a pool on a Banggoo device."""
        network_info = self._get_pool_network_info(context, pool)
        #allocate a snat port/ipaddress on the subnet if one doesn't exist
        self._create_snatport_for_subnet_if_not_exists(context,
                                                       pool['tenant_id'],
                                                       pool['subnet_id'],
                                                       network_info)
        bg_pool = self._prepare_pool_for_creation(pool)
        bg_pool = dict(bg_pool.items() + network_info.items())
        msg = _("Banggoo driver pool creation: %s") % repr(bg_pool)
        LOG.debug(msg)
        status = constants.ACTIVE
        try:
            #raise loadbalancer.NoEligibleBackend(pool_id=pool['id'])
            #raise loadbalancer.PoolInUse(pool_id=pool['id'])
            #raise PoolParaError
            self.client.create_resource(context.tenant_id, POOLS_RESOURCE,
                                        POOL_RESOURCE, bg_pool)

        except bg_client.BGException:
            status = constants.ERROR
            self.plugin._delete_db_pool(context, bg_pool['id'])
            raise PoolParaError

        self.plugin.update_status(context, loadbalancer_db.Pool,
                                  bg_pool["id"], status)

    def update_pool(self, context, old_pool, pool):
        """Update a pool on a Banggoo device."""
        bg_pool = self._prepare_pool_for_update(pool)
        resource_path = "%s/%s" % (POOLS_RESOURCE, old_pool["id"])
        msg = (_("Banggoo driver pool %(pool_id)s update: %(pool_obj)s") %
               {"pool_id": old_pool["id"], "pool_obj": repr(bg_pool)})
        LOG.debug(msg)
        status = constants.ACTIVE
        try:
            self.client.update_resource(context.tenant_id, resource_path,
                                        POOL_RESOURCE, bg_pool)
        except bg_client.BGException:
            status = constants.ERROR
            raise PoolParaError
        self.plugin.update_status(context, loadbalancer_db.Pool,
                                  old_pool["id"], status)

    def delete_pool(self, context, pool):
        """Delete a pool on a Banggoo device."""
        resource_path = "%s/%s" % (POOLS_RESOURCE, pool['id'])
        msg = _("Banggoo driver pool removal: %s") % pool["id"]
        LOG.debug(msg)
        status = constants.ACTIVE
        try:
            self.client.remove_resource(context.tenant_id, resource_path)

            self.plugin._delete_db_pool(context, pool['id'])
            self._remove_snatport_for_subnet_if_not_used(context,pool['tenant_id'],pool['subnet_id'])
        except bg_client.BGException:
            status = constants.ERROR
            self.plugin.update_status(context, loadbalancer_db.Pool,pool["id"],status)
            raise PoolParaError

        #self.plugin.update_status(context, loadbalancer_db.Pool,pool["id"],status)


    def create_member(self, context, member):
        """Create a pool member on a Banggoo device."""
        bg_member = self._prepare_member_for_creation(member)
        msg = (_("Banggoo driver poolmember creation: %s") %
               repr(bg_member))
        LOG.info(msg)
        status = constants.ACTIVE
        try:
            self.client.create_resource(context.tenant_id,
                                        POOLMEMBERS_RESOURCE,
                                        POOLMEMBER_RESOURCE,
                                        bg_member)
        except bg_client.BGException:
            status = constants.ERROR
            self.plugin._delete_db_member(context, member['id'])
            raise PoolParaError
        self.plugin.update_status(context, loadbalancer_db.Member,
                                  member["id"], status)

    def update_member(self, context, old_member, member):
        """Update a pool member on a Banggoo device."""
        bg_member = self._prepare_member_for_update(member)
        resource_path = "%s/%s" % (POOLMEMBERS_RESOURCE, old_member["id"])
        msg = (_("Banggoo driver poolmember %(member_id)s update:"
                 " %(member_obj)s") %
               {"member_id": old_member["id"],
                "member_obj": repr(bg_member)})
        LOG.debug(msg)
        status = constants.ACTIVE
        try:
            self.client.update_resource(context.tenant_id, resource_path,
                                        POOLMEMBER_RESOURCE, bg_member)
        except bg_client.BGException:
            status = constants.ERROR
            raise PoolParaError
        self.plugin.update_status(context, loadbalancer_db.Member,
                                  old_member["id"], status)

    def delete_member(self, context, member):
        """Delete a pool member on a Banggoo device."""
        resource_path = "%s/%s" % (POOLMEMBERS_RESOURCE, member['id'])
        msg = (_("Banggoo driver poolmember removal: %s") %
               member["id"])
        LOG.debug(msg)
        try:
            self.client.remove_resource(context.tenant_id, resource_path)
            self.plugin._delete_db_member(context, member['id'])
        except bg_client.BGException:
            self.plugin.update_status(context, loadbalancer_db.Member,
                                      member["id"],
                                      constants.ERROR)
            raise PoolParaError

    #def create_health_monitor(self, context, health_monitor):
    #    """Create a pool health monitor on a Banggoo device."""

    def create_pool_health_monitor(self, context, health_monitor, pool_id):
        """Create a pool health monitor on a Banggoo device."""
        bg_hm = self._prepare_healthmonitor_for_creation(health_monitor,
                                                          pool_id)
        resource_path = "%s/%s/%s" % (POOLS_RESOURCE, pool_id,
                                      MONITORS_RESOURCE)
        msg = (_("Banggoo driver healthmonitor creation for pool %(pool_id)s"
                 ": %(monitor_obj)s") %
               {"pool_id": pool_id,
                "monitor_obj": repr(bg_hm)})
        LOG.debug(msg)
        status = constants.ACTIVE
        try:
            self.client.create_resource(context.tenant_id, resource_path,
                                        MONITOR_RESOURCE,
                                        bg_hm)
        except bg_client.BGException:
            status = constants.ERROR
            self.plugin._delete_db_pool_health_monitor(context,
                                                       health_monitor['id'],
                                                       pool_id)
            raise PoolParaError
        self.plugin.update_pool_health_monitor(context,
                                               health_monitor['id'],
                                               pool_id,
                                               status, "")

    def update_pool_health_monitor(self, context, old_health_monitor,
                                   health_monitor, pool_id):
        """Update a pool health monitor on a Banggoo device."""
        bg_hm = self._prepare_healthmonitor_for_update(health_monitor)
        resource_path = "%s/%s" % (MONITORS_RESOURCE,
                                   old_health_monitor["id"])
        msg = (_("Banggoo driver healthmonitor %(monitor_id)s update: "
                 "%(monitor_obj)s") %
               {"monitor_id": old_health_monitor["id"],
                "monitor_obj": repr(bg_hm)})
        LOG.debug(msg)
        status = constants.ACTIVE
        try:
            self.client.update_resource(context.tenant_id, resource_path,
                                        MONITOR_RESOURCE, bg_hm)
        except bg_client.BGException:
            status = constants.ERROR
            raise PoolParaError
        self.plugin.update_pool_health_monitor(context,
                                               old_health_monitor['id'],
                                               pool_id,
                                               status, "")

    def delete_pool_health_monitor(self, context, health_monitor, pool_id):
        """Delete a pool health monitor on a Banggoo device."""
        resource_path = "%s/%s/%s/%s" % (POOLS_RESOURCE, pool_id,
                                         MONITORS_RESOURCE,
                                         health_monitor["id"])
        msg = (_("Banggoo driver healthmonitor %(monitor_id)s"
                 "removal for pool %(pool_id)s") %
               {"monitor_id": health_monitor["id"],
                "pool_id": pool_id})
        LOG.debug(msg)
        try:
            self.client.remove_resource(context.tenant_id, resource_path)
            self.plugin._delete_db_pool_health_monitor(context,health_monitor['id'],pool_id)
        except bg_client.BGException:
            self.plugin.update_pool_health_monitor(context,
                                                   health_monitor['id'],
                                                   pool_id,
                                                   constants.ERROR, "")
            raise PoolParaError

    def stats(self, context, pool_id):
        """Retrieve pool statistics from the Banggoo device."""
        resource_path = "%s/%s" % (POOLSTATS_RESOURCE, pool_id)
        msg = _("Banggoo driver pool stats retrieval: %s") % pool_id
        LOG.debug(msg)
        try:
            stats = self.client.retrieve_resource(context.tenant_id,
                                                  resource_path)[1]
        except bg_client.BGException:
            self.plugin.update_status(context, loadbalancer_db.Pool,
                                      pool_id, constants.ERROR)
        else:
            return stats

    def _prepare_vip_for_creation(self, vip):
        creation_attrs = {
            'id': vip['id'],
            'tenant_id': vip['tenant_id'],
            'protocol': vip['protocol'],
            'address': vip['address'],
            'protocol_port': vip['protocol_port'],
        }
        if 'session_persistence' in vip:
            creation_attrs['session_persistence'] = vip['session_persistence']
        update_attrs = self._prepare_vip_for_update(vip)
        creation_attrs.update(update_attrs)
        return creation_attrs

    def _prepare_vip_for_update(self, vip):
        return {
            'name': vip['name'],
            'description': vip['description'],
            'pool_id': vip['pool_id'],
            'connection_limit': vip['connection_limit'],
            'admin_state_up': vip['admin_state_up'],
            'session_persistence':vip['session_persistence']
        }

    def _prepare_pool_for_creation(self, pool):
        creation_attrs = {
            'id': pool['id'],
            'tenant_id': pool['tenant_id'],
            'vip_id': pool['vip_id'],
            'protocol': pool['protocol'],
            'subnet_id': pool['subnet_id'],
        }
        update_attrs = self._prepare_pool_for_update(pool)
        creation_attrs.update(update_attrs)
        return creation_attrs

    def _prepare_pool_for_update(self, pool):
        return {
            'name': pool['name'],
            'description': pool['description'],
            'lb_method': pool['lb_method'],
            'admin_state_up': pool['admin_state_up']
        }

    def _prepare_member_for_creation(self, member):
        creation_attrs = {
            'id': member['id'],
            'tenant_id': member['tenant_id'],
            'address': member['address'],
            'protocol_port': member['protocol_port'],
        }
        update_attrs = self._prepare_member_for_update(member)
        creation_attrs.update(update_attrs)
        return creation_attrs

    def _prepare_member_for_update(self, member):
        return {
            'pool_id': member['pool_id'],
            'weight': member['weight'],
            'admin_state_up': member['admin_state_up']
        }

    def _prepare_healthmonitor_for_creation(self, health_monitor, pool_id):
        creation_attrs = {
            'id': health_monitor['id'],
            'tenant_id': health_monitor['tenant_id'],
            'type': health_monitor['type'],
        }
        update_attrs = self._prepare_healthmonitor_for_update(health_monitor)
        creation_attrs.update(update_attrs)
        return creation_attrs

    def _prepare_healthmonitor_for_update(self, health_monitor):
        bg_hm = {
            'delay': health_monitor['delay'],
            'timeout': health_monitor['timeout'],
            'max_retries': health_monitor['max_retries'],
            'admin_state_up': health_monitor['admin_state_up']
        }
        if health_monitor['type'] in ['HTTP', 'HTTPS']:
            bg_hm['http_method'] = health_monitor['http_method']
            bg_hm['url_path'] = health_monitor['url_path']
            bg_hm['expected_codes'] = health_monitor['expected_codes']
        return bg_hm

    def _get_network_info(self, context, entity):
        network_info = {}
        subnet_id = entity['subnet_id']
        subnet = self.plugin._core_plugin.get_subnet(context, subnet_id)
        network_id = subnet['network_id']
        network = self.plugin._core_plugin.get_network(context, network_id)
        network_info['network_id'] = network_id
        network_info['subnet_id'] = subnet_id
        if PROV_NET_TYPE in network:
            network_info['network_type'] = network[PROV_NET_TYPE]
        if PROV_SEGMT_ID in network:
            network_info['segmentation_id'] = network[PROV_SEGMT_ID]
        return network_info

    def _get_vip_network_info(self, context, vip):
        network_info = self._get_network_info(context, vip)
        network_info['port_id'] = vip['port_id']
        return network_info

    def _get_pool_network_info(self, context, pool):
        return self._get_network_info(context, pool)

    def _get_pools_on_subnet(self, context, tenant_id, subnet_id):
        filter_dict = {'subnet_id': [subnet_id], 'tenant_id': [tenant_id]}
        return self.plugin.get_pools(context, filters=filter_dict)

    def _get_snatport_for_subnet(self, context, tenant_id, subnet_id):
        device_id = '_lb-snatport-' + subnet_id
        subnet = self.plugin._core_plugin.get_subnet(context, subnet_id)
        network_id = subnet['network_id']
        msg = (_("Filtering ports based on network_id=%(network_id)s, "
                 "tenant_id=%(tenant_id)s, device_id=%(device_id)s") %
               {'network_id': network_id,
                'tenant_id': tenant_id,
                'device_id': device_id})
        LOG.debug(msg)
        filter_dict = {
            'network_id': [network_id],
            'tenant_id': [tenant_id],
            'device_id': [device_id],
            'device-owner': [DRIVER_NAME]
        }
        ports = self.plugin._core_plugin.get_ports(context,
                                                   filters=filter_dict)
        if ports:
            msg = _("Found an existing SNAT port for subnet %s") % subnet_id
            LOG.info(msg)
            return ports[0]
        msg = _("Found no SNAT ports for subnet %s") % subnet_id
        LOG.info(msg)

    def _create_snatport_for_subnet(self, context, tenant_id, subnet_id,
                                    ip_address):
        subnet = self.plugin._core_plugin.get_subnet(context, subnet_id)
        fixed_ip = {'subnet_id': subnet['id']}
        if ip_address and ip_address != attributes.ATTR_NOT_SPECIFIED:
            fixed_ip['ip_address'] = ip_address
        port_data = {
            'tenant_id': tenant_id,
            'name': '_lb-snatport-' + subnet_id,
            'network_id': subnet['network_id'],
            'mac_address': attributes.ATTR_NOT_SPECIFIED,
            'admin_state_up': False,
            'device_id': '_lb-snatport-' + subnet_id,
            'device_owner': DRIVER_NAME,
            'fixed_ips': [fixed_ip],
        }
        port = self.plugin._core_plugin.create_port(context,
                                                    {'port': port_data})
        msg = _("Created SNAT port: %s") % repr(port)
        LOG.info(msg)
        return port

    def _remove_snatport_for_subnet(self, context, tenant_id, subnet_id):
        port = self._get_snatport_for_subnet(context, tenant_id, subnet_id)
        if port:
            self.plugin._core_plugin.delete_port(context, port['id'])
            msg = _("Removed SNAT port: %s") % repr(port)
            LOG.info(msg)

    def _create_snatport_for_subnet_if_not_exists(self, context, tenant_id,
                                                  subnet_id, network_info):
        port = self._get_snatport_for_subnet(context, tenant_id, subnet_id)
        if not port:
            msg = _("No SNAT port found for subnet %s."
                    " Creating one...") % subnet_id
            LOG.info(msg)
            port = self._create_snatport_for_subnet(context, tenant_id,
                                                    subnet_id,
                                                    ip_address=None)
        network_info['port_id'] = port['id']
        network_info['snat_ip'] = port['fixed_ips'][0]['ip_address']
        msg = _("SNAT port: %s") % repr(port)
        LOG.info(msg)

    def _remove_snatport_for_subnet_if_not_used(self, context, tenant_id,
                                                subnet_id):
        pools = self._get_pools_on_subnet(context, tenant_id, subnet_id)
        if not pools:
            #No pools left on the old subnet.
            #We can remove the SNAT port/ipaddress
            self._remove_snatport_for_subnet(context, tenant_id, subnet_id)
            msg = _("Removing SNAT port for subnet %s "
                    "as this is the last pool using it...") % subnet_id
            LOG.info(msg)

