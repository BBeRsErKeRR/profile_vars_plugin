#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import configparser
import json
import yaml
import logging
import random
from os import environ, path
from faker import Faker
from faker.providers.python import Provider

import sys

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ch = logging.StreamHandler(sys.stderr)
ch.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

"""
data = {
        '_meta': {
          'hostvars': hostvars
        },
        'all': {
            'children': [
                'ungrouped'
            ]
        },
        'ungrouped': {
            'hosts': ungrouped
        }
    }
"""


def read_yml(fullpath):
    with open(fullpath) as yamlfile:
        yaml_content = yaml.load(yamlfile, Loader=yaml.SafeLoader)
    return yaml_content


class PythonProvider(Provider):
    default_value_types = (
        "str",
        "str",
        "str",
        "str",
        "float",
        "int",
        "int",
        "uri",
        "email",
    )


fake = Faker('en_US')
fake.add_provider(PythonProvider)


class Host(object):

    def __init__(self, name, parent=None, vars=None):
        self.name = name
        self.vars = vars
        self.parent = parent

    def __repr__(self) -> str:
        return 'Host<{}>({},{})'.format(self.name, self.parent, self.vars)


class Group(object):

    def __init__(self, name, parent=None, vars=None):
        self.name = name
        self.parent = parent
        self.vars = vars

    def __repr__(self) -> str:
        return 'Group<{}>({},{})'.format(self.name, self.parent, self.vars)


def get_deep_key_of_var(obj_var, max_deep=1):
    res = {"path": "", "type": None}
    size = len(obj_var)
    curr_index = fake.pyint(0, size-1, 1)
    curr_iem_index = curr_index if isinstance(
        obj_var, list) else list(obj_var.keys())[curr_index]
    res["path"] = '[{}]'.format(curr_index if isinstance(
        obj_var, list) else '"%s"' % list(obj_var.keys())[curr_index])
    next_val = obj_var[curr_iem_index]
    res["type"] = type(next_val)
    if max_deep > 0 and isinstance(next_val, (list, dict,)):
        children = get_deep_key_of_var(next_val, max_deep-1)
        res["path"] += children["path"]
        res["type"] = children["type"]
    return res


class DynamicInventory(object):

    def __init__(self, config):
        self._config = config
        self._groups = list()
        self._hosts = list()

        # Internal
        main_section = 'inventory'
        self.__groups_count = self._config.getint(main_section, 'groups')
        self.__nested_count = self._config.getint(main_section, 'nested')
        self.__hosts_count = self._config.getint(main_section, 'hosts')
        host_vars_section = 'hostvars'
        self.__host_vars = dict(
            min_elements=self._config.getint(
                host_vars_section, 'min_elements'),
            max_elements=self._config.getint(
                host_vars_section, 'max_elements'),
            max_deep=self._config.getint(host_vars_section, 'max_deep'),
            global_names=[i.strip() for i in self._config.get(
                host_vars_section, 'global_names').split(',')],
        )

        group_vars_section = 'groupvars'
        self.__group_vars = dict(
            min_elements=self._config.getint(
                group_vars_section, 'min_elements'),
            max_elements=self._config.getint(
                group_vars_section, 'max_elements'),
            max_deep=self._config.getint(group_vars_section, 'max_deep'),
            global_names=[i.strip() for i in self._config.get(
                group_vars_section, 'global_names').split(',')],
        )
        external_includes = self._config.get(
            group_vars_section, 'external_includes')
        if external_includes:
            self.__group_vars["external_includes"] = [i.strip()
                                                      for i in external_includes.split(',')]
            self.__group_vars["external_includes_max_count"] = self._config.getint(
                group_vars_section, 'external_includes_max_count')

    def __generate_template_vars(self, hostvars, max_deep=0):
        res = hostvars.copy()
        deep_elements = dict()
        for k, v in hostvars.items():
            if isinstance(v, (list, dict,)) and fake.pybool():
                deep_elements[k] = v
                continue
            if fake.pybool() and len(deep_elements) > 0 and isinstance(v, dict):
                el_idx = fake.pyint(0, len(deep_elements)-1, 1)
                cp_key = list(deep_elements.keys())[el_idx]
                cp_el = deep_elements[cp_key]
                next_key = get_deep_key_of_var(
                    cp_el, max_deep)
                new_name = fake.name().replace(" ", "_")
                # logger.info((cp_key, new_name, next_key))
                res[k][new_name] = '{{{{ {0}{1} }}}}'.format(
                    cp_key, next_key["path"])
        return res

    def __add_external_templates(self, hostvars, templates, max_items):
        res = hostvars.copy()
        is_added = False

        for k, v in hostvars.items():
            if fake.pybool() and isinstance(v, dict) and max_items > 2:
                res[k], is_added = self.__add_external_templates(
                    v, templates, fake.pyint(0, max_items-1, 1))
            elif not is_added and fake.pybool():
                el_idx = fake.pyint(0, len(templates)-1, 1)
                # logger.info(templates)
                res[k] = '{{'+templates[el_idx]+'}}'
                is_added = True
        return res, is_added

    def _generate_hostvars(self):
        return {h.name: self.__generate_template_vars(h.vars, self.__host_vars["max_deep"]) for h in self._hosts if h.vars}

    def __generate_deep_vars(self, elements=0, max_deep=0):
        res = fake.pydict(
            nb_elements=elements,
            variable_nb_elements=False,
            value_types=[str, int, bool, list, dict],
        )
        if max_deep > 0:
            for k in list(res.keys()):
                if isinstance(res[k], dict):
                    depth = fake.pyint(0, max_deep-1, 1)
                    items = random.randint(
                        1, elements - 1) if elements > 2 else elements
                    res[k] = self.__generate_deep_vars(items, depth)
        return res

    def _generate_vars(self, config):
        items = random.randint(
            config["min_elements"], config["max_elements"] - 1)
        res = self.__generate_deep_vars(items, config["max_deep"])
        for key in config["global_names"]:
            # changed_key = list(res.keys())[fake.pyint(0, len(res)-1, 1)]
            # new_key = self.__dicts_vars["global_names"][fake.pyint(
            #     0, len(self.__dicts_vars["global_names"])-1, 1)]
            # res[new_key] = res.pop(changed_key)
            items = random.randint(1, 20)
            res[key] = self.__generate_deep_vars(
                items, config["max_deep"])

        return res

    def _create_hosts(self):

        def is_group_of_groups(g_id):
            for g in self._groups:
                if g_id == g.parent:
                    return True
            return False

        def get_rand():
            while True:
                result = random.randint(0, len(self._groups) - 1)
                if all(g.parent for g in self._groups) or not is_group_of_groups(result):
                    return result

        for i in range(0, self.__hosts_count):
            h = Host('test_host_{}'.format(i),
                     parent=get_rand(), vars=self._generate_vars(self.__host_vars))
            self._hosts.append(h)
        logger.debug(str(self._hosts))

    def _create_groups(self):
        def get_rand(current, items):
            while True:
                result = random.randint(0, self.__groups_count - 1)
                if result != current and (len(items) < result or items[result].parent != current):
                    return result

        for i in range(0, self.__groups_count):
            g_vars = self.__generate_template_vars(
                self._generate_vars(self.__group_vars), self.__group_vars["max_deep"])
            g_vars, _ = self.__add_external_templates(
                g_vars, self.__group_vars["external_includes"], self.__group_vars["external_includes_max_count"])
            g = Group('test_{}'.format(i), vars=g_vars)
            if self.__nested_count > 0 and (random.randint(5, 19) % 2 == 1 or self.__groups_count - self.__nested_count < i):
                g.name = 'test_children_{}'.format(i)
                g.parent = get_rand(i, self._groups)
                self.__nested_count = self.__nested_count - 1
            self._groups.append(g)

        logger.debug(str(self._groups))

    def generate_inventory(self):

        self._create_groups()
        self._create_hosts()

        inventory = {
            'all': {'children': [g.name for g in self._groups if not g.parent]},
            '_meta': {
                'hostvars': self._generate_hostvars()
            }
        }

        def get_children(parent, items):
            return [i.name for i in items if parent == i.parent]

        for idx, g in enumerate(self._groups):
            data = dict()
            groups = get_children(idx, self._groups)
            hosts = get_children(idx, self._hosts)

            if groups:
                data = {'children': groups}
            if hosts:
                data = {'hosts': hosts}
            if g.vars and data:
                data["vars"] = g.vars
            if data:
                inventory[g.name] = data

        return inventory


if __name__ == "__main__":
    config = configparser.ConfigParser()
    cfg_dir = path.dirname(path.abspath(__file__))
    default_cfg = path.join(cfg_dir, '.config.ini')
    config.read(environ.get('INVENTORY_CONFIG', default_cfg))
    use_cache = config.getboolean("inventory", 'use_cache')
    inventory__file = path.join(cfg_dir, '.inventory.yaml')
    if use_cache and path.isfile(inventory__file):
        res = read_yml(inventory__file)
    else:
        res = DynamicInventory(config)
        res = res.generate_inventory()
        with open(inventory__file, 'w') as writefile:
            writefile.write(yaml.safe_dump(
                res, indent=2, default_flow_style=False))
    print(json.dumps(res))
