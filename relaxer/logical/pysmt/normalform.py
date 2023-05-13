from typing import FrozenSet
import pysmt.fnode
import pysmt.operators
import pysmt.oracles
import pysmt.shortcuts
import pysmt.walkers


class NNFTransformer(pysmt.walkers.DagWalker):
    def __init__(self) -> None:
        super().__init__()
        self._atoms = set()
        self._is_in_normal_form = False
        self._runs = 0

    @property
    def _manager(self):
        return self.env.formula_manager

    @property
    def runs(self) -> int:
        return self.runs

    def transform(self, formula: pysmt.fnode.FNode) -> pysmt.fnode.FNode:
        self._atoms = pysmt.shortcuts.get_atoms(formula)
        self._is_in_normal_form = False

        self._runs = 0
        out_formula = formula
        while not self._is_in_normal_form:
            self._is_in_normal_form = True
            out_formula = self.walk(out_formula)
            self._runs += 1

        assert pysmt.shortcuts.is_valid(pysmt.shortcuts.Iff(out_formula, formula))

        return out_formula

    def walk_and(self, formula, args, **kwargs):
        conjuncts = []

        literal_sets = set(
            (
                frozenset(clause.args()) if clause.is_or() else frozenset([clause])
                for clause in args
            )
        )

        for arg in set(args):
            if arg.is_and():
                for nested_arg in arg.args():
                    conjuncts.append(nested_arg)
                continue

            if arg.is_or():
                literal_set = frozenset(arg.args())
                absorpted = False
                for other_literal_set in literal_sets:
                    if literal_set == other_literal_set:
                        continue
                    if literal_set.issuperset(other_literal_set):
                        absorpted = True
                        break

                if absorpted:
                    continue

            if arg.is_not():
                negated = arg.arg(0)
                if negated in args:
                    # contradiction
                    return self._manager.FALSE()

            if arg.is_false():
                # contradiction
                return self._manager.FALSE()

            if arg.is_true():
                # identity
                continue

            conjuncts.append(arg)

        if len(conjuncts) == 0:
            return self._manager.TRUE()

        return self._manager.And(conjuncts)

    def walk_or(self, formula, args, **kwargs):
        disjuncts = []

        literal_sets = set(
            (
                frozenset(term.args()) if term.is_and() else frozenset([term])
                for term in args
            )
        )

        for arg in set(args):
            if arg.is_or():
                for nested_arg in arg.args():
                    disjuncts.append(nested_arg)
                continue

            if arg.is_and():
                literal_set = frozenset(arg.args())
                absorpted = False
                for other_literal_set in literal_sets:
                    if literal_set == other_literal_set:
                        continue
                    if literal_set.issuperset(other_literal_set):
                        absorpted = True
                        break

                if absorpted:
                    continue

            if arg.is_not():
                negated = arg.arg(0)
                if negated in args:
                    # tautology
                    return self._manager.TRUE()

            if arg.is_true():
                return self._manager.TRUE()

            if arg.is_false():
                # identity
                continue

            disjuncts.append(arg)

        if len(disjuncts) == 0:
            return self._manager.TRUE()

        return self._manager.Or(disjuncts)

    def walk_not(self, formula, args, **kwargs):
        assert len(args) == 1
        arg = args[0]
        if arg in self._atoms:
            return self._manager.Not(arg)

        self._is_in_normal_form = False

        if arg.is_false():
            return self._manager.TRUE()

        if arg.is_true():
            return self._manager.FALSE()

        if arg.is_not():
            return arg.arg(0)

        if arg.is_and():
            disjuncts = set()
            for conjunct in arg.args():
                if conjunct.is_not():
                    assert len(conjunct.args()) == 1
                    disjuncts.add(conjunct.arg(0))

                disjuncts.add(self._manager.Not(conjunct))
            return self._manager.Or(disjuncts)

        assert arg.is_or()

        conjuncts = set()
        for disjunct in arg.args():
            if disjunct.is_not():
                assert len(disjunct.args()) == 1
                conjuncts.add(disjunct.arg(0))

            conjuncts.add(self._manager.Not(disjunct))
        return self._manager.And(conjuncts)

    @pysmt.walkers.handles(
        set(pysmt.operators.ALL_TYPES)
        - {pysmt.operators.NOT, pysmt.operators.OR, pysmt.operators.AND}
    )
    def walk_identity(self, formula, **kwargs):
        return formula


class CNFTransformer(NNFTransformer):
    def __init__(self) -> None:
        super().__init__()

    def walk_and(self, formula, args, **kwargs):
        transformed = super().walk_and(formula, args, **kwargs)
        for arg in transformed.args():
            if arg.is_and():
                # contains nested conjunction
                self._is_in_normal_form = False
                break

        return transformed

    def walk_or(self, formula, args, **kwargs):
        preprocessed = super().walk_or(formula, args, **kwargs)

        if not preprocessed.is_or():
            return preprocessed

        # push disjunctions "back"
        nested_conjunction = None
        disjuncts = set()
        for arg in preprocessed.args():
            if arg.is_and():
                nested_conjunction = arg
            disjuncts.add(arg)

        if nested_conjunction is not None:
            self._is_in_normal_form = False
            conjuncts = set()
            for arg in nested_conjunction.args():
                conjuncts.add(
                    self._manager.Or(
                        disjuncts.difference({nested_conjunction}).union({arg})
                    )
                )

            return self._manager.And(conjuncts)

        return preprocessed


class DNFTransformer(NNFTransformer):
    def __init__(self) -> None:
        super().__init__()

    def walk_or(self, formula, args, **kwargs):
        transformed = super().walk_or(formula, args, **kwargs)
        for arg in transformed.args():
            if arg.is_or():
                # contains nested disjunction
                self._is_in_normal_form = False
                break

        return transformed

    def walk_and(self, formula, args, **kwargs):
        preprocessed = super().walk_and(formula, args, **kwargs)

        if not preprocessed.is_and():
            return preprocessed

        # push conjunctions "back"
        nested_disjunction = None
        conjuncts = set()
        for arg in preprocessed.args():
            if arg.is_or():
                nested_disjunction = arg
            conjuncts.add(arg)

        if nested_disjunction is not None:
            self._is_in_normal_form = False
            disjuncts = set()
            for arg in nested_disjunction.args():
                disjuncts.add(
                    self._manager.And(
                        conjuncts.difference({nested_disjunction}).union({arg})
                    )
                )

            return self._manager.Or(disjuncts)

        return preprocessed
