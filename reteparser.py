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

    def __init__(self, rules=None, facts=None, policy='order', debug=False):
        self.dbg = debug
        # build if rules and facts are specified
        if rules and facts:
            self.init_rete(rules)
            self.init_wm(facts)

            if self.dbg:
                print(self.nodes_alpha)
                print(self.wm)

            self.threshold = 10
            self.saved_memory = [{'n_rule':'None', 'rule':pd.DataFrame()}]*self.threshold

            self.refractor_table = [[]]*len(self.map_alpha)

            """
            m = self.matched
            chosen = self.resolve_conflicts(m)
            while chosen:
                temp_wm = self.apply_action(chosen[0], chosen[1], v, wm, a, c)
                print('Iteration ' + str(n))
                print(temp_wm)
                print('')
                wms.append(temp_wm)
                wm = []
                wm = temp_wm
                temp_wm = []
                #m, v = match(wm, a, debug=True)
                m, v = match(wm, a, debug=debug)
                chosen = resolve_conflicts(m)
            """


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
            bm = pd.DataFrame()
            rule_matches = []
            for n in range(len(rule)):
                bm = self.beta_match(bm, rule[n])
                rule_matches.append(bm)
            rules_matched.append(bm)
            self.beta_memory.append(rule_matches)

        print(rules_matched)

        matched = []
        for n, rule in enumerate(rules_matched):
            print(rule)
            if rule.isnull().values.any():
                matched.append(rule.to_dict())
            else:
                matched.append([self.wm.loc[n].to_dict() for n in rule.index])

        print(matched)
        self.matched = matched

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
                tally_matches.append(self.eval_attribute(tup, wme, neg, local_vars, index=wm_type.index))

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
            if len(am1.columns) == 0:
                bm = pd.concat([am2, am1], join='outer', axis=1)
            else:
                bm = pd.merge(am1, am2, how='inner')
        except:
            print('Too many variables somewhere: game over')
            bm = pd.DataFrame()

        # check for unhandled expressions from previous round of matching
        # TODO add safeguards for [eval] and make less fugly
        unhandled = [var for var in bm.columns if len(var) > 1]
        try:
            len(unhandled) < 2
        except:
            print("Warning: unpredictable behaviour ahead")
        if unhandled:
            print(bm)
            cond = self.nodes_alpha.loc[_mem2]
            if self.dbg:
                print(unhandled)
                print(cond)
            neg = eval(cond['negation'])
            cond = cond.drop({'type', 'negation'}).dropna()

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
                # negation matching last
                ismatch = (neg != ismatch)

                if ismatch:
                    bm_idxs.append(wme.name)
                    bm_vars.append(loop_vars)

            bm = pd.DataFrame(bm_vars, index=bm_idxs)

        return bm

    def resolve_conflicts(self, _matches, _policy='order'):
        if _policy == 'order':
            # always choose the first
            for n in range(len(_matches)):
                if not len(_matches[n].index) == 0:
                    chosen = _matches[n]
                    n_chosen = n
                    break

            loop_test = []
            for n in range(self.threshold):
                if self.saved_memory[-(n+1)]['n_rule'] == n_chosen:
                    loop_test.append(True)
                else:
                    loop_test.append(False)
            if np.all(loop_test):
                print("You're probably stuck in some kind of loop")

            self.saved_memory.append({'n_rule':chosen, 'rule':chosen})

        elif _policy == 'recent_first' or _policy == 'recent_last':
            chosen = None
            for i, cand in enumerate(_matches):
                for n in range(len(self.saved_memory)):
                    iterator = -(n+1) if _policy == 'recent_first' else n
                    chos = self.saved_memory[-(n+1)]['n_rule']
                    # look for first rule in memory that is in matches
                    if len(cand.index) > 0 and i == chos:
                        chosen = cand
                        self.saved_memory.append({'n_rule':i, 'rule':chosen})
                        break
            
            if chosen == None:
                print('No recently chosen rules, using order instead')
                chosen = self.resolve_conflicts(_matches)
            
        # choose most specific rule: the rule for which its WMEs are the subset of the most other rules
        elif _policy == 'specific':
            chosen_wmes = [set(rule.index) for rule in _matches if len(rule.index) > 0]
            tally = [0]*len(chosen_wmes)
            for i, c in enumerate(chosen_wmes):
                for j, d in enumerate(chosen_wmes):
                    if c.issuperset(d): tally[j]+=1
            chosen = _matches[np.argmax(tally)]

        # forbid repetition of specific WME-Rule pairs
        elif _policy == 'refractoriness':
            for i, rule in enumerate(_matches):
                for j in rule.index:
                    if j not in self.refractor_table[i]:
                        chosen = rule
                        self.refractor_table[i].append(j)

        return chosen

    def eval_attribute(self, _cond, _fact, _neg=False, _var={}, index=None, return_var=False):
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
                    print(_var)
                    for varkey, varval in _var.iteritems():
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
            except:
                print('Key warning: fact has no such value')
            match = True
        # atom
        else:
            match = True if val == _fact[key] else False
         
        if return_var:
            return match, _var
        else:
            return match

    def apply_action(self, _chosen):
        # get variables from conditions
        consequence = _consequences[_n_rule]

        for n_cons_c in range(len(consequence.index)):
            cons_clause = consequence.iloc[n_cons_c]
            action = cons_clause['action']        

            if action == 'remove':
                _wm = _wm.drop(int(cons_clause['on']) - 1)
            elif action == 'add':
                values = cons_clause.drop({'action', 'on'})
                try:
                    rule_vars = _rule_vars[_n_rule]
                except:
                    rule_vars = {}
                new_values = parse_values(values, rule_vars)
                df = dict(zip(values.keys(), new_values))
                _wm = _wm.append(df, ignore_index=True)
            elif action == 'modify':
                wme_id = _n_wmes[int(cons_clause['on']) - 1]
                values = cons_clause.drop({'action', 'on'})
                try:
                    rule_vars = _rule_vars[_n_rule]
                except:
                    rule_vars = {}
                new_values = parse_values(values, rule_vars)
                for n_key in range(len(values.keys())):
                    _wm.iloc[wme_id][values.keys()[n_key]] = new_values[n_key]

        new_wm = _wm.copy()
        _wm = []

        return new_wm

    def parse_values(_values, _vars):
        out_values = []
        for value in _values:
            value = str(value)
            # evaluation
            if value.startswith('['):
                args = value.translate(None, '[]')
                args = args.replace('&', ' and ').replace('|', ' or ')
                vars = re.findall(r'[a-z]+', args)
                for var in vars:
                    try:
                        args = args.replace(var, _vars[var])
                    except:
                        print('evaluation error: no variables found')
                result = eval(args)
                out_values.append(str(result))

            # variables
            elif len(value) == 1 and value.islower():
                out_values.append(str(_vars[value]))

            # atom
            else:
                out_values.append(str(value))
        
        return out_values

