#!/usr/bin/pythonn

import numpy as np
import pandas as pd

import re
import string

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
            self.first_run()

            if self.dbg:
                print(self.nodes_alpha)
                print(self.wm)
                print(self.alpha_memory)

    # generates the required Rete structures from plaintext
    def init_rete(self, _rules):
        # all conditions/actions to be parsed during pattern matching/action
        conditions = []
        actions = []

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
                conditions.append(self.str_to_dict(cond, 'condition'))
                # TODO
                temp_cond_map.append(n_cond)
                n_cond += 1

            # convert plaintext actions into dictionaries
            for act in actions_raw:
                actions.append(self.str_to_dict(act, 'action'))

            # TODO
            rule_condition_map.append(temp_cond_map)

        # alpha nodes: the set of rule conditions
        self.nodes_alpha = pd.DataFrame(conditions)
        self.conditions = conditions
        # rule map: maps rules to their conditions 
        self.map_alpha = rule_condition_map

    # initializes WM from a joint table of all WMEs from plaintext facts
    def init_wm(self, _facts):
        wmes = []
        for wme in filter(None, _facts.split('\n')):
            wme_dict = self.str_to_dict(wme, 'wme')
            wmes.append(wme_dict)
        self.wm = pd.DataFrame(wmes)

    def str_to_dict(self, _str, _sender="unspecified"):
        # attribut-value tuple
        attval = {}
        # remove any punctuation from string
        temp_str = _str.translate(None, '()')
        # for each attribute-value tuple split on ':' and make dict
        for tup in temp_str.split():
            att, val = tup.split(':')
            try: attval[att] = val
            except: print("Syntax error in " + _sender + ": " + tup)
        return attval

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

        for rule in self.map_alpha:
            bm = self.alpha_memory[rule[0]]
            rule_matches = []
            for n in range(len(rule)-1):
                print(bm)
                bm = self.beta_match(bm, self.alpha_memory[rule[n+1]])
                rule_matches.append(bm)
            print(rule_matches)

    def alpha_match(self, _cond, _wm):
        cond = _cond.drop({'type', 'negation'})
        neg = eval(_cond['negation'])

        alpha_idxs = []
        alpha_vars = []
        
        # type matching first
        wm_type = _wm.loc[_wm['type'] == _cond['type']].dropna(axis=1)
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
        am2 = _mem2

        # perform inner join on indexes of input memories
        bm = pd.concat([am1, am2], join='inner', axis=1)

        # check for unhandled expressions from previous round of matching
        if '{exp}' in bm.columns:            
            # assumes that types already match!
            cond = self.nodes_alpha.loc[_cond1].drop({'type', 'negation'}).dropna(axis=1)
            neg = eval(_cond1['negation'])
            # take index memory from current node
            wm_subset = self.wm.loc[am1.index]
            # take column memory from other node
            other_var = am2.to_dict('records')
            # test to see if current alpha nodes' memory aligns with other nodes' dict
            #if len(wm_subset) == len(other_var):

        return bm

    def eval_attribute(self, _cond, _fact, _neg=False, _var={}):
        key, val = _cond
        # expression
        if val.startswith('{'):
            args = val.translate(None, '{}')
            args = args.replace('&', ' and ').replace('|', ' or ')
            free_vars = re.findall(r'[a-z]+', args)
            # not enough information!
            if free_vars not in _var.keys():
                _var['{exp}'] = args
                match = not _neg
            # can be evaluated now
            else:
                for varkey, varval in _var:
                    args.replace(varkey, varval)
                match = eval(_fact[key] + args) if args[0] in operators else eval(args)
        # variable
        elif len(val) == 1 and val.islower():
            _var[val] = _fact[key]
            match = True
        # atom
        else:
            match = True if val == _fact[key] else False
         
        return match
