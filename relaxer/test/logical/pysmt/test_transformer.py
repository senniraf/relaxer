import unittest

from pysmt.shortcuts import And, Not, Or, Symbol

from relaxer.logical.pysmt.normalform import CNFTransformer, NNFTransformer


# TODO: Make assertions independent from ordering
class TestNNFTransformer(unittest.TestCase):
    def test_not(self):
        a = Symbol("a")
        formula = Not(Not(a))
        sut = NNFTransformer()
        nnf = sut.transform(formula)
        self.assertEquals(nnf, a)

    def test_and(self):
        a, b, c = Symbol("a"), Symbol("b"), Symbol("c")
        formula = Not(And(a, b, c))
        sut = NNFTransformer()
        nnf = sut.transform(formula)
        self.assertEquals(nnf, Or(Not(a), Not(b), Not(c)))

    def test_or(self):
        a, b, c = Symbol("a"), Symbol("b"), Symbol("c")
        formula = Not(Or(a, b, c))
        sut = NNFTransformer()
        nnf = sut.transform(formula)
        self.assertEquals(nnf, And(Not(a), Not(b), Not(c)))

    def test_nested_or_and(self):
        a, b, c = Symbol("a"), Symbol("b"), Symbol("c")
        formula = Not(Or(a, And(b, c)))
        sut = NNFTransformer()
        nnf = sut.transform(formula)
        self.assertEquals(nnf, And(Not(a), Or(Not(b), Not(c))))

    def test_nested_and_or(self):
        a, b, c = Symbol("a"), Symbol("b"), Symbol("c")
        formula = Not(And(a, Or(b, c)))
        sut = NNFTransformer()
        nnf = sut.transform(formula)
        self.assertEquals(nnf, Or(Not(a), And(Not(b), Not(c))))


class TestCNFTransformer(unittest.TestCase):
    def test_not(self):
        a = Symbol("a")
        formula = Not(Not(a))
        sut = CNFTransformer()
        cnf = sut.transform(formula)
        self.assertEquals(cnf, a)

    def test_not_and(self):
        a, b, c = Symbol("a"), Symbol("b"), Symbol("c")
        formula = Not(And(a, b, c))
        sut = CNFTransformer()
        cnf = sut.transform(formula)
        self.assertEquals(cnf, Or(Not(a), Not(b), Not(c)))

    def test__not_or(self):
        a, b, c = Symbol("a"), Symbol("b"), Symbol("c")
        formula = Not(Or(a, b, c))
        sut = CNFTransformer()
        cnf = sut.transform(formula)
        self.assertEquals(cnf, And(Not(a), Not(b), Not(c)))

    def test_nested_or_and(self):
        a, b, c = Symbol("a"), Symbol("b"), Symbol("c")
        formula = Not(Or(a, And(b, c)))
        sut = CNFTransformer()
        cnf = sut.transform(formula)
        self.assertEquals(cnf, And(Not(a), Or(Not(b), Not(c))))

    def test_nested_and_or(self):
        a, b, c = Symbol("a"), Symbol("b"), Symbol("c")
        formula = Not(And(a, Or(b, c)))
        sut = CNFTransformer()
        cnf = sut.transform(formula)
        self.assertEquals(cnf, And(Or(Not(a), Not(c)), Or(Not(a), Not(b))))

    def test_dnf(self):
        a, b, c, d = Symbol("a"), Symbol("b"), Symbol("c"), Symbol("d")
        formula = Or(And(a, b), And(c, d))
        sut = CNFTransformer()
        cnf = sut.transform(formula)
        print(cnf.get_type())
        self.assertEquals(cnf, And(Or(a, c), Or(b, c), Or(a, d), Or(b, d)))


if __name__ == "__main__":
    unittest.main()
