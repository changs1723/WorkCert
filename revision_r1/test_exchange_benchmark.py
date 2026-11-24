"""Independent acceptance checks for the exchange benchmark diagnostics."""
from fractions import Fraction
import tempfile
from pathlib import Path
import unittest

import numpy as np
from benchmark_exchange import (ReducedResponse, bypass_fallback, count_fallback,
                                from_indices, reduce_response)


class ExchangeDiagnosticsTests(unittest.TestCase):
    def test_positive_windows_do_not_trigger_fallback(self):
        x=np.arange(9., dtype=float)
        f=np.arange(1., 10., dtype=float)
        table=from_indices(x,f,np.arange(9))
        a,b=np.array([0.,.5,2.]),np.array([4.,3.,8.])
        before=table.window_work(a,b)
        with count_fallback(table) as counts:
            observed=table.window_work(a,b)
        np.testing.assert_array_equal(before,observed)
        self.assertEqual(counts['queries'],3)
        self.assertEqual(counts['fallback_queries'],0)

    def test_stress_value_checked_with_rational_integration(self):
        x=np.arange(33., dtype=float)
        f=np.zeros(33)
        f[[1,3,5,7,9]]=2*np.array([1e100,1.,1e-100,-1e100,-1.])
        reference=sum((Fraction(float(x[i+1]))-Fraction(float(x[i]))) *
                      (Fraction(float(f[i+1]))+Fraction(float(f[i]))) / 2
                      for i in range(len(x)-1))
        table=from_indices(x,f,np.arange(len(x)))
        with count_fallback(table) as counts:
            observed=table.window_work(np.zeros(7),np.full(7,32.))
        np.testing.assert_array_equal(observed,np.full(7,float(reference)))
        self.assertEqual(counts['fallback_queries'],7)
        self.assertEqual(float(reference),2e-100)
        with bypass_fallback(table):
            self.assertEqual(table.window_work(0.,32.),0.)
        self.assertEqual(table.window_work(0.,32.),float(reference))

    def test_benchmark_diagnostics_restore_method_after_exception(self):
        t=from_indices([0.,1.,2.],[0.,1.,0.],[0,1,2])
        original=t._cancellation_fallback
        try:
            with count_fallback(t):
                raise RuntimeError('deliberate diagnostic interruption')
        except RuntimeError:
            pass
        self.assertEqual(t._cancellation_fallback,original)
        try:
            with bypass_fallback(t):
                raise RuntimeError('deliberate diagnostic interruption')
        except RuntimeError:
            pass
        self.assertEqual(t._cancellation_fallback,original)

    def test_real_serialized_file_retains_source_and_query_metadata(self):
        x=np.linspace(0.,10.,101)
        force=np.sin(x)+2.
        table=reduce_response(x,force,method='work',max_points=33,
                              x_unit='mm',force_unit='kN')
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'exchange.json'
            table.save(p)
            self.assertEqual(p.stat().st_size,len(table.to_bytes()))
            restored=ReducedResponse.load(p)
            self.assertEqual(restored.certificate,table.certificate)
            self.assertEqual(restored.metadata,table.metadata)
            self.assertTrue(restored.verify_reference(x,force))
            np.testing.assert_array_equal(restored.work([1.,5.,10.]),table.work([1.,5.,10.]))


if __name__=='__main__':
    unittest.main()
