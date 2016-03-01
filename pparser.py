#!/usr/bin/pythonn

import pandas as pd
import re
import string
import numpy as np
from itertools import chain

# names reserved for use by the system
conditional = ['if', 'then']
action = ['add', 'remove', 'modify']
operators = '<>!=&|%'

def parse_rules(_rules):
    # antecedents/consequences to be parsed during pattern matching/action
    antecedents = []
    consequences = []

    # for each production rule
    for pr in [r for r in _rules.split('\n') if r]:
        # split into antecedent and consequence, assumed to be separated by 'then' keyword
        ante, cons = pr.split(conditional[1])
        # separate antecedent/consequence into their separate clauses by brackets
        ante_clauses = re.findall(r'\((.*?)\)', ante)
        cons_clauses = re.findall(r'\((.*?)\)', cons)

        # a first run to collect our types, attributes, and specs for WM
        # atecedents and consequences are collected but not parsed
        antecedent = []
        for clause in ante_clauses:
            atts = []
            specs = []

            # deal with negation
            negation = True if clause.startswith('~') else False
            clause = clause.replace('~ ', '')
            atts.append('negation')
            specs.append(negation)

            # parse attributes/specifications by clause
            for att_spec in clause.split():
                att, spec = att_spec.split(':')
                atts.append(att)
                specs.append(spec)

            antecedent.append(dict(zip(atts, specs)))

        antecedents.append(antecedent)

        consequence = []
        for clause in cons_clauses:
            # parse attributes/specifications by clause
            atts = []
            specs = []
            for att_spec in clause.split():
                att, spec = att_spec.split(':')
                atts.append(att)
                specs.append(spec)

            consequence.append(dict(zip(atts, specs)))

        consequences.append(consequence)

    # build antecedents table for each rule
    rule_antecedents = []
    for rule in antecedents:
        rule_df = pd.DataFrame([clause for clause in rule], index=range(len(rule)))
        rule_antecedents.append(rule_df)

    # build antecedents table for each rule
    rule_consequences = []
    for rule in consequences:
        rule_df = pd.DataFrame([clause for clause in rule], index=range(len(rule)))
        rule_consequences.append(rule_df)

    return rule_antecedents, rule_consequences

def parse_facts(_facts):

    wm = pd.DataFrame()
    for wme in filter(None, _facts.split('\n')):
        wme_vals = {}
        wme = wme.translate(None, '()')

        for att_val in wme.split():
            att, val = att_val.split(':')
            try:
                wme_vals[att] = [val]
            except:
                print(att_val)

        wm = wm.append(pd.DataFrame(wme_vals), ignore_index=True)

    return wm

"""
this basically works on a multi-level truth table / tree with:
    - rules
    - clauses
    - attributes
working memory elements are matched 
"""
def match(_wm, _antecedents, _consequences, debug=True):

    # store all wme matches
    master_truth_table = []    
    # match rules in sequence
    for n_rule in range(len(_antecedents)):
        antecedent = _antecedents[n_rule]
        consequence = _consequences[n_rule]

        if debug:
            print('')
            print('RULE ' + str(n_rule))
        rule_truth_table = []

        # persist WME variables across clauses
        wmes_vars = [{}]*len(_wm.index)
        wmes_truth_table = []

        # for clauses in the rule
        for n_clause in range(len(antecedent.index)):
            clause = antecedent.iloc[n_clause]

            # get only wmes that match clause type
            #wmes = _wm.loc[_wm['type'] == clause['type']]
            wmes = _wm

            #clause_drop = clause.drop({'negation', 'type'}).dropna()
            clause_drop = clause.drop({'negation'}).dropna()

            if debug:
                print('')
                print('CLAUSE ' + str(n_clause))
                print('Negation: ' + str(clause['negation']))
                print(clause_drop)

            if not wmes.empty:
                wmes_vars, temp_wmes_truth_table = clause_match(clause_drop, wmes, wmes_vars)
                # check for negation and append
                wmes_truth_table.append(clause['negation'] != temp_wmes_truth_table)

        #wmes_truth_table = np.vstack(wmes_truth_table)
        print(wmes_truth_table)

        if np.all(rule_truth_table):
            for n_clause in range(len(consequence.index)):
                clause = consequence.iloc[n_clause]


def clause_match(_clause, _wmes, _wmes_vars):

    temp_wmes_vars = []
    temp_wmes_truth_table = []
    for n_wme in range(len(_wmes.index)):
        wme = _wmes.iloc[n_wme]
        wme_vars = _wmes_vars[n_wme].copy()
        #wme_truth_table = temp_wmes_truth_table[n_wme]

        clause_truth_table = []
        # check each attribute except 'negation'
        if _clause['type'] != wme['type']:
            clause_truth_table.append(np.NaN)
        else:
            for attribute in _clause.index:
                value = str(_clause[attribute])
                # expression
                if value.startswith('{'):
                    if not wme_vars:
                        print("expression: no variables set")
                        break
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
                        try:
                            cmd = "_wmes['" + attribute + "'].values.astype(float)"
                            for var in vars:
                                args = args.replace(var, wme_vars[var])
                            result = eval(cmd + args)
                            clause_truth_table.append(np.any(result))
                        except:
                            print("expression op in front: variable not found")
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

        print('WME ' + str(n_wme))
        temp_wmes_truth_table.append(np.all(clause_truth_table))
        print(list(_clause.keys()))
        print(clause_truth_table)
        temp_wmes_vars.append(wme_vars)

    return temp_wmes_vars, temp_wmes_truth_table

def resolve_conflicts(_agenda, policy='dfs'):
    pass

