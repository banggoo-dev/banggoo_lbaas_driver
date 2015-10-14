# Banggoo LBaaS Driver for ADC.

Banggoo github repos:

- [banggoo-openstack-lbaas](https://github.com/banggoo-dev/banggoo_lbaas_driver) - OpenStack LBaaS driver. 

## Introduction:

This guide is for the Banggoo LBaaS Driver, which is specifically designed to manage Banggoo-dev Application Delivery Controller (ADC) appliances. 

In this installation guide, we will introduce installation caveat and configuration method. In the end, method about how to check the installation is correct will be listed. Expectedly, an updated community-supported driver will be in the Juno release of OpenStack. We will promptly update our drivers.

  > The latest version of this document can be found at https://github.com/banggoo-dev/banggoo_lbaas_driver


## Installation steps:

### Step 1:

Make sure you have the neutron-lbaas-agent installed.

### Step 2: 

Download the driver from: <https://github.com/banggoo-dev/banggoo_lbaas_driver>

![image1](https://cloud.githubusercontent.com/assets/15115131/10474255/34c52f2a-7267-11e5-9c11-40f5b3aed0fe.png)

### Step 3:

Move the directories and files to the appropriate locations.

`neutron/services/loadbalancer/drivers/banggoo -> your neutron directory`

The relative path is neutron/services/loadbalancer/drivers/.

![image2](https://cloud.githubusercontent.com/assets/15115131/10474138/9c60d92e-7265-11e5-84b4-c3f595c881ff.png)

If the operating system is Centos7, absolute path is typically /usr/lib/python2.7/site-packages/neutron/services/loadbalancer/drivers/.

If the operating system is Centos6, absolute path is typically /usr/lib/python2.6/site-packages/neutron/services/loadbalancer/drivers/.

#### Installation script:

```
NEUTRON_IMPORT=` printf "import neutron\nprint neutron.__file__\n" | python`
NEUTRON_DIR=`dirname $NEUTRON_IMPORT`
if [ -z “$NEUTRON_DIR” ]; then
  echo “ERROR: neutron is not installed”
else
  git clone https://github.com/banggoo-dev/banggoo_lbaas_driver
  cd banggoo_lbaas_driver/neutron/services/loadbalancer/drivers 
  sudo cp -r banggoo/ $neutron_dir/services/loadbalancer/drivers/ 
  cd - >/dev/null
fi

```


### Step 4:

Modify `/etc/openstack-dashboard/local_settings`

```
OPENSTACK_NEUTRON_NETWORK = { 
        …
        'enable_lb': True,
    }
```


### Step 5:

Modify `/etc/neutron/neutron.conf`

```
[DEFAULT]
…
service_plugins = router, lbaas

[service_providers]
# Specify service providers (drivers) for advanced services like loadbalancer, VPN, Firewall.
# Must be in form:
# service_provider=<service_type>:<name>:<driver>[:default]
# List of allowed service types includes LOADBALANCER, FIREWALL, VPN
# Combination of <service type> and <name> must be unique; <driver> must also be unique
# This is multiline option, example for default provider:
# service_provider=LOADBALANCER:name:lbaas_plugin_driver_path:default
# example of non-default provider:
# service_provider=FIREWALL:name2:firewall_driver_path
# --- Reference implementations ---
…
service_provider=LOADBALANCER:Haproxy:neutron.services.loadbalancer.drivers.haproxy.plugin_driver.HaproxyOnHostPluginDriver
service_provider=VPN:openswan:neutron.services.vpn.service_drivers.ipsec.IPsecVPNDriver:default
service_provider=LOADBALANCER:Banggoo:neutron.services.loadbalancer.drivers.banggoo.driver.BanggooLoadBalancerDriver:default

```

### Step 6:

Modify `/etc/neutron/lbaas_agent.ini`

```
[DEFAULT] 
 …
interface_driver = neutron.agent.linux.interface.OVSInterfaceDriver
```

### Step 7:

Create and configure the banggoo section of the bangooo/banggoo_config.ini file. The file is located in:

`/etc/neutron/services/loadbalancer/banggoo/banggoo_config.ini`


```
adc_address=https://vDirectServerIP:vDirectServerPort/
adc_user=vDirectUserName
adc_password=vDirectUserPassword

Example:
adc_address=https://192.168.4.200:4488/
adc_user=admin
adc_password=admin
```

### Step 8:

Restart Neutron to verify successful completion of driver installation.

#### Example:

```
service neutron-lbaas-agent restart
service neutron-server restart
service httpd restart
```


## Validation:

Validate the configurations are correct and customize further settings if necessary.

### Step 1:

Login to the OpenStack dashboard.

![image3](https://cloud.githubusercontent.com/assets/15115131/10474148/ad8b2b6e-7265-11e5-8adc-786383c3bbb3.png)

### Step 2:

Under the “Network” menu, go to the “Load Balancers” tab and select “Add Pool”:

![image4](https://cloud.githubusercontent.com/assets/15115131/10474168/f55d3126-7265-11e5-9ddd-002f757219fa.png)

Once you have added a pool, a success message should appear. 

### Step 3:

Under the “Network” menu, go to the “Load Balancers” tab and select “Add Member”:

![image5](https://cloud.githubusercontent.com/assets/15115131/10474160/e6cc1866-7265-11e5-8cc7-b0b354bf7106.png)

### Step 4:

Under the “Network” menu, go to the “Load Balancers” tab and select “Edit Vip”:

![image6](https://cloud.githubusercontent.com/assets/15115131/10474177/03c04dfc-7266-11e5-9cf3-c93cada43968.png)

### Step 5:

Login to the GUI on your ADC device, and validate which configuration was applied if the VS are set. The VS name is the tenant ID. 

![image7](https://cloud.githubusercontent.com/assets/15115131/10474184/166d0c42-7266-11e5-89ac-8059f2c9e164.png)
