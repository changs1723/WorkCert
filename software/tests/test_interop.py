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
        from dataclasses import replace
        from pathlib import Path
        import tempfile
        x, force = [0,1,2,3], [0,2,1,0]
        response=from_indices(x,force,[0,1,3])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'external.json';response.save(path)
            loaded=ReducedResponse.load(path)
            self.assertTrue(loaded.verify_reference(x,force))
            np.testing.assert_array_equal(loaded.work([.2,1.5]),response.work([.2,1.5]))
            # A table written on a different float64 implementation can differ
            # by final arithmetic bits, while its source hash stays exact.
            numeric = ("eta", "xi", "prefix", "window", "delta",
                       "signed_terminal_error", "reference_work",
                       "min_cumulative_error", "max_cumulative_error")
            for x_scale in (1e-9, 1., 1e9):
                for force_scale in (1e-9, 1., 1e9):
                    xx = np.array([0., .5, 1.5, 3.]) * x_scale
                    ff = np.array([0., 3., -1., 2.]) * force_scale
                    table = from_indices(xx, ff, [0, 1, 3])
                    c = table.certificate
                    for name in numeric:
                        with self.subTest(x_scale=x_scale, force_scale=force_scale,
                                          roundoff_field=name):
                            shifted = float(np.nextafter(getattr(c, name), np.inf))
                            changed = replace(c, **{name: shifted})
                            other = ReducedResponse(table.x, table.force, table.indices,
                                changed, metadata=table.metadata)
                            other.save(path)
                            restored = ReducedResponse.load(path)
                            before = restored.to_bytes()
                            if getattr(c, name) == 0.:
                                with self.assertRaisesRegex(ValueError, "Certificate field"):
                                    restored.verify_reference(xx, ff)
                            else:
                                self.assertTrue(restored.verify_reference(xx, ff))
                            self.assertEqual(restored.to_bytes(), before)
                    # Altered but internally consistent bounds must still be
                    # rejected after the envelope checksum has been renewed.
                    q_abs = float(np.sum(np.diff(xx) *
                        (0.5 * np.abs(ff[:-1]) + 0.5 * np.abs(ff[1:]))))
                    eta = c.eta + 1e-7 * q_abs
                    corruptions = (
                        replace(c, eta=eta, xi=(eta + abs(c.signed_terminal_error)) * .5),
                        replace(c, delta=c.delta + 1e-7 * float(np.max(np.abs(ff)))))
                    for bad in corruptions:
                        other = ReducedResponse(table.x, table.force, table.indices,
                            bad, metadata=table.metadata)
                        other.save(path)
                        with self.subTest(x_scale=x_scale, force_scale=force_scale,
                                          corruption="self-consistent bounds"):
                            with self.assertRaisesRegex(ValueError, "Certificate field"):
                                ReducedResponse.load(path).verify_reference(xx, ff)
                    changed_source = ff.copy()
                    changed_source[2] = np.nextafter(changed_source[2], np.inf)
                    with self.subTest(x_scale=x_scale, force_scale=force_scale,
                                      corruption="discarded source bit"):
                        with self.assertRaisesRegex(ValueError, "Reference checksum mismatch"):
                            table.verify_reference(xx, changed_source)
            # There is no absolute 1-unit floor: a zero source admits no
            # nonzero roundoff in either force or work metadata.
            zero = from_indices([0., 1., 2.], [0., 0., 0.], [0, 2])
            self.assertTrue(zero.verify_reference([0., 1., 2.], [0., 0., 0.]))
            tiny_delta = replace(zero.certificate, delta=float(np.nextafter(0., 1.)))
            other = ReducedResponse(zero.x, zero.force, zero.indices, tiny_delta,
                                    metadata=zero.metadata)
            with self.assertRaisesRegex(ValueError, "Certificate field 'delta'"):
                other.verify_reference([0., 1., 2.], [0., 0., 0.])


if __name__=='__main__':unittest.main()
