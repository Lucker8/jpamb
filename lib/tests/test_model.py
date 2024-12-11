from jpamb import model, jvm
from pathlib import Path


def test_suite_singleton():
    path = Path("../").absolute()
    assert model.Suite(path) is model.Suite(path)


def test_cases_roundtrip():

    cases = []

    with open("../stats/cases.txt") as fp:
        for line in fp:
            methodid, input, _ = model.Case.match(line).groups()
            absmethod = jvm.Absolute.decode(methodid, jvm.MethodID.decode)
            assert absmethod.encode() == methodid, f"{absmethod}"

            values = model.Input.decode(input)
            assert values.encode() == input, f"{values}"

            case = model.Case.decode(line)
            cases.append(case)

            assert isinstance(str(case), str), str(case)

    # Make sure we can sort methods
    assert sorted(cases) == sorted(sorted(cases))


def test_checkhealth():
    path = Path("../").absolute()
    model.Suite(path).checkhealth(failfast=True)


def test_classlookup():
    path = Path("../").absolute()
    suite = model.Suite(path)

    sourcefiles = list(suite.sourcefiles())
    classfiles = list(suite.classfiles())
    decompiledfiles = list(suite.decompiledfiles())

    for cn in suite.classes():
        assert suite.sourcefile(cn) in sourcefiles
        assert suite.classfile(cn) in classfiles
        assert suite.decompiledfile(cn) in decompiledfiles
