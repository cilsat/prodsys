#!/usr/bin/python

import numpy as np
import pandas as pd

node_types = ['root', 'alpha', 'beta', 'rule']

class ReteNode():
    def __init__(self, _name=None, _type=None, _prev=None, _next=None, _memory=pd.DataFrame(), _match=None):
        self.name = _name
        self.type = _type
        try:
            self.type in node_types
        except:
            print("invalid node type")
        self.prev = _prev
        self.next = _next
        self.memory = _memory
        self.match = _match

    def print_node(self):
        print('name:'),
        print(self.name),
        print(', type:'),
        print(self.type),
        print(', prev:'),
        print(self.prev),
        print(', next:'),
        print(self.next),
        print(', memory:')
        print(self.memory)
        print('')

    def alpha_match(self):
        pass

    def beta_match(self):
        pass
