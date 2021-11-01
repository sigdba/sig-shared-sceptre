#!/usr/bin/env python3

import unittest
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import MultiHostElb as mut

class TestRuleModel(unittest.TestCase):
    def test_no_path_or_host(self):
        with self.assertRaises(ValueError):
            mut.RuleModel.parse_obj({})

    def test_path_singular_str(self):
        m = mut.RuleModel.parse_obj({'path': 'thepath'})
        self.assertEqual(m.paths, ['thepath'])

    def test_path_singular_list(self):
        m = mut.RuleModel.parse_obj({'path': ['a', 'b']})
        self.assertEqual(m.paths, ['a', 'b'])

    def test_host_singular_str(self):
        m = mut.RuleModel.parse_obj({'host': 'thehost'})
        self.assertEqual(m.hosts, ['thehost'])

    def test_host_singular_list(self):
        m = mut.RuleModel.parse_obj({'host': ['a', 'b']})
        self.assertEqual(m.hosts, ['a', 'b'])

    def test_host_both(self):
        with self.assertRaises(ValueError):
            mut.RuleModel.parse_obj({'host': 'ahost', 'hosts': ['a', 'b']})

    def test_path_both(self):
        with self.assertRaises(ValueError):
            mut.RuleModel.parse_obj({'path': 'apath', 'paths': ['a', 'b']})


class TestRedirectModel(unittest.TestCase):
    def test_protocol(self):
        mut.RedirectModel.parse_obj({'protocol': '#{protocol}'})
        with self.assertRaises(ValueError):
            mut.RedirectModel.parse_obj({'protocol': 'something'})


class TestActionModel(unittest.TestCase):
    def test_target_group_attribute_defaults(self):
        m = mut.ActionModel()
        self.assertEqual(m.target_group_attributes['stickiness.enabled'], 'true')
        self.assertEqual(m.target_group_attributes['stickiness.type'], 'lb_cookie')

    def test_target_group_attribute_extended_defaults(self):
        m = mut.ActionModel(target_group_attributes={'stickiness.enabled': 'false'})
        self.assertEqual(m.target_group_attributes['stickiness.enabled'], 'false')
        self.assertEqual(m.target_group_attributes['stickiness.type'], 'lb_cookie')

    def test_targets(self):
        m = mut.ActionModel(targets=['inst1', mut.TargetModel(id='inst2'), 'inst3'])
        self.assertEqual([mut.TargetModel(id='inst1'), mut.TargetModel(id='inst2'), mut.TargetModel(id='inst3')], m.targets)


class TestListenerModel(unittest.TestCase):
    def test_hostnames_required_for_https(self):
        m = mut.ListenerModel(port=80)
        with self.assertRaises(ValueError):
            m = mut.ListenerModel(port=443)

    def test_protocol(self):
        m = mut.ListenerModel(port=80)
        self.assertEqual(m.protocol, 'HTTP')
        m = mut.ListenerModel(port=443, hostnames=['ahost'])
        self.assertEqual(m.protocol, 'HTTPS')
        m = mut.ListenerModel(port=443, protocol='HTTP')
        self.assertEqual(m.protocol, 'HTTP')


class TestUserDataModel(unittest.TestCase):
    def test_listeners(self):
        with self.assertRaises(ValueError) as cm:
            mut.UserDataModel(listeners=[], subnet_ids=['id1', 'id2'], internet_facing=False)
        j = cm.exception.json()
        self.assertTrue('one listener' in j, msg='Wrong message: {}'.format(j))

    def test_subnets(self):
        with self.assertRaises(ValueError) as cm:
            mut.UserDataModel(listeners=[mut.ListenerModel(port=80)], subnet_ids=['id1'], internet_facing=False)
        j = cm.exception.json()
        self.assertTrue('two subnet_ids' in j, msg='Wrong message: {}'.format(j))

    def test_attributes_defaults(self):
        m = mut.UserDataModel(listeners=[mut.ListenerModel(port=80)], subnet_ids=['id1', 'id2'], internet_facing=False)
        self.assertEqual(m.attributes['access_logs.s3.enabled'], 'true')
        self.assertEqual(m.attributes['access_logs.s3.prefix'], '${AWS::StackName}-access.')

    def test_attributes_defaults(self):
        m = mut.UserDataModel(listeners=[mut.ListenerModel(port=80)], subnet_ids=['id1', 'id2'], internet_facing=False,
                              attributes={'access_logs.s3.enabled': 'false'})
        self.assertEqual(m.attributes['access_logs.s3.enabled'], 'false')
        self.assertEqual(m.attributes['access_logs.s3.prefix'], '${AWS::StackName}-access.')


if __name__ == '__main__':
    unittest.main()
