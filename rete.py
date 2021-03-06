#!/usr/bin/pythonn

import numpy as np
import pandas as pd

import retenode as rn

import re
import string

from collections import OrderedDict
import itertools as iter
from IPython.display import display, HTML

# reserved keywords and characters
conditional = ['if', 'then', 'IF', 'THEN']
action = ['add', 'remove', 'modify']
operators = '<>!=&|%'
conjuctions = ['<', '>', '<=', '>=', '!=', '==']

class Rete():
    """
    Initialize all class attributes: read this as a sort of Contents
    """
    def __init__(self, rules=None, facts=None, policy='refractor', debug=None):
        # user-facing attributes
        self.policy = policy    # options are 'order', 'recent_first', 'recent_last',
                                # 'specific', and 'refractor'.

        self.dbg = debug        # options are 'cli' and 'web'. choose 'web' if running
                                # on ipython/jupyter notebook.

        # internal attributes/structures
        # top level/main loop
        self.conditions = None  # pandas dataframe (henceforth 'table') containing 
                                # antecedents/conditions of all rules.

        self.actions = None     # list of tables of actions of each rule.

        self.wm = None          # table representing the working memory (WM), 
                                # containing all current working memoty elements.

        self.net = None         # dictionary that contains all alpha, beta, and
                                # termination nodes. the first element (-1) is always 
                                # the root node.
        self.alpha_nodes = []   # a convenience list of only the alpha nodes.
        self.beta_nodes = []    # a convenience list of only the neta nodes.
        self.rule_nodes = []    # a convenience list of only the rule nodes.

        # policy attributes
        self.saved_memory = None    # chose rule-wme buffer/memory. checked each
                                # iteration to detect infinite loops.
        self.threshold = 10     # chosen rule-wme buffer/memory size.

        self.refractor_table = None # table that stores instances of previously
                                # triggered rule-wme pairs. initialized in main loop.

        self.specific_table = None  # table that stores information of how specific
                                # a rule is. initialized while building network.

        # if the rules and facts are already specified, let's get the party started!
        if rules and facts:
            # parse rules to obtain conditions to match and actions to perform
            conditions, actions, map, self.wm = self.parse(rules, facts)
            if self.dbg == 'cli':
                print('conditions:')
                print(conditions)
                print('\nrule-condition map:'),
                print(map)
                print('facts:')
                print(self.wm)
            if self.dbg == 'web':
                print('Conditions:')
                display(conditions)
                print('\nRule-Condition Map:'),
                print(map)
                print('\nFacts:')
                display(self.wm)

            # build rete alpha and beta node network from conditions
            self.net = self.init_net(conditions, actions, map)

            # start main loop: match, choose, and apply till WM is exhausted or 
            # conflict resolution stop condition is met
            self.main_loop()


    """
    Opens specified files as rules and facts, respectively.
    Parses file and generates a table of conditionals and list of actions, a list of 
    rule-conditionals mappings, and table of initial Working Memory Elements.
    """
    def parse(self, _rules, _facts):

        # local function to parse strings into dictionaries
        def str_to_dict(_str, _sender="unspecified"):
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

        # read files
        _rules = open(_rules).read()
        _facts = open(_facts).read()

        # all conditions/actions and their respective attributes
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

            temp_cond_map = []
            # convert plaintext conditions into dictionaries
            for cond in conditions_raw:
                attvals, keys = str_to_dict(cond, 'condition')
                conditions.append(attvals)
                [cond_cols.append(key) for key in keys if key not in cond_cols]
                temp_cond_map.append(n_cond)
                n_cond += 1

            rule_condition_map.append(temp_cond_map)

            temp_act_map = []
            # convert plaintext actions into dictionaries
            for act in actions_raw:
                attvals, keys = str_to_dict(act, 'action')
                [act_cols.append(key) for key in keys if key not in act_cols]
                temp_act_map.append(attvals)

            actions.append(pd.DataFrame(temp_act_map, columns=act_cols))

        conditions = pd.DataFrame(conditions, columns=cond_cols)

        # all initial WMEs and their attribute names
        wmes = []
        fact_cols = []
        for wme in filter(None, _facts.split('\n')):
            wme_dict, keys = str_to_dict(wme, 'condition')
            [fact_cols.append(key) for key in keys if key not in fact_cols]
            wmes.append(wme_dict)
        wm = pd.DataFrame(wmes, columns=fact_cols)

        return conditions, actions, rule_condition_map, wm


    """
    Builds the RETE network from a table of conditions, actions, and rule-condition mappings:
        1. Initialize an alpha node for each UNIQUE condition.
        2. Initialize root node and point to ALL alpha nodes.
        3. Initialize a beta node for each UNIQUE alpha-alpha OR alpha-beta PAIR in the rule
           condition mapping.
        4. Initialize a termination node for each rule in the rule-condition mapping. Bind relevant
           action to this termination/rule node.
    """
    def init_net(self, _conditions, _actions, _map):

        # build specificity table
        scores = [0 for _ in range(len(_map))]
        for n_rule, rule in enumerate(_map):
            for n in rule:
                scores[n_rule] += len(_conditions.loc[n].dropna().keys())

        self.specific_table = np.argsort(scores)[::-1]

        # build a ditionary mapping duplicated nodes to its first occurrence
        equiv_table = {}
        for n_node in _conditions.index:
            node = _conditions.loc[n_node]
            for n_inner in _conditions.index[n_node+1:]:
                inner = _conditions.loc[n_inner]
                if node.equals(inner) and n_inner not in equiv_table.keys():
                    equiv_table[n_inner] = n_node

        # drop duplicate nodes from table
        alpha_patterns = _conditions.drop_duplicates()
        alpha_nodes = list(set(alpha_patterns.index))

        # update alpha network: replace duplicate nodes with their first occurrence
        for n_rule, rule in enumerate(_map):
            _map[n_rule] = [equiv_table[n] if n in equiv_table.keys() else n for n in rule]
        if self.dbg == 'cli':
            print('\nrule-alpha map:'),
            print(_map)

        # build beta network
        prev_nodes = []
        rule_nodes = []
        beta_offset = max(alpha_nodes) + 1
        for n_rule, rule in enumerate(_map):
            beta_rule = rule[:]
            while True:
                if len(beta_rule) == 1: 
                    if beta_rule not in prev_nodes: prev_nodes.append(beta_rule)
                    break
                else:
                    sub = beta_rule[:2]
                    if sub not in prev_nodes:
                        prev_nodes.append(sub)
                    idx = prev_nodes.index(sub) + beta_offset
                    if self.dbg == 'init_net':
                        print("sub:"),
                        print(sub),
                        print("beta:"),
                        print(beta_rule),
                        print("idx:"),
                        print(idx)
                    if len(beta_rule) == 2:
                        beta_rule = [idx]
                    else:
                        beta_rule = [idx] + beta_rule[2:]

            rule_nodes.append(beta_rule)

        rete_nodes = dict(zip(alpha_nodes, [[-1]]*len(alpha_nodes)))
        for n_node, node in enumerate(prev_nodes):
            rete_nodes[n_node + beta_offset] = node
        if self.dbg == 'init_net':
            print(_map)
            print(prev_nodes)
            print(rule_nodes)
            print(rete_nodes)

        # initialize rete network (as dictionary) and populate with nodes
        rete_net = {}
        # create root node
        root = rn.ReteNode(-1, 'root', None, [], _function=rn.ReteNode.root_match)
        # push root node into rete net
        rete_net[-1] = root
        # create other nodes
        for node_id, prev in rete_nodes.iteritems():
            # alpha node connected to root
            if len(prev) == 1 and prev[0] == -1:
                node = rn.ReteNode(node_id, 'alpha', prev, [], _pattern=_conditions.loc[node_id].dropna(), _function=rn.ReteNode.alpha_match)
                self.alpha_nodes.append(node_id)
            # rule node
            elif len(prev) == 1 and prev[0] != -1:
                node = rn.ReteNode(node_id, 'rule', prev, None, _function=rn.ReteNode.alpha_match)
                self.rule_nodes.append(node_id)
            # beta node
            else:
                node = rn.ReteNode(node_id, 'beta', prev, [], _function=rn.ReteNode.beta_match)

                # set depth of beta node
                depth = 0
                if node.prev[0] in self.beta_nodes:
                    while True:
                        try:
                            depth += 1
                            node.left[depth]
                        except:
                            break
                node.depth = depth

                self.beta_nodes.append(node_id)

            # insert into our dictionary of nodes
            rete_net[node_id] = node
            # generate successor nodes
            for p in prev:
                try:
                    rete_net[p].next.append(node_id)
                except:
                    print("attempting to add successor to nonexistant or rule node")
                    raise SystemExit

        if self.dbg == 'init_rete':
            for key, val in rete_net.iteritems():
                val.print_node()
        return rete_net


    """
    Utilizes the alpha/beta network compiled in the init_rete step. Essentialy does:
        1. MATCH WMEs through the net to obtain Rule:WME(s) pairs
        2. CHOOSE ONE pair from a possible set of matches
        3. APPLY actions from the chosen pair
        4. TERMINATE when WM is exhausted or when conflict resolution condition met
    """
    def main_loop(self):

        # initialize policy attributes
        self.saved_memory = [{'n_rule':[None], 'rule':None}]*self.threshold
        self.refractor_table = [[] for _ in range(len(self.rule_nodes))]

        # initialize change tokens
        tokens = {}
        for wme in self.wm.index:
            tokens[wme] = 'add'

        n_iter = 0
        while True:
            # start the matching process
            conflict_set = self.match(tokens)
            break

            # choose a rule-wme pair from conflict set
            # if no rules are chosen, terminate
            try:
                chosen = self.resolve_conflicts(conflict_set)
            except:
                print('process terminating')
                break

            # apply actions from chosen rule-wme pair
            tokens = self.apply_action(chosen)


    """
    Reads a dictionary of change tokens to determine which WMEs to attempt to match.
    Initially, the entire WM is pushed inside and the node memories built.
    """
    def match(self, _tokens):

        matches = []
        alpha_next = []
        # apply tokens to all alpha nodes first
        for n_wme, action in _tokens.iteritems():
            wme = self.wm.loc[n_wme]

            # apply tokens to root node
            root_next = self.net[-1].apply_token(wme, action)

            # apply tokens to alpha nodes
            for node in root_next:
                node_matches = self.net[node].apply_token(wme, action)
                if len(node_matches) == 1 and node_matches[0] in self.rule_nodes:
                    continue
                alpha_next.extend(node_matches)

        # revese alpha next so that we pop the first element in the list instead
        alpha_next = sorted(set(alpha_next))[::-1]
        print('alpha next:'),
        print(alpha_next)
        
        # apply tokens to beta nodes
        for n_wme, action in _tokens.iteritems():
            while alpha_next:
                node = self.net[alpha_next.pop()]

                # set the left and right sides of the beta node
                beta_prev = node.prev
                node.left = self.net[beta_prev[0]].memory
                node.right = self.net[beta_prev[1]].memory
                
                # check if left and right hand sides are of the same type
                if self.net[beta_prev[0]].type == 'alpha':
                    diff_type = self.net[beta_prev[0]].pattern['type'] != self.net[beta_prev[1]].pattern['type']
                else:
                    diff_type = self.net[self.net[beta_prev[0]].prev[1]].pattern['type'] != self.net[beta_prev[1]].pattern['type']
                node.diff_type = diff_type

                # apply tokens
                try: alpha_next.extend(node.apply_token(wme, action))
                except:
                    if self.dbg == 'match': print(node)
                    continue

        if self.dbg == 'cli':
            print(self.beta_nodes)
            for node in self.beta_nodes: self.net[node].print_node()


        """
        try:
            an = self.alpha_nodes.copy()
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
        self.alpha_memory = dict(zip(self.alpha_nodes.index, am))

        # beta matching: generate beta memory iteratively for each beta node
        # TODO modify for use with rete network rather than alpha map
        self.beta_memory = []
        rules_matched = []
        for rule in self.alpha_net:
            rule_matches = []
            # check if rule has multiple conditions: if not, just pass the alpha
            bm = self.alpha_memory[rule[0]].reset_index().rename(columns={'index':'0'})
            if len(rule) > 1:
                node_type = self.alpha_nodes.loc[rule[0], 'type']
                for n in range(1, len(rule)):
                    # determine whether we need to append or concat on node
                    diff_type = False
                    curr_type = self.alpha_nodes.loc[rule[n], 'type']
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
            rule_depth = range(len(self.alpha_net[nrule]))
            partial_matches = []
            for n in rule.index:
                try:
                    wme_set = [rule.loc[n, str(dep)] for dep in rule_depth]
                    partial_matches.append(wme_set)
                except:
                    partial_matches.append([])
            matches.append(partial_matches)
        self.matches = matches
        """

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

    def resolve_conflicts(self, _matches, _policy='refractor'):

        if self.dbg == 'cli':
            print('')
            print('conflict set -> chosen (rule:[wme])')
        if self.dbg == 'web':
            print('')
            print('Conflict Set:'),
        all_rules = []
        for n_rule, rule in enumerate( _matches):
            for wme in rule:
                all_rules.append({'rule':n_rule, 'wme':wme})
                print(str(n_rule) + ':' + str(wme) + ','),
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

        elif _policy == 'most_recent' or _policy == 'least_recent':
            sm = list(reversed(self.saved_memory))
            rules_used = set([r['rule'] for r in all_rules])
            last_used = [None for _ in range(len(rules_used))]

            for n_rule, rule in enumerate(rules_used):
                for n_s_rule, s_rule in enumerate(sm, 1):
                    if rule == s_rule['rule']:
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
            # choose first rule in specific_table
            chosen = [rule for ns in self.specific_table for n, rule in enumerate(all_rules) if ns == n]
            print('order:'),
            print(self.specific_table)
            print('specific:'),
            print(chosen)
            chosen = chosen[0]

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
            raise SystemExit

        if self.dbg == 'cli':
            print(' -> ' + str(chosen['rule']) + ':' + str(chosen['wme']))
        if self.dbg == 'web':
            print('Chosen Rule/WME:'),
            display(self.alpha_nodes.loc[self.alpha_net[chosen['rule']]].dropna(axis=1, how='all')),
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
        chosen_vars = [chosen_memory.loc[chosen_memory[str(n)] == n_wme[n]] for n in range(len(n_wme))]
        try:
            pd.concat(chosen_vars).drop_duplicates(keep=False).empty
            chosen_vars = chosen_vars[0]
        except:
            print("something's wrong here")
            raise SystemExit
            
        # rule conditions: we don't have a direct mapping of rule->conditions, so we go through alpha_net
        conditions = self.alpha_nodes.loc[self.alpha_net[n_rule]]
        # the action itself
        actions = self.actions[n_rule]

        # iterate through the actions
        for n_act in actions.index:
            # drop nan values so that we only modify relevant attributes
            action_node = actions.loc[n_act].dropna()
            action_name = action_node['action']        

            if action_name == 'remove':
                # drop the WME specified in the 'on' attribute corresponding to the WME specified in the chosen 'wme' field 
                self.wm = self.wm.drop(n_wme[int(action_node['on']) - 1])

            elif action_name == 'add':
                # acquire values to add
                values = action_node.drop({'action'})
                new_values = self.parse_values(values, chosen_vars)
                df = dict(zip(values.keys(), new_values))

                # insert new WME at the end of the table and make sure the columns are available
                target_idx = self.wm_index
                for key, val in df.iteritems():
                    self.wm.loc[target_idx, key] = val
                self.wm_index += 1

            elif action_name == 'modify':
                wme = self.wm.loc[n_wme[int(action_node['on'])-1]]
                values = action_node.drop({'action', 'on'}).to_dict()
                new_values = self.parse_values(values, chosen_vars)
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
                    new_val = _vars[var].values[0]
                    args = args.replace(var, new_val)
                result = eval(args)
                out_values.append(str(result))

            # variables
            elif len(value) == 1 and value.islower():
                new_val = _vars[value].values[0]
                out_values.append(new_val)

            # atom
            else:
                out_values.append(str(value))
        
        return out_values

