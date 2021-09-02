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

if __name__ == '__main__':
    unittest.main()
