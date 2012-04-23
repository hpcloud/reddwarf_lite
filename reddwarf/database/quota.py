# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Hewlett-Packard Development Company, L.P.
# Copyright 2011 OpenStack LLC.
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
import logging

from reddwarf import db
from reddwarf.common import config
from reddwarf.database import models

CONFIG = config.Config
LOG = logging.getLogger(__name__)

def _get_default_quotas():
    defaults = {
        'instances': CONFIG.get('quota_instances', 0),
        'snapshots': CONFIG.get('snapshot_instances', 0)
    }
    # -1 in the quota flags means unlimited
    for key in defaults.keys():
        if defaults[key] == -1:
            defaults[key] = None
    return defaults

def get_tenant_quotas(context, tenant_id):
    defaults = _get_default_quotas()
    quotas = models.Quota.find_all(tenant_id=tenant_id, deleted=False)
    
    if quotas is None:
        return defaults
    
    for key in defaults.keys():
        for quota in quotas:
            if key == quota['resource']:
                defaults[key] = quota['hard_limit']
                break
    return defaults

def allowed_instances(context, requested_instances):
    """Check quota and return min(requested_instances, allowed_instances)."""
    tenant_id = context.tenant
    
    usage = models.DBInstance.find_all(tenant_id=tenant_id, deleted=False).count()
    quota = get_tenant_quotas(context, tenant_id)
    LOG.debug('Quota for num of instances allowed to create %s, requested %s, used %s' % (quota, requested_instances, usage))

    allowed_instances = quota['instances'] - usage

    return min(requested_instances, allowed_instances)

def allowed_snapshots(context, requested_snapshots):
    """Check quota and return min(requested_snapshots, allowed_snapshots)."""
    tenant_id = context.tenant
    
    usage = models.Snapshot.find_all(tenant_id=tenant_id, deleted=False).count()
    quota = get_tenant_quotas(context, tenant_id)
    LOG.debug('Quota for num of instances allowed to create %s, requested %s, used %s' % (quota, requested_snapshots, usage))

    allowed_snapshots = quota['snapshots'] - usage

    return min(requested_snapshots, allowed_snapshots)