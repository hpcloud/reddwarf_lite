# vim: tabstop=4 shiftwidth=4 softtabstop=4
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
import unittest

from sqlalchemy.orm import query

from reddwarf.database import quota
from reddwarf.database import models
from reddwarf.common import context as rd_context
from reddwarf import tests

LOG = logging.getLogger(__name__)

class QuotaTest(tests.BaseTest):
    
    DUMMY_INSTANCE = {"id": "uuid0-uuid1-uuid2",
                      "name": "DUMMY_NAME" }
    
    DUMMY_CONTEXT =  rd_context.ReddwarfContext(
                          auth_tok='Auth_ABCDEFG',
                          tenant='12345')
    
    def test_get_default_quotas(self):
        """Tests the default quota for instances and snapshots is 0,
        unless there exist database values that override them"""
        
        self.mock.StubOutWithMock(models.Quota, 'find_all')
        models.Quota.find_all(tenant_id='tenant_id', deleted=False).AndReturn(None)
        
        self.mock.ReplayAll()

        quotas = quota.get_tenant_quotas(self.DUMMY_CONTEXT, 'tenant_id')
        self.assertTrue(quotas['instances'] == 0, 'Expected 0 as default quota limit for instances, instead got %s' % quotas['instances'])
        self.assertTrue(quotas['snapshots'] == 0, 'Expected 0 as default quota limit for snapshots, instead got %s' % quotas['snapshots'])
        
    def test_get_default_quotas_with_db_overrides(self):
        """Tests that the database quota values for a given tenant
        do override the default 0's"""
        
        default_quotas = [{ "tenant_id": "12345", "hard_limit": 3, "resource":"instances"},
                          { "tenant_id": "12345", "hard_limit": 10, "resource":"snapshots"}]
        
        self.mock.StubOutWithMock(models.Quota, 'find_all')
        models.Quota.find_all(tenant_id='tenant_id', deleted=False).AndReturn(default_quotas)
        
        self.mock.ReplayAll()

        quotas = quota.get_tenant_quotas(self.DUMMY_CONTEXT, 'tenant_id')
        self.assertTrue(quotas['instances'] == 3, 'Expected 3 as quota for instances, instead got %s' % quotas['instances'])
        self.assertTrue(quotas['snapshots'] == 10, 'Expected 10 as quota for snapshots, instead got %s' % quotas['snapshots'])
        
        
        
    def test_allowed_instances(self):
        """Tests that given a quota on instances, the number of 
        intances allowed to be created is calculated appropriately"""

        # Pretend that 1 instance exists for this tenant
        self.mock.StubOutWithMock(query.Query, 'count')
        query.Query.count().AndReturn(1)

        # Allow up to 3 instances to be created
        default_quotas = [{ "tenant_id": "12345", "hard_limit": 3, "resource":"instances"}]        
        self.mock.StubOutWithMock(models.Quota, 'find_all')
        models.Quota.find_all(tenant_id='12345', deleted=False).AndReturn(default_quotas)
        
        self.mock.ReplayAll()
        
        # Check if we are allowed to create 1 instance
        allowed = quota.allowed_instances(self.DUMMY_CONTEXT, 1)
        self.assertTrue(allowed == 1, 'Expected 1 allowed instance, instead got %s' % allowed)

    def test_allowed_instances_more_than_1(self):
        # Pretend that 1 instance exists for this tenant
        self.mock.StubOutWithMock(query.Query, 'count')
        query.Query.count().AndReturn(1)

        # Allow up to 3 instances to be created
        default_quotas = [{ "tenant_id": "12345", "hard_limit": 3, "resource":"instances"}]        
        self.mock.StubOutWithMock(models.Quota, 'find_all')
        models.Quota.find_all(tenant_id='12345', deleted=False).AndReturn(default_quotas)
        
        self.mock.ReplayAll()

        # Check if we are allowed to create 2 instances
        allowed = quota.allowed_instances(self.DUMMY_CONTEXT, 2)
        self.assertTrue(allowed == 2, 'Expected 2 allowed instance, instead got %s' % allowed)
        
    def test_allowed_instances_truncated(self):
        """ Ensure that the request for an instance count that exceeds quota
        gets truncated to the maximum allowed """
        # Pretend that 1 instance exists for this tenant
        self.mock.StubOutWithMock(query.Query, 'count')
        query.Query.count().AndReturn(1)

        # Allow up to 3 instances to be created
        default_quotas = [{ "tenant_id": "12345", "hard_limit": 3, "resource":"instances"}]        
        self.mock.StubOutWithMock(models.Quota, 'find_all')
        models.Quota.find_all(tenant_id='12345', deleted=False).AndReturn(default_quotas)
        
        self.mock.ReplayAll()

        # Check if we are allowed to create 3 instances
        allowed = quota.allowed_instances(self.DUMMY_CONTEXT, 3)
        self.assertTrue(allowed == 2, 'Expected 2 allowed instance, instead got %s' % allowed)

    def test_allowed_instances_exceeds_quota(self):
        """ Ensure that a 0 is returned when instance count == quota limit """
        # Pretend that 1 instance exists for this tenant
        self.mock.StubOutWithMock(query.Query, 'count')
        query.Query.count().AndReturn(3)

        # Allow up to 3 instances to be created
        default_quotas = [{ "tenant_id": "12345", "hard_limit": 3, "resource":"instances"}]        
        self.mock.StubOutWithMock(models.Quota, 'find_all')
        models.Quota.find_all(tenant_id='12345', deleted=False).AndReturn(default_quotas)
        
        self.mock.ReplayAll()

        # Check if we are allowed to create 1 instance
        allowed = quota.allowed_instances(self.DUMMY_CONTEXT, 1)
        self.assertTrue(allowed == 0, 'Expected 0 allowed instance, instead got %s' % allowed)
        
        

    def test_allowed_snapshotss(self):
        """Tests that given a quota on snapshots, the number of 
        snapshots allowed to be created is calculated appropriately"""

        # Pretend that 1 snapshot exists for this tenant
        self.mock.StubOutWithMock(query.Query, 'count')
        query.Query.count().AndReturn(1)

        # Allow up to 5 snapshots to be created
        default_quotas = [{ "tenant_id": "12345", "hard_limit": 5, "resource":"snapshots"}]        
        self.mock.StubOutWithMock(models.Quota, 'find_all')
        models.Quota.find_all(tenant_id='12345', deleted=False).AndReturn(default_quotas)
        
        self.mock.ReplayAll()
        
        # Check if we are allowed to create 1 snapshot
        allowed = quota.allowed_snapshots(self.DUMMY_CONTEXT, 1)
        self.assertTrue(allowed == 1, 'Expected 1 allowed snapshot, instead got %s' % allowed)

    def test_allowed_snapshots_more_than_1(self):
        # Pretend that 1 snapshot exists for this tenant
        self.mock.StubOutWithMock(query.Query, 'count')
        query.Query.count().AndReturn(1)

        # Allow up to 5 snapshots to be created
        default_quotas = [{ "tenant_id": "12345", "hard_limit": 5, "resource":"snapshots"}]        
        self.mock.StubOutWithMock(models.Quota, 'find_all')
        models.Quota.find_all(tenant_id='12345', deleted=False).AndReturn(default_quotas)
        
        self.mock.ReplayAll()
        
        # Check if we are allowed to create 1 snapshot
        allowed = quota.allowed_snapshots(self.DUMMY_CONTEXT, 3)
        self.assertTrue(allowed == 3, 'Expected 3 allowed snapshot, instead got %s' % allowed)
        
    def test_allowed_snapshots_truncated(self):
        """ Ensure that the request for an snapshot count that exceeds quota
        gets truncated to the maximum allowed """
        # Pretend that 1 snapshot exists for this tenant
        self.mock.StubOutWithMock(query.Query, 'count')
        query.Query.count().AndReturn(1)

        # Allow up to 5 snapshots to be created
        default_quotas = [{ "tenant_id": "12345", "hard_limit": 5, "resource":"snapshots"}]        
        self.mock.StubOutWithMock(models.Quota, 'find_all')
        models.Quota.find_all(tenant_id='12345', deleted=False).AndReturn(default_quotas)
        
        self.mock.ReplayAll()
        
        # Check if we are allowed to create 1 snapshot
        allowed = quota.allowed_snapshots(self.DUMMY_CONTEXT, 5)
        self.assertTrue(allowed == 4, 'Expected 4 allowed snapshots, instead got %s' % allowed)

    def test_allowed_snapshots_exceeds_quota(self):
        """ Ensure that a 0 is returned when snapshot count == quota limit """
        # Pretend that 1 snapshot exists for this tenant
        self.mock.StubOutWithMock(query.Query, 'count')
        query.Query.count().AndReturn(5)

        # Allow up to 5 snapshots to be created
        default_quotas = [{ "tenant_id": "12345", "hard_limit": 5, "resource":"snapshots"}]        
        self.mock.StubOutWithMock(models.Quota, 'find_all')
        models.Quota.find_all(tenant_id='12345', deleted=False).AndReturn(default_quotas)
        
        self.mock.ReplayAll()
        
        # Check if we are allowed to create 1 snapshot
        allowed = quota.allowed_snapshots(self.DUMMY_CONTEXT, 1)
        self.assertTrue(allowed == 0, 'Expected 0 allowed snapshot, instead got %s' % allowed)
