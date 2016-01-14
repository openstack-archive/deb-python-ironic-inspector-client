# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest

import mock
from oslo_utils import netutils
from oslo_utils import uuidutils

import ironic_inspector_client
from ironic_inspector_client.common import http


FAKE_HEADERS = {
    http._MIN_VERSION_HEADER: '1.0',
    http._MAX_VERSION_HEADER: '1.9'
}


@mock.patch.object(http.requests, 'get',
                   return_value=mock.Mock(headers=FAKE_HEADERS,
                                          status_code=200))
class TestInit(unittest.TestCase):
    my_ip = 'http://' + netutils.get_my_ipv4() + ':5050'
    token = "token"

    def get_client(self, **kwargs):
        return ironic_inspector_client.ClientV1(auth_token=self.token,
                                                **kwargs)

    def test_ok(self, mock_get):
        self.get_client()
        mock_get.assert_called_once_with(self.my_ip)

    def test_explicit_version(self, mock_get):
        self.get_client(api_version=(1, 2))
        self.get_client(api_version=1)
        self.get_client(api_version='1.3')

    def test_unsupported_version(self, mock_get):
        self.assertRaises(ironic_inspector_client.VersionNotSupported,
                          self.get_client, api_version=(1, 99))
        self.assertRaises(ironic_inspector_client.VersionNotSupported,
                          self.get_client, api_version=2)
        self.assertRaises(ironic_inspector_client.VersionNotSupported,
                          self.get_client, api_version='1.42')

    def test_explicit_url(self, mock_get):
        self.get_client(inspector_url='http://host:port')
        mock_get.assert_called_once_with('http://host:port')


class BaseTest(unittest.TestCase):
    def setUp(self):
        super(BaseTest, self).setUp()
        self.uuid = uuidutils.generate_uuid()
        self.my_ip = 'http://' + netutils.get_my_ipv4() + ':5050'
        self.token = "token"

    @mock.patch.object(http.BaseClient, 'server_api_versions',
                       lambda self: ((1, 0), (1, 99)))
    def get_client(self, **kwargs):
        return ironic_inspector_client.ClientV1(auth_token=self.token,
                                                **kwargs)


@mock.patch.object(http.BaseClient, 'request')
class TestIntrospect(BaseTest):
    def test(self, mock_req):
        self.get_client().introspect(self.uuid)
        mock_req.assert_called_once_with(
            'post', '/introspection/%s' % self.uuid,
            params={'new_ipmi_username': None, 'new_ipmi_password': None})

    def test_invalid_input(self, mock_req):
        self.assertRaises(TypeError, self.get_client().introspect, 42)
        self.assertRaises(ValueError, self.get_client().introspect, 'uuid',
                          new_ipmi_username='user')

    def test_set_ipmi_credentials(self, mock_req):
        self.get_client().introspect(self.uuid,
                                     new_ipmi_password='p',
                                     new_ipmi_username='u')
        mock_req.assert_called_once_with(
            'post', '/introspection/%s' % self.uuid,
            params={'new_ipmi_username': 'u', 'new_ipmi_password': 'p'})


@mock.patch.object(http.BaseClient, 'request')
class TestGetStatus(BaseTest):
    def test(self, mock_req):
        mock_req.return_value.json.return_value = 'json'

        self.get_client().get_status(self.uuid)

        mock_req.assert_called_once_with(
            'get', '/introspection/%s' % self.uuid)

    def test_invalid_input(self, _):
        self.assertRaises(TypeError, self.get_client().get_status, 42)


@mock.patch.object(http.BaseClient, 'request')
class TestGetData(BaseTest):
    def test_json(self, mock_req):
        mock_req.return_value.json.return_value = 'json'

        self.assertEqual('json', self.get_client().get_data(self.uuid))

        mock_req.assert_called_once_with(
            'get', '/introspection/%s/data' % self.uuid)

    def test_raw(self, mock_req):
        mock_req.return_value.content = b'json'

        self.assertEqual(b'json', self.get_client().get_data(self.uuid,
                                                             raw=True))

        mock_req.assert_called_once_with(
            'get', '/introspection/%s/data' % self.uuid)

    def test_invalid_input(self, _):
        self.assertRaises(TypeError, self.get_client().get_data, 42)


@mock.patch.object(http.BaseClient, 'request')
class TestRules(BaseTest):
    def get_rules(self, **kwargs):
        return self.get_client(**kwargs).rules

    def test_create(self, mock_req):
        self.get_rules().create([{'cond': 'cond'}], [{'act': 'act'}])

        mock_req.assert_called_once_with(
            'post', '/rules', json={'conditions': [{'cond': 'cond'}],
                                    'actions': [{'act': 'act'}],
                                    'uuid': None,
                                    'description': None})

    def test_create_all_fields(self, mock_req):
        self.get_rules().create([{'cond': 'cond'}], [{'act': 'act'}],
                                uuid='u', description='d')

        mock_req.assert_called_once_with(
            'post', '/rules', json={'conditions': [{'cond': 'cond'}],
                                    'actions': [{'act': 'act'}],
                                    'uuid': 'u',
                                    'description': 'd'})

    def test_create_invalid_input(self, mock_req):
        self.assertRaises(TypeError, self.get_rules().create,
                          {}, [{'act': 'act'}])
        self.assertRaises(TypeError, self.get_rules().create,
                          [{'cond': 'cond'}], {})
        self.assertRaises(TypeError, self.get_rules().create,
                          [{'cond': 'cond'}], [{'act': 'act'}],
                          uuid=42)
        self.assertFalse(mock_req.called)

    def test_from_json(self, mock_req):
        self.get_rules().from_json({'foo': 'bar'})

        mock_req.assert_called_once_with(
            'post', '/rules', json={'foo': 'bar'})

    def test_get_all(self, mock_req):
        mock_req.return_value.json.return_value = {'rules': ['rules']}

        res = self.get_rules().get_all()
        self.assertEqual(['rules'], res)

        mock_req.assert_called_once_with('get', '/rules')

    def test_get(self, mock_req):
        mock_req.return_value.json.return_value = {'answer': 42}

        res = self.get_rules().get('uuid1')
        self.assertEqual({'answer': 42}, res)

        mock_req.assert_called_once_with('get', '/rules/uuid1')

    def test_get_invalid_input(self, mock_req):
        self.assertRaises(TypeError, self.get_rules().get, 42)
        self.assertFalse(mock_req.called)

    def test_delete(self, mock_req):
        self.get_rules().delete('uuid1')

        mock_req.assert_called_once_with('delete', '/rules/uuid1')

    def test_delete_invalid_input(self, mock_req):
        self.assertRaises(TypeError, self.get_rules().delete, 42)
        self.assertFalse(mock_req.called)

    def test_delete_all(self, mock_req):
        self.get_rules().delete_all()

        mock_req.assert_called_once_with('delete', '/rules')
