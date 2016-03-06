#!/usr/bin/pythonn

import numpy as np
import pandas as pd

import re
import string
from itertools import chain

# names reserved for use by the system
conditional = ['if', 'then']
action = ['add', 'remove', 'modify']
operators = '<>!=&|%'
conjuctions = ['<', '>', '<=', '>=', '!=', '==']

class Rete():

    def __init__(self, rules=None, facts=None):
        # build if rules and facts are specified
        if rules and facts:
            self.init_rete(rules)
            self.init_wm(facts)
            self.init_alpha_mem()

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
        self.alpha_nodes = conditions
        # rule map: maps rules to their conditions 
        self.rule_map = rule_condition_map

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

    def init_alpha_mem(self):
        try:
            an = self.alpha_nodes
            wm = [self.wm.ix[n].dropna().to_dict() for n in range(len(self.wm.index))]
        except:
            print("Error: Rete uninitialized")

        # initialize memory for each alpha node
        am = [pd.DataFrame()]*len(an)
        # for each node and for each wme
        n=0
        for i, cond in enumerate(an):
            for j, wme in enumerate(wm):
                print(n),
                print(cond),
                print(wme),
                self.match(wme, cond.copy(), am[i], j)
                n+=1

        self.alpha_memory = am

    # checks if a given fact matches a given pattern/condition 
    def match(self, _wme, _cond, _mem, _idx):
        # match type first and negation last
        # TODO make this less hacky
        if _cond['type'] == _wme['type']:
            _cond.pop('type')
            negation = eval(_cond.pop('negation'))

            tally_matches = []
            local_vars = {}
            for key, val in _cond.iteritems():
                # expression
                if val.startswith('{'):
                    val = val.translate(None, '{}')
                    for var_key, var_val in local_vars:
                        val.replace(var_key, var_val)
                    result = eval(_wme[key] + val) if val[0] in operators else eval(val)
                    val_match = True if np.all(result) else False
                    tally_matches.append(val_match)
                # evaluation
                elif val.startswith('['):
                    pass
                # variable
                elif len(val) == 1 and val.islower():
                    local_vars[val] = _wme[key]
                    tally_matches.append(True)
                # atom
                else:
                    val_match = True if val == _wme[key] else False
                    tally_matches.append(val_match)
            print(local_vars)
                
            ismatch = np.all(tally_matches)
            # handle negation of condition
            ismatch = (negation != ismatch)

            if ismatch:
                for var_key, var_val in local_vars.copy().iteritems():
                    _mem.loc[_idx, var_key] = var_val 

"""
this basically works on a multi-level truth table / tree with:
    - rules
    - clauses
    - attributes
working memory elements are matched 
"""
def match(_wm, _antecedents, debug=True):

    # match rules in sequence
    matches = []
    variables = []
    for n_rule in range(len(_antecedents)):
        antecedent = _antecedents[n_rule]

        if debug:
            print('')
            print('RULE ' + str(n_rule))
        rule_vars = {}
        rule_table = []

        # persist WME variables and WME truth tables across clauses
        wmes_vars = [{}]*len(_wm.index)
        wmes_truth_table = []

        # WMEs and antecedent clauses interact through their types
        # an antecedent may contain clauses of various types
        # we assume that clauses of the same type are grouped
        cur_type = antecedent['type'].iloc[0]
        # for clauses in the rule
        for n_clause in range(len(antecedent.index)):
            clause = antecedent.iloc[n_clause]

            # if we've changed clause type, resolve the current WME truth table
            if wmes_truth_table and cur_type != clause['type']:
                wmes_truth_table = np.vstack(wmes_truth_table)
                matched_wmes = np.all(wmes_truth_table.T, axis=-1).reshape(-1)
                rule_table.append(dict(zip(wmes.index, matched_wmes)))
                try:
                    rule_vars.update(dict(zip(wmes.index, wmes_vars)))
                except:
                    print("something went terribly wrong and you probably can't fix it")

                if debug:
                    print('Clause type change triggered')
                    #print('WMEs truth table:')
                    #print(wmes_truth_table)

                wmes_truth_table = []
                cur_type = clause['type']

            # get only wmes that match clause type
            wmes = _wm.loc[_wm['type'] == clause['type']]
            clause_drop = clause.drop({'negation', 'type'}).dropna()
            #wmes = _wm
            #clause_drop = clause.drop({'negation'}).dropna()

            if debug:
                print('')
                print('CLAUSE ' + str(n_clause))
                #print('Negation: ' + str(clause['negation']))
                #print(clause_drop)

            if not wmes.empty:
                wmes_vars, temp_wmes_truth_table = clause_match(clause_drop, wmes, wmes_vars, debug=debug)
                # check for negation and append
                if temp_wmes_truth_table:
                    wmes_truth_table.append(clause['negation'] != temp_wmes_truth_table)
                    if debug:
                        print('End of clause round WME: '),
                        print(wmes_truth_table)
                        print('')

        if wmes_truth_table:
            wmes_truth_table = np.vstack(wmes_truth_table)
            matched_wmes = np.all(wmes_truth_table.T, axis=-1).reshape(-1)
            rule_table.append(dict(zip(wmes.index, matched_wmes)))
            try:
                rule_vars.update(dict(zip(wmes.index, wmes_vars)))
            except:
                print("something went terribly wrong and you probably can't fix it")
        if debug:
            #print('WMEs truth table:')
            #print(wmes_truth_table)
            print(rule_vars)

        # SUPER HACKY
        per_rule = []
        var_rule = []
        # resolve type groupings first
        if np.all([np.any(r.values()) for r in rule_table]):
            for r in rule_table:
                for key, val in r.iteritems():
                    if val:
                        per_rule.append(key)
                        if rule_vars[key]:
                            var_rule.append(rule_vars[key])
        matches.append(per_rule)
        variables.extend(var_rule)

    if debug:
        print('')
        print(matches)
        print(variables)

    return matches, variables

def clause_match(_clause, _wmes, _wmes_vars, debug=True):

    temp_wmes_vars = []
    temp_wmes_truth_table = []
    for n_wme in range(len(_wmes.index)):
        wme = _wmes.iloc[n_wme]
        wme_vars = _wmes_vars[n_wme].copy()
        #wme_truth_table = temp_wmes_truth_table[n_wme]

        clause_truth_table = []
        # check each attribute except 'negation'
        for attribute in _clause.index:
            value = str(_clause[attribute])
            # expression
            if value.startswith('{'):
                args = value.translate(None, '{}')
                args = args.replace('&', ' and ').replace('|', ' or ')
                vars = re.findall(r'[a-z]+', args)
                # starts with a var or atom: evaluate as per usual
                if args[0] not in operators:
                    try:
                        for var in vars:
                            args = args.replace(var, wme_vars[var])
                        result = eval(args)
                        clause_truth_table.append(np.any(result))
                    except:
                        print("expression: variable not found")
                        clause_truth_table.append(np.NaN)
                # starts with an operator: evaluate for entire WM
                else:
                    col = [c for c in _clause.index if c != attribute]
                    trunc = _wmes.iloc[np.any((_wmes[col] == _clause), axis=-1)]
                    
                    cmd = "trunc['" + attribute + "'].values.astype(float)"
                    try:
                        for var in vars:
                            args = args.replace(var, wme_vars[var])
                        result = eval(cmd + args)
                        clause_truth_table.append(np.any(result))
                    except:
                        print("expression op in front: something went wrong")
                        clause_truth_table.append(np.NaN)

            # evaluation
            elif value.startswith('['):
                if not wme_vars:
                    print("expression: no variables set")
                    break
                args = value.translate(None, '[]')
                vars = re.findall(r'[a-z]+', args)
                # starts with a var or atom: evaluate as per usual
                try:
                    for var in vars:
                        args = args.replace(var, wme_vars[var])
                    result = eval(args)
                    clause_truth_table.append(np.any(result))
                except:
                    print("expression: variable not found")

            #conjunction
            elif value[0] in string.punctuation:
                print('conjuction triggered')
                cmd = "_wmes['" + attribute + "'].values.astype(float)"
                try:
                    result = eval(cmd + value)
                except:
                    print("conjuction error: something went wrong")
                clause_truth_table.append(np.any(result))

            # variable: always evaluates true and initializes the cur_eval dict
            elif len(value) == 1 and value.islower():
                wme_vars[value] = wme[attribute]
                clause_truth_table.append(True)

            # atom: true if value in wme equivalent to value in clause
            else:
                if wme[attribute] == value:
                    clause_truth_table.append(True)
                else:
                    clause_truth_table.append(False)

        if clause_truth_table:
            temp_wmes_truth_table.append(np.all(clause_truth_table))
        if debug:
            print('WME ' + str(n_wme))
            print(dict(zip(list(_clause.keys()), clause_truth_table)))
            print(temp_wmes_truth_table)
            print(wme_vars)
            
        temp_wmes_vars.append(wme_vars)

    return temp_wmes_vars, temp_wmes_truth_table

def resolve_conflicts(_match, policy='order'):
    if policy == 'order':
        n = 0
        try:
            while not _match[n] and n <= len(_match): n+=1
            return n, _match[n]
        except:
            return []
    elif policy == 'specific':
        pass
    elif policy == 'recent':
        agenda.append(_match)
        print(match)
        pass
    elif policy == 'refractor':
        pass

def apply_action(_n_rule, _n_wmes, _rule_vars, _wm, _antecedents, _consequences):
    # get variables from antecedents
    antecedent = _antecedents[_n_rule]
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

def test_loop(rule_text='/home/cilsat/dev/rpp/prodsys/days-rules', fact_text='/home/cilsat/dev/rpp/prodsys/days-memory', debug=True):
    wms = []
    a, c = parse_rules(open(rule_text).read())
    wm = parse_facts(open(fact_text).read())
    wms.append(wm)
    m, v = match(wm, a, debug=debug)
    #m, v = match(wm, a, debug=True)
    n = 1
    chosen = resolve_conflicts(m)
    while chosen:
        temp_wm = apply_action(chosen[0], chosen[1], v, wm, a, c)
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
        n+=1

    print('Program terminated')
    return wms

