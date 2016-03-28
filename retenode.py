#!/usr/bin/python

import numpy as np
import pandas as pd

node_types = ['root', 'alpha', 'beta', 'rule']

class ReteNode():
    def __init__(self, _name=None, _type=None, _prev=None, _next=None, _memory=pd.DataFrame(), _pattern=None):
        self.name = _name
        self.type = _type
        self.prev = _prev
        self.next = _next
        self.memory = _memory
        self.pattern = _pattern

    def print_node(self):
        print('name: '),
        print(self.name)
        print('type: '),
        print(self.type)
        print('prev: '),
        print(self.prev)
        print('next: '),
        print(self.next)
        print('memory:')
        print(self.memory)
        print('pattern: '),
        print(self.pattern)
