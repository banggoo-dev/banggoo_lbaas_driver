import os
import re

BG_CONF = "/etc/neutron/services/loadbalancer/banggoo/banggoo_config.ini"

def cfgparse():
    patten = "\s*(\w+)\s*=\s*(.*)"

    if not os.path.exists(BG_CONF):
        return {}

    conf = {}

    lines = file(BG_CONF).readlines()
    for line in lines:
        match_res = re.match(patten, line)

        if match_res:
            conf[match_res.group(1)] = match_res.group(2)
 
    return conf
