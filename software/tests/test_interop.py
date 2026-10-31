import unittest
import numpy as np
from workcert import from_indices, certify, ReducedResponse


class ExternalSelectionTests(unittest.TestCase):
    def test_arbitrary_subset_matches_independent_error_evaluation(self):
        x, force = np.arange(7.), [0, 4, 1, 3, -2, 1, 0]
        ids = [0, 1, 4, 6]
        response = from_indices(x, force, ids, x_unit="mm", force_unit="N", provenance={"selector":"external test"})
        self.assertEqual(response.certificate, certify(x, force, ids))
        self.assertTrue(response.verify_reference(x, force))
        self.assertEqual(response.metadata["selection_method"], "external_indices")
        self.assertEqual(response.work_unit, "mJ")
        truth = from_indices(x, force, np.arange(7))
        actual = truth.work(3.3) - response.work(3.3)
        self.assertLessEqual(abs(actual), response.certificate.prefix)

    def test_endpoint_integer_and_provenance_validation(self):
        for ids in ([1, 3], [0, 2.5, 3], [0, 0, 3], [0, 4]):
            with self.assertRaises(ValueError):from_indices([0,1,2,3], [0,2,1,0], ids)
        with self.assertRaises(ValueError):from_indices([0,1], [1,2], [0,1], provenance=[])

    def test_external_table_survives_portable_roundtrip(self):
        from pathlib import Path
        import tempfile
        x, force = [0,1,2,3], [0,2,1,0]
        response=from_indices(x,force,[0,1,3])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'external.json';response.save(path)
            loaded=ReducedResponse.load(path)
            self.assertTrue(loaded.verify_reference(x,force))
            np.testing.assert_array_equal(loaded.work([.2,1.5]),response.work([.2,1.5]))


if __name__=='__main__':unittest.main()
