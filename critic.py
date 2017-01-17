#!/usr/bin/env python3

from pdb import set_trace

from argparse import ArgumentParser
from ast import parse, NodeVisitor
from collections import namedtuple
from os.path import exists as file_exists

OPERATORS = {
    'and':'and',
    'or':'or',
    'not':'not',
    'is':'is',
    'isnot':'is not',
    'eq':'==',
    'noteq':'!=',
    'lt':'<',
    'lte':'<=',
    'gt':'>',
    'gte':'>=',
    'add':'+',
    'sub':'-',
    'mult':'*',
    'div':'/',
    'mod':'%',
    'pow':'**',
}

PATTERNS = []

Critique = namedtuple('Critique', ['line', 'col', 'message'])

def register_pattern(cls):
    PATTERNS.append(cls)

def critique_code(code):
    critiques = []
    for pattern in PATTERNS:
        critic = pattern()
        critic.critique(code)
        critiques.extend(critic.critiques)
    for critique in critiques:
        print('{}:{}: {}'.format(critique.line, critique.col, critique.message))

def node_type(node):
    return type(node).__name__

def unparse_operator(node):
    return OPERATORS[node_type(node).lower()]

def is_name_constant(node, value):
    return node_type(node) == 'NameConstant' and node.value is value

class CritiquePattern(NodeVisitor):
    def __init__(self):
        super().__init__()
        self.source = ""
        self.critiques = []
    def reset(self):
        self.source = ""
        self.critiques = []
    def critique(self, code):
        self.reset()
        self.source = code
        ast = parse(code)
        self.visit(ast)
    def add_critique(self, node, message):
        self.critiques.append(Critique(node.lineno, node.col_offset, message))

@register_pattern
class NeedlessBoolOp(CritiquePattern):
    def visit_BoolOp(self, node):
        op = unparse_operator(node.op)
        for i, value in enumerate(node.values):
            if (op == 'and' and is_name_constant(value, True)) or (op == 'or' and is_name_constant(value, False)):
                if i == 0:
                    fragment = '{} {}'.format(value.value, op)
                else:
                    fragment = '{} {}'.format(op, value.value)
                self.add_critique(node, '`{}` is pointless and should be omitted'.format(fragment))

@register_pattern
class AndFalse(CritiquePattern):
    def visit_BoolOp(self, node):
        op = unparse_operator(node.op)
        for i, value in enumerate(node.values):
            if op == 'and' and is_name_constant(value, False):
                if i == 0:
                    fragment = '{} {}'.format(value.value, op)
                else:
                    fragment = '{} {}'.format(op, value.value)
                self.add_critique(node, '`{}` makes the entire Boolean expression false'.format(fragment))

@register_pattern
class OrTrue(CritiquePattern):
    def visit_BoolOp(self, node):
        op = unparse_operator(node.op)
        for i, value in enumerate(node.values):
            if op == 'or' and is_name_constant(value, True):
                if i == 0:
                    fragment = '{} {}'.format(value.value, op)
                else:
                    fragment = '{} {}'.format(op, value.value)
                self.add_critique(node, '`{}` makes the entire Boolean expression true'.format(fragment))

@register_pattern
class EqualNone(CritiquePattern):
    def visit_Compare(self, node):
        for op, comparator in zip(node.ops, node.comparators):
            if self.visit(comparator) and is_name_constant(comparator, None):
                op = unparse_operator(op)
                if op == '==':
                    self.add_critique(node, '`== None` should be converted to `is None`')
                elif op == '!=':
                    self.add_critique(node, '`!= None` should be converted to `is not None`')

@register_pattern
class EqualBoolean(CritiquePattern):
    def visit_Compare(self, node):
        for op, comparator in zip(node.ops, node.comparators):
            op = unparse_operator(op)
            if is_name_constant(comparator, True):
                if op == '==':
                    self.add_critique(node, '`== True` is pointless and should be omitted')
                elif op == '!=':
                    self.add_critique(node, '`!= True` should be converted to a `not`')
            elif is_name_constant(comparator, False):
                if op == '==':
                    self.add_critique(node, '`== False` should be converted to a `not`')
                elif op == '!=':
                    self.add_critique(node, '`!= False` is pointless and should be omitted')

@register_pattern
class MixedComparisons(CritiquePattern):
    def visit_Compare(self, node):
        ops = set(unparse_operator(op) for op in node.ops)
        if len(ops) == 1:
            return
        elif ops == set(['==', '!=']):
            return
        elif ops == set(['<', '<=']):
            return
        elif ops == set(['>', '>=']):
            return
        else:
            ops_list = ', '.join('`{}`'.format(op) for op in ops)
            self.add_critique(node, 'mixing comparisons ({}) is confusing; use `and` instead'.format(ops_list))

@register_pattern
class ReturnBoolean(CritiquePattern):
    '''
    if a:
        return True
    else:
        return False
    '''
    pass


@register_pattern
class VariableLift(CritiquePattern):
    '''
    for i in range(10):
        q = 10
    '''
    pass

def main():
    arg_parser = ArgumentParser()
    arg_parser.add_argument('code_or_file')
    args = arg_parser.parse_args()
    if file_exists(args.code_or_file):
        with open(args.code_or_file) as fd:
            code = fd.read()
    else:
        code = args.code_or_file
    critique_code(code)

if __name__ == '__main__':
    main()
