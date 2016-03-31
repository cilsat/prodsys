#!/usr/bin/python

import numpy as np
import pandas as pd

import re, string

dbg = False
node_types = ['root', 'alpha', 'beta', 'rule']

class ReteNode():

    def __init__(self, _name=None, _type=None, _prev=None, _next=None, _pattern=None, _function=None):

        self.name = _name
        self.type = _type
        try:
            self.type in node_types
        except:
            print("invalid node type")
        self.prev = _prev
        self.next = _next
        self.memory = pd.DataFrame()
        self.pattern = _pattern
        self.function = _function
        self.matches = pd.DataFrame()

        if self.type == 'beta':
            self.left = pd.DataFrame()
            self.right = pd.DataFrame()
            self.depth = 0
            self.diff_type = False


    def apply_token(self, _wme, _action):

        # check if memory exists yet, and initialize if not
        if self.matches.empty:
            self.matches = pd.DataFrame(columns=_wme.keys())

        if _wme.name not in self.memory.index and _action == 'add':
            if self.function(self, _wme):
                self.matches.loc[_wme.name] = _wme
                return self.next
            else:
                return []

        elif _wme.name in self.memory.index and _action == 'remove':
            self.matches.drop(_wme.name)

        elif _wme.name in self.memory.index and _action == 'modify':
            self.matches.loc[_wme.name] = _wme


    def root_match(self, _pattern):
        if dbg: print('root match')
        return True


    def alpha_match(self, _wme):
        # immediately return false if differing types
        if _wme['type'] != self.pattern['type']:
            if dbg: print("different types for " + str(self.name))
            return False

        neg = eval(self.pattern['negate'])
        tally = []
        temp_memory = {}
        temp_wme = _wme.drop({'type'}).dropna()
        if dbg: print(self.pattern)

        # tally the truth values of individual attribute-value tuples
        for tup in self.pattern.drop({'type', 'negate'}).to_dict().iteritems():
            tally.append(self.eval_attribute(tup, temp_wme, neg, temp_memory))

        # tally truth values of att-val tuples
        ismatch = True if np.all(tally) else False

        # apply condition negation
        ismatch = (neg != ismatch)

        if ismatch:
            if dbg:
                print('temp memory:'),
                print(temp_memory)
            if temp_memory:
                self.memory = pd.DataFrame(columns=temp_memory.keys())
                self.memory.loc[_wme.name] = temp_memory
            else:
                self.memory = pd.DataFrame(index=[_wme.name])

        return ismatch


    def beta_match(self, _):
        am1 = self.left
        am2 = self.right.reset_index().rename(columns={'index':str(self.depth)})
        lam1 = len(am1.index)
        lam2 = len(am2.index)

        # if one side has no matches, then both sides have no matches
        if  lam1*lam2 > 0:
            # check for columns/variables to merge on
            try:
                bm = am1.merge(am2, how='inner')
                if self.dbg == 1: print('column merge')

            # no columns/variables to merge on :(
            except:
                # append right side if of different type
                # we return the complete set of combinations of the rows of the left and right sides
                if _diff_type:
                    comb = list(iter.product(am1.index, am2.index))
                    df = []
                    for a, b in comb:
                        df.append(am1.loc[a].append(am2.loc[b]).to_dict())
                    bm = pd.DataFrame(df)
                    #bm = pd.concat([am1, am2], join='outer', axis=1)
                    if self.dbg == 1: print('type append')

                # inner concat right side
                # check for indexes/wmes to merge on
                else:
                    bm = pd.concat([am1.set_index(str(_n-1), drop=False), am2.set_index(str(_n), drop=False)], join='inner', axis=1)
                    if self.dbg == 1: print('index concat')

            if self.dbg == 1:
                print(am1)
                print('')
                print(am2)
                print('')
                print(bm)
                print('')
        else:
            bm = pd.DataFrame()

        # check for unhandled expressions from previous round of matching
        # TODO add safeguards for [eval] and make less fugly
        unhandled = [var for var in bm.columns if len(str(var)) > 1]
        try:
            len(unhandled) < 2
        except:
            print("Warning: unpredictable behaviour ahead")
        if unhandled:
            cond = self.alpha_nodes.loc[_mem2]
            if self.dbg == 0:
                print(unhandled)
                print(cond)
            neg = eval(cond['negate'])
            cond = cond.drop({'type', 'negate'}).dropna()

            bm_idxs = []
            bm_vars = []
            for wme in [self.wm.loc[n] for n in bm.index]:
                tally_matches = []
                loop_vars = bm.loc[wme.name].to_dict()
                for tup in cond.iteritems():
                    tally, loop_vars = self.eval_attribute(tup, wme, neg, loop_vars, index=bm.index, return_var=True)
                    tally_matches.append(tally)
                # tally truth values of attributes
                ismatch = True if np.all(tally_matches) else False
                # negate matching last
                ismatch = (neg != ismatch)

                if ismatch:
                    bm_idxs.append(wme.name)
                    bm_vars.append(loop_vars)

            bm = pd.DataFrame(bm_vars, index=bm_idxs)

        return bm

        if dbg: print('beta match')
        return True


    def print_node(self):

        print('name:'),
        print(self.name),
        print(', type:'),
        print(self.type),

        if self.type == 'beta':
            print(', depth:'),
            print(self.depth)
            print('left:')
            print(self.left)
            print('right:')
            print(self.right)

        if self.prev:
            print(', prev:'),
            print(self.prev),

        if self.next:
            print(', next:'),
            print(self.next)

        if self.type == 'alpha':
            print('pattern:')
            print(self.pattern.head().to_dict())

        print('memory:')
        print(self.memory)

        print('matches:')
        print(self.matches)
        print('')

    def eval_attribute(self, _patt, _fact, _neg, _var):
        key, val = _patt
        # expression
        if val.startswith('{'):
            args = val.translate(None, '{}')
            args = args.replace('&', ' and ').replace('|', ' or ')
            free_vars = re.findall(r'[a-z]+', args)
            # not enough information!
            if free_vars:
                if free_vars[0] not in _var.keys():
                    _var[key] = '{'+args+'}'
                    match = not _neg
                # can be evaluated now
                else:
                    try:
                        del _var[key]
                    except:
                        pass
                    for varkey, varval in _var.iteritems():
                        if varkey.islower():
                            args = args.replace(varkey, varval)
                    if args[0] in operators:
                        try:
                            wm_sub = 'self.wm.loc[index][key].astype(float)'
                            result = eval(wm_sub + args)
                            match = np.any(result)
                        except:
                            print('Expression error: missing or incorrect index')
                    else:
                        match = eval(args)
            else:
                try:
                    result = eval(_fact[key] + args)
                    match = np.any(result)
                except:
                    print('Expression error: missing or incorrect index')

        # variable
        elif len(val) == 1 and val.islower():
            try:
                _var[val] = _fact[key]
                match = True
            except:
                if dbg: print('Key warning: WME has NaN values')
                match = False
        # atom
        else:
            match = True if val == _fact[key] else False
         
        return match
