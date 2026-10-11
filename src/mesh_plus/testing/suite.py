"""Owner-callable unittest suites with independent expected native facts."""

import copy
import hashlib
import unittest
from dataclasses import asdict

from jsonschema.exceptions import ValidationError

from ..api import SDK_INTERFACE_VERSION, current_sessions, reconstructed, validate_response
from ..protocol import ProtocolError
from ..state import check_binding, resolve_profile
from .cases import corpus_bytes, profile_cases

CONFORMANCE_INTERFACE_VERSION = 1


class _ProfileTest(unittest.TestCase):
    def __init__(self, factory, case):
        super().__init__("runTest")
        self.factory, self.case = factory, case
        self.domain = case.domain
        self.case_id = "profile-" + case.case_id

    def runTest(self):
        c = self.case
        p = resolve_profile(c.domain, self.factory(c.domain))
        response = copy.deepcopy(c.response)
        validate_response(response, profile=p)
        self.assertEqual([list(p.record_identity(row)) for row in response["sessions"]], c.identities)
        for host in response["mesh"]["hosts"]:
            if host["owner"] is None:
                continue
            host_id = host["hostId"]
            frame = reconstructed(response, host, profile=p)
            self.assertEqual(frame, c.native[host_id])
            for source in ("default", "configured_source"):
                codec = p.bind(host_id, source)
                check_binding(codec, host_id, source, p.descriptor.profile_id)
                inspected = codec.inspect_native(copy.deepcopy(frame))
                for row in inspected.records:
                    self.assertIs(type(p.record_eligible(row, inspected)), bool)
                state = asdict(inspected)
                state["records"], state["receipts"] = list(state["records"]), list(state["receipts"])
                self.assertEqual(state, c.states[host_id])
        for sample in c.selections:
            self.assertEqual(current_sessions(response, sample["now_ms"], response["mesh"]["reader"]["clock"], profile=p),
                             sample["rows"])
        # Mutation controls exercise Mesh guarantees, not arbitrary native errors.
        if response["sessions"]:
            duplicate = copy.deepcopy(response)
            duplicate["sessions"].insert(0, copy.deepcopy(duplicate["sessions"][0]))
            with self.assertRaises((ProtocolError, ValidationError)):
                validate_response(duplicate, profile=p)
        for index, host in enumerate(response["mesh"]["hosts"]):
            if host["receipts"] and host["owner"]["metadata"] is not None:
                missing = copy.deepcopy(response)
                missing["mesh"]["hosts"][index]["receipts"].pop()
                with self.assertRaises((ProtocolError, ValidationError)):
                    validate_response(missing, profile=p)
            for j, receipt in enumerate(host["receipts"]):
                if receipt["expiresAtMs"] is not None:
                    upgraded = copy.deepcopy(response)
                    upgraded["mesh"]["hosts"][index]["receipts"][j]["expiresAtMs"] += 100
                    with self.assertRaises((ProtocolError, ValidationError)):
                        validate_response(upgraded, profile=p)


def profile_suite(profile_factory, *, domain, cases=None):
    """Create pure tests; expected facts must not come from the tested profile."""
    selected = tuple(profile_cases(domain) if cases is None else cases)
    if not selected or any(c.domain != domain for c in selected) or len({c.case_id for c in selected}) != len(selected):
        raise ValueError("conformance_cases")
    return unittest.TestSuite(_ProfileTest(profile_factory, case) for case in selected)


class _Result(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.cases = []

    def _record(self, test, status):
        item = {"caseId": test.case_id, "status": status}
        if hasattr(test, "case"):
            from ..protocol import encode
            item["inputDigest"] = "sha256:" + hashlib.sha256(encode(asdict(test.case))).hexdigest()
        self.cases.append(item)

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, "failed")

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, "error")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "skipped")

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._record(test, "expected_failure")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._record(test, "unexpected_success")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self._record(test, "failed" if issubclass(err[0], test.failureException) else "error")


def run_suite(suite, *, domain):
    """Run on a synchronous caller thread; skips cannot certify conformance."""
    from ..state import descriptor
    expected = descriptor(domain)
    def cases(items):
        for item in items:
            if isinstance(item, unittest.TestSuite):
                yield from cases(item)
            else:
                yield item
    selected = list(cases(suite))
    if not selected or any(getattr(test, "domain", None) != domain for test in selected):
        raise ValueError("conformance_suite_scope")
    if len({test.case_id for test in selected}) != len(selected):
        raise ValueError("conformance_suite_duplicates")
    result = _Result()
    suite.run(result)
    complete = (result.testsRun == len(selected) == len(result.cases)
                and {case["caseId"] for case in result.cases} == {test.case_id for test in selected}
                and all(case["status"] == "passed" for case in result.cases))
    return {"format": "mesh-plus.conformance.v1", "interfaceVersion": CONFORMANCE_INTERFACE_VERSION,
            "sdkVersion": SDK_INTERFACE_VERSION, "profile": asdict(expected),
            "corpusDigest": "sha256:" + hashlib.sha256(corpus_bytes()).hexdigest(),
            "coverage": "selected cases only; owner-native semantics and deployment are separate",
            "ok": result.wasSuccessful() and complete,
            "testsRun": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
            "skipped": len(result.skipped), "cases": result.cases}
