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
    # the list of unique attributes will be used to build our WM table
    attributes = []
    # for each production rule
    for pr in filter(None, _rules.split('\n')):
        # split into antecedent and consequence, assumed to be separated by 'then' keyword
        ante, cons = pr.split(conditional[1])
        # separate antecedent/consequence into their separate clauses by brackets
        ante_clauses = re.findall(r'\((.*?)\)', ante)
        cons_clauses = re.findall(r'\((.*?)\)', cons)

        # a first run to collect our types, attributes, and specs for WM
        # atecedents and consequences are collected but not parsed
        antecedent = []
        for clause in ante_clauses:
            # deal with negation
            negation = True if clause.startswith('~') else False
            clause = clause.replace('~ ', '')

            # parse attributes/specifications by clause
            atts = []
            specs = []
            for att_spec in clause.split():
                att, spec = att_spec.split(':')
                atts.append(att)
                specs.append(spec)

            attributes.append(atts)
            antecedent.append([negation, dict(zip(atts, specs))])

        antecedents.append(antecedent)

        """
        consequence = []
        for clause in cons_clauses:
            # parse attributes/specifications by clause
            atts = []
            specs = []
            for att_spec in clause.split():
                att, spec = att_spec.split(':')
                atts.append(att)
                specs.append(spec)

            attributes.append(atts)
            consequence.append([negation, dict(zip(atts, specs))])

        consequences.append(consequence)
        """

    # build wm table from gathered types/attributes
    cols = list(set(chain.from_iterable(attributes)))
    wm = pd.DataFrame(columns=cols)

    return antecedents, wm

def parse_mem(_mem, _tables):

    for wme in filter(None, _mem.split('\n')):
        wme_vals = {}
        wme = wme.translate(None, '()')

        for att_val in wme.split():
            att, val = att_val.split(':')
            # if attribute does not appear in rules, we can safely ignore it
            try:
                _tables[att]
                wme_vals[att] = [val]
            except:
                print('attribute ' + att + ' unused')

        _tables = _tables.append(pd.DataFrame(wme_vals), ignore_index=True)
    return _tables

"""
this basically works on a multi-level truth table / tree with:
    - rules
    - clauses
    - attributes
working memory elements are matched 
"""
def match_antecedents(_antecedents, _wm_table, debug=True):

    # store all wme matches
    master_truth_table = []    
    # match rules in sequence
    n_rule = 1
    for rule in _antecedents:

        # figure out number of clauses and evaluate individually against each wme
        # build a rule truth table: >= 1 wme needs to match
        rule_truth_table = []
        for i in range(len(_wm_table.index)):
            # current working memory element is the particular row in the table
            wme = _wm_table.iloc[i]
            if debug: print('WME ' + str(i+1) + ': ' + wme['type'])

            # build a truth table for the current wme: ALL clauses must match
            # test wme against each clause of the antecedent
            wme_truth_table = []
            cur_eval = {}
            for clause in rule:
                #print(cur_eval)
                negation, attributes_values = clause

                # build a clause truth table: ALL attribute tests must pass
                clause_truth_table = []
                # match the types
                for attribute in attributes_values:
                    value = attributes_values[attribute]

                    # expression
                    if value.startswith('{'):
                        if not cur_eval:
                            print("expression: no variables set")
                            break
                        args = value.translate(None, '{}')
                        args = args.replace('&', ' and ').replace('|', ' or ')
                        vars = re.findall(r'[a-z]+', args)
                        # starts with a var or atom: evaluate as per usual
                        if args[0] not in operators:
                            try:
                                for var in vars:
                                    args = args.replace(var, cur_eval[var])
                                result = eval(args)
                                clause_truth_table.append(np.any(result))
                            except:
                                print("expression: variable not found")
                        # starts with an operator: evaluate for entire WM
                        else:
                            try:
                                cmd = "_wm_table['" + attribute + "'].values.astype(float)"
                                for var in vars:
                                    args = args.replace(var, cur_eval[var])
                                result = eval(cmd + args)
                                #print(result)
                                clause_truth_table.append(np.any(result))
                            except:
                                print("expression op in front: variable not found")

                    # evaluation
                    elif value.startswith('['):
                        if not cur_eval:
                            print("expression: no variables set")
                            break
                        args = value.translate(None, '[]')
                        vars = re.findall(r'[a-z]+', args)
                        # starts with a var or atom: evaluate as per usual
                        try:
                            for var in vars:
                                args = args.replace(var, cur_eval[var])
                            result = eval(args)
                            clause_truth_table.append(np.any(result))
                        except:
                            print("expression: variable not found")

                    # variable: always evaluates true and initializes the cur_eval dict
                    elif len(value) == 1 and value.islower():
                        cur_eval[value] = wme[attribute]
                        clause_truth_table.append(True)

                    # atom: true if value in wme equivalent to value in clause
                    else:
                        if wme[attribute] == value:
                            clause_truth_table.append(True)
                        else:
                            clause_truth_table.append(False)

                if debug:
                    print("Clause Truth Table: ")
                    print(clause_truth_table)
                if clause_truth_table:
                    # this is where we evaluate the negation of the clause:
                    wme_truth_table.append(negation != np.all(clause_truth_table))
                else:
                    wme_truth_table.append(False)

            if debug:
                print("WME " + str(i+1) + " Truth Table:")
                print(wme_truth_table)
                print('')
            if wme_truth_table:
                rule_truth_table.append(np.all(wme_truth_table))
            else:
                rule_truth_table.append(False)

        matches = np.argwhere(rule_truth_table).reshape(-1)
        if matches:
            master_truth_table.append(matches)
        #if debug:
        print("Rule Truth Table:")
        print(rule_truth_table)
        for wme in matches:
            print("WME " + str(wme+1) + " matches Rule " + str(n_rule) + "!")
        print('')

        n_rule += 1

    if master_truth_table:
        master_truth_table = np.vstack(master_truth_table).reshape(-1)
        return _wm_table.iloc[master_truth_table]
    else:
        return

def resolve_conflicts(_agenda, policy='dfs'):
    pass

