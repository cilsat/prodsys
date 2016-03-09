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

            self.match()
            print(self.wm)

            self.threshold = 10
            self.saved_memory = [{'n_rule':'None', 'rule':pd.DataFrame()}]*self.threshold

            if policy == 'refractor':
                self.refractor_table = [[] for _ in range(len(self.map_alpha))]

            m = self.matches
            #print(self.matches)

            chosen = self.resolve_conflicts(m, policy)
            print('')

            while chosen:
                self.apply_action(chosen)
                print(self.wm)

                self.match()
                #print(self.matches)
                chosen = self.resolve_conflicts(self.matches, policy)
                try:
                    print('')
                except:
                    print('')
                    print('End of process')
                    break
                

    # generates the required Rete structures from plaintext
    def init_rete(self, _rules):
        # all conditions/actions to be parsed during pattern matching/action
        conditions = []
        actions = []

        cond_cols = []
        act_cols = []
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
                [cond_cols.append(key) for key in keys if key not in cond_cols]
                # TODO
                temp_cond_map.append(n_cond)
                n_cond += 1

            temp_act_map = []
            # convert plaintext actions into dictionaries
            for act in actions_raw:
                attvals, keys = self.str_to_dict(act, 'action')
                [act_cols.append(key) for key in keys if key not in act_cols]
                temp_act_map.append(attvals)

            actions.append(pd.DataFrame(temp_act_map, columns=act_cols))

            # TODO
            rule_condition_map.append(temp_cond_map)

        # alpha nodes: the set of rule conditions
        self.cond_cols = cond_cols
        self.nodes_alpha = pd.DataFrame(conditions, columns=cond_cols)
        self.conditions = conditions
        self.actions = actions
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

    def match(self):
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
            for n in range(1, len(rule)):
                bm = self.beta_match(bm, rule[n])
                rule_matches.append(bm)
            rules_matched.append(bm)
            self.beta_memory.append(rule_matches)

        self.rules_memory = rules_matched

        matches = []
        for rule in rules_matched:
            if rule.isnull().values.any():
                matches.append([list(rule.index)])
            else:
                matches.append([[n] for n in rule.index])

        self.matches = matches

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

        if len(am1.columns) == 0:
            if  len(am1.index) > 0:
                bm = am1.append(am2)
            else:
                bm = am1
        else:
            try:
                bm = pd.merge(am1, am2, how='inner')
            except:
                bm = pd.concat([am1, am2], join='inner', axis=1)

        # check for unhandled expressions from previous round of matching
        # TODO add safeguards for [eval] and make less fugly
        unhandled = [var for var in bm.columns if len(var) > 1]
        try:
            len(unhandled) < 2
        except:
            print("Warning: unpredictable behaviour ahead")
        if unhandled:
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

        print('')
        print('conflict set (rule:wme)')
        all_rules = []
        for n_rule, rule in enumerate( _matches):
            for wme in rule:
                all_rules.append({'rule':n_rule, 'wme':wme})
                print(str(n_rule) + ':' + str(wme).translate(None, '[]') + ','),
        print('')

        chosen = None

        if _policy == 'order':
            # always choose the first
            try:
                chosen = all_rules[0]
            except:
                print('')
                print('No rules to choose from')

        elif _policy == 'random':
            # choose a random rule-wme pair
            r = np.random.randint(0, len(all_rules))
            chosen = all_rules[r]

        elif _policy == 'recent_first' or _policy == 'recent_last':
            for n in range(len(self.saved_memory)):
                iterator = -(n+1) if _policy == 'recent_first' else n
                mem = self.saved_memory[iterator]
                print(mem)
                for rule in all_rules:
                    # look for first rule in memory that is in matches
                    if mem == rule:
                        chosen = rule
                        break
                else:
                    continue
                break

            if chosen == None and _policy == 'recent_first':
                print('No recently chosen rules, using order instead')
                chosen = self.resolve_conflicts(_matches)
            elif chosen == None and _policy == 'recent_last':
                # choose a random wme that isn't in memory
                for rule in all_rules:
                    if rule not in self.saved_memory:
                        chosen = rule
            
        # choose most specific rule: the rule for which its WMEs are the subset of the most other rules
        elif _policy == 'specific':
            # each rule-wme tuple has a tally
            for tup in all_rules:
                tup['tally'] = 0

            # each rule has a tally
            rule_tally = [0 for _ in range(len(_matches))]

            # set up a nested loop of rule matches against rule-wme tuples 
            for i in _matches:
                c = set([ci for si in i for ci in si])
                for nj, j in enumerate(_matches):
                    d = set([dj for sj in j for dj in sj])
                    # count how many rule wmes each rule-wme tuple is a subset of
                    if c.issuperset(d): 
                        rule_tally[nj] += 1
                        for tup in all_rules:
                            if tup['rule'] == nj: tup['tally'] += 1

            chosen_rule = np.argmax(rule_tally)
            # choose rule-wme tuple with the highest tally
            chosen_wmes = [rule for rule in all_rules if rule['rule'] == chosen_rule]
            tallies = [rule['tally'] for rule in chosen_wmes]
            try:
                chosen = chosen_wmes[np.argmax(tallies)]
            except:
                print('')
                print("No rules to choose from")
                chosen = None

        # forbid repetition of specific WME-Rule pairs
        # we have a refractor table of each rule
        elif _policy == 'refractor':
            for rule in all_rules:
                n_rule = rule['rule']
                wme = rule['wme']
                if wme not in self.refractor_table[n_rule]:
                    chosen = rule
                    self.refractor_table[n_rule].append(wme)
                    break

            if chosen == None:
                print('')
                print('All rule-wme pairs used: terminating')
                raise SystemExit

        loop_test = []
        for n in range(self.threshold):
            if self.saved_memory[-(n+1)] == chosen:
                loop_test.append(True)
            else:
                loop_test.append(False)
        # if loop_test contains a False value then everything's OK
        if not np.any(False == np.array(loop_test)):
            print('')
            print("You're probably stuck in some kind of loop: terminating")
            raise SystemExit

        self.saved_memory.append(chosen)
        print('chosen (rule:wme)')
        print(str(chosen['rule']) + ':' + str(chosen['wme']).translate(None, '[]'))

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
        n_rule = _chosen['rule']
        n_wme = _chosen['wme']

        # memory from selection phase for chosen rule/wme pair
        chosen_memory = self.rules_memory[n_rule]
        # rule conditions: we don't have a direct mapping of rule->conditions, so we go through map_alpha
        conditions = self.nodes_alpha.iloc[self.map_alpha[n_rule]]
        # the action itself
        actions = self.actions[n_rule]

        # iterate through the actions
        for n_act in actions.index:
            action_node = actions.loc[n_act]
            action_name = action_node['action']        

            if action_name == 'remove':
                # drop the WME specified in the 'on' attribute corresponding to the WME specified in the chosen 'wme' field 
                self.wm = self.wm.drop(n_wme[int(action_node['on']) - 1])

            elif action_name == 'add':
                # acquire values to add
                values = action_node.drop({'action', 'on'})
                new_values = self.parse_values(values, chosen_memory)
                df = dict(zip(values.keys(), new_values))

                # insert new WME at the end of the table and make sure the columns are available
                idx = list(self.wm.index)
                target_idx = idx[-1] if len(idx) > 0 else 0
                for key, val in df.iteritems():
                    self.wm.loc[target_idx, key] = val

            elif action_name == 'modify':
                wme = self.wm.loc[n_wme[int(action_node['on'])-1]]
                values = action_node.drop({'action', 'on'}).to_dict()
                new_values = self.parse_values(values, chosen_memory)
                action_pairs = dict(zip(values.keys(), new_values))
                for key, val in action_pairs.iteritems():
                    wme = n_wme[int(action_node['on'])-1]
                    self.wm.loc[wme, key] = val

        return self.wm

    def parse_values(self, _values, _vars):
        out_values = []
        for key, value in _values.iteritems():
            value = str(value)
            # evaluation
            if value.startswith('['):
                args = value.translate(None, '[]')
                args = args.replace('&', ' and ').replace('|', ' or ')
                vars = re.findall(r'[a-z]+', args)
                for var in vars:
                    new_val = _vars[var].dropna().values[0]
                    args = args.replace(var, new_val)
                result = eval(args)
                out_values.append(str(result))

            # variables
            elif len(value) == 1 and value.islower():
                new_val = _vars[value].dropna().values[0]
                out_values.append(new_val)

            # atom
            else:
                out_values.append(str(value))
        
        return out_values

