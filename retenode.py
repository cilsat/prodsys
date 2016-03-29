#!/usr/bin/python

import numpy as np
import pandas as pd

node_types = ['root', 'alpha', 'beta', 'rule']

class ReteNode():
    def __init__(self, _name=None, _type=None, _prev=None, _next=None, _memory=pd.DataFrame(), _pattern=None, _match=None):
        self.name = _name
        self.type = _type
        try:
            self.type in node_types
        except:
            print("invalid node type")
        self.prev = _prev
        self.next = _next
        self.memory = _memory
        self.pattern = _pattern
        self.match = _match

    def print_node(self):
        print('name:'),
        print(self.name),
        print(', type:'),
        print(self.type),

        if self.prev:
            print(', prev:'),
            print(self.prev),

        if self.next:
            print(', next:'),
            print(self.next)

        if self.type == 'alpha':
            print('pattern:')
            print(self.pattern.head())

        print('memory:')
        print(self.memory)
        print('')

    def root_match(self):
        pass

    def alpha_match(self):
        print('alpha match')

    def beta_match(self):
        pass
