#!/usr/bin/pythonn

import numpy as np
import pandas as pd

import re
import string

from collections import OrderedDict
import itertools as iter

from IPython.display import display, HTML

# reserved keywords and characters
conditional = ['if', 'then']
action = ['add', 'remove', 'modify']
operators = '<>!=&|%'
conjuctions = ['<', '>', '<=', '>=', '!=', '==']

class Rete():

    def __init__(self, rules='rules', facts='facts', policy='refractor', debug='web'):
        self.dbg = debug
        # build if rules and facts are specified
        if rules and facts:
            # parse rules: build alpha nodes, conditions, and actions
            self.init_rete(open(rules).read())
            # parse facts: build working memory
            self.init_wm(open(facts).read())
            # wme index counter: gives out wme index during adds
            self.wm_index = len(self.wm.index)

            if self.dbg == 'cli':
                print(self.nodes_alpha)
                print(self.wm)

            if self.dbg == 'web':
                print('Alpha Nodes:')
                display(self.nodes_alpha)

            self.match()
            if self.dbg == 'cli':
                print('working memory')
                print(self.wm)

            self.threshold = 10
            self.saved_memory = [{'n_rule':'None', 'rule':pd.DataFrame()}]*self.threshold
            self.refractor_table = [[] for _ in range(len(self.map_alpha))]
            self.policy = policy

            m = self.matches
            #print(self.matches)

            chosen = self.resolve_conflicts(m, self.policy)
            print('')

            n_iter = 0

            while chosen:
                if self.dbg == 'web':
                    print('\n' + str(n_iter) + ' Working Memory:')
                    display(self.wm)

                self.apply_action(chosen)

                if self.dbg == 'cli':
                    print('working memory')
                    print(self.wm)

                self.match()
                #print(self.matches)
                try:
                    chosen = self.resolve_conflicts(self.matches, self.policy)
                    n_iter += 1
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
        except:
            print("Error: Rete uninitialized")

        # alpha matching: generate alpha memory for each alpha node
        am = []
        for cond in an:
            if self.dbg == 0:
                print('alpha '),
                print(cond.name),
                print([[key,val] for key, val in cond.iteritems()])
            am.append(self.alpha_match(cond, wm))
        self.alpha_memory = am

        # beta matching: generate beta memory iteratively for each beta node
        # TODO modify for use with rete network rather than alpha map
        self.beta_memory = []
        rules_matched = []
        for rule in self.map_alpha:
            rule_matches = []
            # check if rule has multiple conditions: if not, just pass the alpha
            bm = self.alpha_memory[rule[0]].reset_index().rename(columns={'index':'0'})
            if len(rule) > 1:
                node_type = self.nodes_alpha.loc[rule[0], 'type']
                for n in range(1, len(rule)):
                    # determine whether we need to append or concat on node
                    diff_type = False
                    curr_type = self.nodes_alpha.loc[rule[n], 'type']
                    if self.dbg == 1:
                        print(node_type),
                        print(curr_type)
                    if node_type != curr_type:
                        diff_type = True
                    # previous beta memory and alpha mem index is passed (rather than the mem itself)
                    bm = self.beta_match(bm, rule[n], n, diff_type)
                    rule_matches.append(bm)
                    node_type = curr_type
            else:
                if self.dbg == 1: print('\nno beta match')

            rules_matched.append(bm)
            self.beta_memory.append(rule_matches)

        self.rules_memory = rules_matched

        # finally, generate a list of matching rules-wmes
        matches = []
        for nrule, rule in enumerate(rules_matched):
            rule_depth = range(len(self.map_alpha[nrule]))
            partial_matches = []
            for n in rule.index:
                try:
                    wme_set = [rule.loc[n, str(dep)] for dep in rule_depth]
                    partial_matches.append(wme_set)
                except:
                    partial_matches.append([])
            matches.append(partial_matches)
        self.matches = matches

    def alpha_match(self, _cond, _wm):
        cond = _cond.drop({'type', 'negate'})
        neg = eval(_cond['negate'])

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

            if self.dbg == 0:
                print(list(cond.keys())),
                print(tally_matches)

            # tally truth values of attributes
            ismatch = True if np.all(tally_matches) else False
            # negate matching last
            ismatch = (neg != ismatch)

            if ismatch:
                alpha_idxs.append(wme.name)
                alpha_vars.append(local_vars)

        # returns alpha memory, with indexes representing WME
        return pd.DataFrame(alpha_vars, index=alpha_idxs)

    def beta_match(self, _mem1, _mem2, _n, _diff_type=True):
        am1 = _mem1
        am2 = self.alpha_memory[_mem2].reset_index().rename(columns={'index':str(_n)})
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
            cond = self.nodes_alpha.loc[_mem2]
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

    def resolve_conflicts(self, _matches, _policy='order'):

        if self.dbg == 'cli':
            print('')
            print('conflict set -> chosen (rule:[wme])')
        all_rules = []
        for n_rule, rule in enumerate( _matches):
            for wme in rule:
                all_rules.append({'rule':n_rule, 'wme':wme})
                print(str(n_rule) + ':' + str(wme) + ','),

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

        elif _policy == 'most_recent' or _policy == 'least_recent':
            sm = list(reversed(self.saved_memory))
            last_used = [None for _ in range(len(all_rules))]

            for n_rule, rule in enumerate(all_rules):
                for n_s_rule, s_rule in enumerate(sm, 1):
                    if rule == s_rule:
                        last_used[n_rule] = n_s_rule
                    break

            print('last used: '),
            print(last_used)

            if last_used != [None for _ in range(len(all_rules))]:
                if _policy == 'most_recent':
                    chosen = all_rules[np.argmin(last_used)]
                elif _policy == 'least_recent':
                    chosen = all_rules[np.argmax(last_used)]

            if chosen == None:
                print('Current conflict set has never been chosen, refractoring')
                chosen = self.resolve_conflicts(_matches, _policy='refractor')
            
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
                print('all rule-wme pairs have been used: terminating')
                raise SystemExit

        # update refractor table anyway, just in case
        if _policy != 'refractor' and chosen:
            self.refractor_table[chosen['rule']].append(chosen['wme'])

        # detect infinite loops through a 10 item loop test
        loop_test = []
        for n in range(self.threshold):
            if self.saved_memory[-(n+1)] == chosen:
                loop_test.append(True)
            else:
                loop_test.append(False)

        self.saved_memory.append(chosen)

        # if loop_test contains a False value then everything's OK
        if not np.any(False == np.array(loop_test)):
            print('')
            print("You're probably stuck in some kind of loop: refractoring")
            self.policy = 'refractor'
            chosen = self.resolve_conflicts(_matches, _policy=self.policy)

        if self.dbg == 'cli':
            print(' -> ' + str(chosen['rule']) + ':' + str(chosen['wme']))
        if self.dbg == 'web':
            print('Chosen Rule/WME:'),
            display(self.nodes_alpha.loc[self.map_alpha[chosen['rule']]].dropna(axis=1, how='all')),
            display(self.wm.loc[set(chosen['wme'])])

        return chosen

    def eval_attribute(self, _cond, _fact, _neg=False, _var={}, index=None, return_var=False):
        key, val = _cond
        if self.dbg == 0:
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
                target_idx = self.wm_index
                for key, val in df.iteritems():
                    self.wm.loc[target_idx, key] = val
                self.wm_index += 1

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

