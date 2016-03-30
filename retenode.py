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


    def apply_token(self, _wme, _action):

        # check if memory exists yet, and initialize if not
        if self.memory.empty:
            self.memory = pd.DataFrame(columns=_wme.keys())

        if _wme.name not in self.memory.index and _action == 'add':
            print('match test:'),
            print(self.match(self, 3))
            if self.match(self, _wme):
                self.memory.loc[_wme.name] = _wme

        elif _wme.name in self.memory.index and _action == 'remove':
            self.memory.drop(_wme.name)

        elif _wme.name in self.memory.index and _action == 'modify':
            self.memory.loc[_wme.name] = _wme

        self.print_node()
        return self.next


    def root_match(self, _pattern):
        print('root match')
        return True


    def alpha_match(self, _pattern):
        print('alpha match')
        return True


    def beta_match(self, _pattern):
        print('beta match')
        return True


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
