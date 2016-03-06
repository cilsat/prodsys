#!/usr/bin/pythonn

import numpy as np
import pandas as pd

import re
import string

from collections import OrderedDict

# reserved keywords and characters
conditional = ['if', 'then']
action = ['add', 'remove', 'modify']
operators = '<>!=&|%'
conjuctions = ['<', '>', '<=', '>=', '!=', '==']

class Rete():

    def __init__(self, rules=None, facts=None, debug=False):
        self.dbg = debug
        # build if rules and facts are specified
        if rules and facts:
            self.init_rete(rules)
            self.init_wm(facts)
            if self.dbg:
                print(self.nodes_alpha)
                print(self.wm)
            self.matched = self.first_run()

    # generates the required Rete structures from plaintext
    def init_rete(self, _rules):
        # all conditions/actions to be parsed during pattern matching/action
        conditions = []
        actions = []

        cols = []
        # map each rule to its constituent conditions and actions, respectively
        rule_condition_map = []
        rule_action_map = []
        # for each production rule
        n_cond = 0
        for pr in [r for r in _rules.split('\n') if r]:
            try:
                # split into LHS and RHS, separated by keyword
                lhs_raw, rhs_raw = pr.split(conditional[1])
                # split into conditions and actions, separated by brackets
                conditions_raw = re.findall(r'\((.*?)\)', lhs_raw)
                actions_raw = re.findall(r'\((.*?)\)', rhs_raw)
            except:
                print("Syntax error in rule definition")

            # TODO modify to make less fugly and wrong
            temp_cond_map = []

            # convert plaintext conditions into dictionaries
            for cond in conditions_raw:
                attvals, keys = self.str_to_dict(cond, 'condition')
                conditions.append(attvals)
                [cols.append(key) for key in keys if key not in cols]
                # TODO
                temp_cond_map.append(n_cond)
                n_cond += 1

            # convert plaintext actions into dictionaries
            for act in actions_raw:
                actions.append(self.str_to_dict(act, 'action'))

            # TODO
            rule_condition_map.append(temp_cond_map)

        # alpha nodes: the set of rule conditions
        self.cols = cols
        self.nodes_alpha = pd.DataFrame(conditions, columns=cols)
        self.conditions = conditions
        # rule map: maps rules to their conditions 
        self.map_alpha = rule_condition_map

    # initializes WM from a joint table of all WMEs from plaintext facts
    def init_wm(self, _facts):
        wmes = []
        cols = []
        for wme in filter(None, _facts.split('\n')):
            wme_dict, keys = self.str_to_dict(wme, 'condition')
            [cols.append(key) for key in keys if key not in cols]
            wmes.append(wme_dict)
        self.wm = pd.DataFrame(wmes, columns=cols)

    def str_to_dict(self, _str, _sender="unspecified"):
        # attribut-value tuple
        attval = OrderedDict()
        keys = []
        # remove any punctuation from string
        temp_str = _str.translate(None, '()')
        # for each attribute-value tuple split on ':' and make dict
        for tup in temp_str.split():
            att, val = tup.split(':')
            if att not in keys: keys.append(att)
            try: attval[att] = val
            except: print("Syntax error in " + _sender + ": " + tup)
        return attval, keys

    def first_run(self):
        try:
            an = self.nodes_alpha.copy()
            an = [an.loc[n].dropna() for n in an.index]
            wm = self.wm
            #bm = self.build_map_beta(self.map_alpha)
        except:
            print("Error: Rete uninitialized")

        # for each node and for each wme
        am = []
        for cond in an:
            if self.dbg:
                print('alpha '),
                print(cond.name),
                print([[key,val] for key, val in cond.iteritems()])
            am.append(self.alpha_match(cond, wm))

        self.alpha_memory = am
        self.beta_memory = []
        
        rules_matched = []
        for rule in self.map_alpha:
            bm = self.alpha_memory[rule[0]]
            rule_matches = []
            for n in range(len(rule)-1):
                bm = self.beta_match(bm, rule[n+1])
                if bm.empty: break
                rule_matches.append(bm)
            rules_matched.append(bm)
            self.beta_memory.append(rule_matches)
        return rules_matched

    def alpha_match(self, _cond, _wm):
        cond = _cond.drop({'type', 'negation'})
        neg = eval(_cond['negation'])

        alpha_idxs = []
        alpha_vars = []
        
        # type matching first
        wm_type = _wm.loc[_wm['type'] == _cond['type']]
        for wme in [wm_type.loc[n] for n in wm_type.index]:
            local_vars = {}
            tally_matches = []

            # match all attributes next
            for tup in cond.iteritems():
                tally_matches.append(self.eval_attribute(tup, wme, neg, local_vars))

            if self.dbg:
                print(list(cond.keys())),
                print(tally_matches)

            # tally truth values of attributes
            ismatch = True if np.all(tally_matches) else False
            # negation matching last
            ismatch = (neg != ismatch)

            if ismatch:
                alpha_idxs.append(wme.name)
                alpha_vars.append(local_vars)

        # returns alpha memory, with indexes representing WME
        return pd.DataFrame(alpha_vars, index=alpha_idxs)

    def beta_match(self, _mem1, _mem2):
        am1 = _mem1
        am2 = self.alpha_memory[_mem2]

        try:
            bm = pd.merge(am1, am2, left_index=True, right_index=True)
        except:
            print('Too many variables somewhere: game over')
            bm = pd.DataFrame()

        # check for unhandled expressions from previous round of matching
        # TODO add safeguards for [eval] too
        unhandled = [var for var in bm.columns if len(var) > 1]
        print(unhandled)
        if unhandled:
            for key in unhandled:
                for mem in [bm.loc[n] for n in bm.index]:
                    cond = self.nodes_alpha.loc[_mem2]
                    neg = eval(cond['negation'])
                    cond = cond.drop({'type', 'negation'})
                    for tup in cond.iteritems():
                        print(self.eval_attribute(tup, self.wm.loc[mem.name], neg, mem.to_dict()))

        return bm

    def eval_attribute(self, _cond, _fact, _neg=False, _var={}):
        key, val = _cond
        if self.dbg:
            print(key in _fact.index)
        print(key, val)
        # expression
        if val.startswith('{'):
            args = val.translate(None, '{}')
            args = args.replace('&', ' and ').replace('|', ' or ')
            free_vars = re.findall(r'[a-z]+', args)
            # not enough information!
            if free_vars not in _var.keys():
                _var[key] = '{'+args+'}'
                match = not _neg
            # can be evaluated now
            else:
                for varkey, varval in _var:
                    args.replace(varkey, varval)
                match = eval(_fact[key] + args) if args[0] in operators else eval(args)
        # variable
        elif len(val) == 1 and val.islower():
            try:
                _var[val] = _fact[key]
            except:
                print('Key warning: fact has no such value')
            match = True
        # atom
        else:
            match = True if val == _fact[key] else False
         
        return match
