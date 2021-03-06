# Copyright 2014 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.
import time
import random
import logging
import datetime
from tests import unittest

import botocore.session
from botocore.client import ClientError
from botocore.compat import six
from six import StringIO


class TestBucketWithVersions(unittest.TestCase):
    def setUp(self):
        self.session = botocore.session.get_session()
        self.client = self.session.create_client('s3', region_name='us-west-2')
        self.bucket_name = 'botocoretest%s-%s' % (
            int(time.time()), random.randint(1, 1000000))

    def extract_version_ids(self, versions):
        version_ids = []
        for marker in versions['DeleteMarkers']:
            version_ids.append(marker['VersionId'])
        for version in versions['Versions']:
            version_ids.append(version['VersionId'])
        return version_ids

    def test_create_versioned_bucket(self):
        # Verifies we can:
        # 1. Create a bucket
        # 2. Enable versioning
        # 3. Put an Object
        self.client.create_bucket(Bucket=self.bucket_name)
        self.addCleanup(self.client.delete_bucket, Bucket=self.bucket_name)

        self.client.put_bucket_versioning(
            Bucket=self.bucket_name,
            VersioningConfiguration={"Status": "Enabled"})
        response = self.client.put_object(
            Bucket=self.bucket_name, Key='testkey', Body='bytes body')
        self.addCleanup(self.client.delete_object,
                        Bucket=self.bucket_name,
                        Key='testkey',
                        VersionId=response['VersionId'])

        response = self.client.get_object(
            Bucket=self.bucket_name, Key='testkey')
        self.assertEqual(response['Body'].read(), b'bytes body')

        response = self.client.delete_object(Bucket=self.bucket_name,
                                             Key='testkey')
        # This cleanup step removes the DeleteMarker that's created
        # from the delete_object call above.
        self.addCleanup(self.client.delete_object,
                        Bucket=self.bucket_name,
                        Key='testkey',
                        VersionId=response['VersionId'])
        # Object does not exist anymore.
        with self.assertRaises(ClientError):
            self.client.get_object(Bucket=self.bucket_name, Key='testkey')
        versions = self.client.list_object_versions(Bucket=self.bucket_name)
        version_ids = self.extract_version_ids(versions)
        self.assertEqual(len(version_ids), 2)


# This is really a combination of testing the debug logging mechanism
# as well as the response wire log, which theoretically could be
# implemented in any number of modules, which makes it hard to pick
# which integration test module this code should live in, so I picked
# the client module.
class TestResponseLog(unittest.TestCase):

    def test_debug_log_contains_headers_and_body(self):
        # This test just verifies that the response headers/body
        # are in the debug log.  It's an integration test so that
        # we can refactor the code however we want, as long as we don't
        # lose this feature.
        session = botocore.session.get_session()
        client = session.create_client('s3', region_name='us-west-2')
        debug_log = StringIO()
        session.set_stream_logger('', logging.DEBUG, debug_log)
        client.list_buckets()
        debug_log_contents = debug_log.getvalue()
        self.assertIn('Response headers', debug_log_contents)
        self.assertIn('Response body', debug_log_contents)


class TestAcceptedDateTimeFormats(unittest.TestCase):
    def setUp(self):
        self.session = botocore.session.get_session()
        self.client = self.session.create_client('emr', 'us-west-2')

    def test_accepts_datetime_object(self):
        response = self.client.list_clusters(
            CreatedAfter=datetime.datetime.now())
        self.assertIn('Clusters', response)

    def test_accepts_epoch_format(self):
        response = self.client.list_clusters(CreatedAfter=0)
        self.assertIn('Clusters', response)

    def test_accepts_iso_8601_unaware(self):
        response = self.client.list_clusters(
            CreatedAfter='2014-01-01T00:00:00')
        self.assertIn('Clusters', response)

    def test_accepts_iso_8601_utc(self):
        response = self.client.list_clusters(
            CreatedAfter='2014-01-01T00:00:00Z')
        self.assertIn('Clusters', response)

    def test_accepts_iso_8701_local(self):
        response = self.client.list_clusters(
            CreatedAfter='2014-01-01T00:00:00-08:00')
        self.assertIn('Clusters', response)
