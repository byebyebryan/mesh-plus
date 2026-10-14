"""Receipt order belongs to one acquisition stream, not completion order."""

from .protocol import check


class ReceiptHistory:
    def __init__(self):
        self.owner_binding = None
        self.accepted = {}

    def check(self, binding, receipts):
        if binding == self.owner_binding:
            for receipt in receipts:
                previous = self.accepted.get((receipt["sourceId"], receipt["component"]))
                if previous is not None:
                    check(receipt["accepted"] >= previous[0], "source_receipt_regression")
                    check(receipt["accepted"] != previous[0] or receipt["expiry"] == previous[1],
                          "source_lease_renewal")

    def commit(self, binding, receipts):
        self.accepted = {(r["sourceId"], r["component"]): (r["accepted"], r["expiry"])
                         for r in receipts}
        self.owner_binding = binding
