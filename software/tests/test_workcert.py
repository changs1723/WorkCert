"""Independent numerical, persistence, boundary and command-line checks."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

from workcert import ReducedResponse, certify, reduce_response, split_monotone_branches

def make_table(x, force, **kwargs):
    kwargs.setdefault("method", "work")
    kwargs.setdefault("peak_mode", "positive")
    return reduce_response(x, force, **kwargs)


class AnalyticTests(unittest.TestCase):
    def test_affine_force_and_nonzero_origin(self):
        x = np.array([2., 3., 5., 8.])
        table = make_table(x, 3*x-7, max_points=2)
        q = np.array([[2., 3.2], [6., 8.]])
        expected = 1.5*(q*q-4)-7*(q-2)
        np.testing.assert_allclose(table.work(q), expected, atol=1e-13)
        np.testing.assert_allclose(table.force_at(q), 3*q-7, atol=1e-13)
        self.assertAlmostEqual(table.window_work(3, 7), 32.)
        self.assertEqual(table.certificate.eta, 0.)

    def test_one_sign_error_has_exact_equal_bounds(self):
        c = certify([0,1,2,3,4], [0,1,4,9,16], [0,4])
        self.assertEqual(c.reference_work, 22.)
        self.assertEqual(c.signed_terminal_error, -10.)
        self.assertEqual((c.eta,c.xi,c.prefix,c.window,c.delta), (10.,10.,10.,10.,4.))

    def test_cancellation_and_two_sided_window(self):
        c = certify(np.arange(7), [0,2,0,-4,0,2,0], [0,6])
        self.assertEqual(c.reference_work, 0.)
        self.assertEqual((c.eta,c.xi,c.prefix,c.window), (8.,4.,2.,4.))
        self.assertEqual(c.min_cumulative_error, -2.)
        self.assertEqual(c.max_cumulative_error, 2.)
        with self.assertRaises(ValueError):
            c.bound(relative=True)

    def test_interior_stationary_point_not_missed(self):
        # Residual r moves 0, 1, -1, 0. The positive primitive peaks at x=1.5.
        c = certify([0,1,2,3], [0,1,-1,0], [0,3])
        self.assertAlmostEqual(c.prefix, .75)
        self.assertAlmostEqual(c.window, .75)

    def test_peak_and_nonmonotone_hierarchy(self):
        x = [0,1,2,3,4,5]
        f = [0,1,2,0,3,0]
        tables = [make_table(x,f,max_points=k) for k in (3,4,5)]
        np.testing.assert_allclose([t.certificate.eta for t in tables], [2.590909090909091,3.,0.])
        self.assertTrue(all(4 in t.indices and max(t.force)==3 for t in tables))
        stopped = make_table(x,f,max_points=5,tolerance=2.8,certificate="eta")
        self.assertEqual(len(stopped.x),3)
        self.assertTrue(stopped.metadata["tolerance_met"])
        unmet = make_table(x,f,max_points=3,tolerance=1e-6)
        self.assertFalse(unmet.metadata["tolerance_met"])

    def test_shift_invariance_and_signed_normalization(self):
        x = np.arange(7.)
        f = np.array([-2,1,0,-4,3,-1,-2.])
        a=make_table(x,f,max_points=5)
        b=make_table(x,f+100,max_points=5)
        np.testing.assert_array_equal(a.indices,b.indices)
        np.testing.assert_allclose([a.certificate.eta,a.certificate.prefix,a.certificate.window],
                                   [b.certificate.eta,b.certificate.prefix,b.certificate.window],atol=1e-12)
        self.assertEqual(a.certificate.bound(relative=True),a.certificate.prefix/abs(a.certificate.reference_work))

    def test_random_certificates_against_dense_independent_quadrature(self):
        rng=np.random.default_rng(4832)
        for _ in range(20):
            x=np.r_[0.,np.cumsum(rng.uniform(.1,1.5,12))]
            f=rng.normal(1,2,len(x))
            ids=np.r_[0,np.sort(rng.choice(np.arange(1,len(x)-1),4,replace=False)),len(x)-1]
            c=certify(x,f,ids)
            grid=np.unique(np.r_[np.linspace(x[0],x[-1],100001),x])
            r=np.interp(grid,x,f)-np.interp(grid,x[ids],f[ids])
            dx=np.diff(grid)
            d=np.r_[0.,np.cumsum(.5*(r[:-1]+r[1:])*dx)]
            eta=float(np.sum(.5*(np.abs(r[:-1])+np.abs(r[1:]))*dx))
            self.assertAlmostEqual(eta,c.eta,delta=1e-6)
            self.assertAlmostEqual(max(abs(d)),c.prefix,delta=1e-6)
            self.assertAlmostEqual(max(d)-min(d),c.window,delta=1e-6)
            self.assertLessEqual(c.prefix,c.window+1e-12)
            self.assertLessEqual(c.window,c.xi+1e-12)
            self.assertLessEqual(c.xi,c.eta+1e-12)

    def test_random_window_queries_obey_bound(self):
        rng=np.random.default_rng(93)
        x=np.linspace(0,10,57)
        f=np.sin(4*x)+.5*x
        reference=make_table(x,f,max_points=len(x))
        reduced=make_table(x,f,max_points=11)
        endpoints=np.sort(rng.uniform(0,10,(2,1000)),axis=0)
        actual=reference.window_work(*endpoints)-reduced.window_work(*endpoints)
        self.assertTrue(np.all(np.abs(actual)<=reduced.certificate.window+1e-12))
        scalar=reference.work(10)-reduced.work(10)
        self.assertAlmostEqual(scalar,reduced.certificate.signed_terminal_error,delta=1e-12)

    def test_units_preserve_native_numeric_product(self):
        a=make_table([0,2],[2,2],max_points=2,x_unit="mm",force_unit="N")
        self.assertEqual(a.work_unit,"mJ")
        self.assertEqual(a.work(2),4.)
        b=make_table([0,2],[2,2],max_points=2,x_unit="m",force_unit="kN")
        self.assertEqual(b.work_unit,"kJ")
        self.assertEqual(b.work(2),4.)

    def test_uniform_and_full_reproduction(self):
        x=np.array([0,.1,.3,.8,1,2,4,6])
        f=np.array([0,1,8,2,4,3,5,0])
        for method in ("uniform","uniform_peak","work","vertical"):
            t=make_table(x,f,max_points=5,method=method,preserve_peak=False)
            self.assertEqual(len(t.x),5)
        t=make_table(x,f,max_points=100)
        self.assertEqual(t.certificate.eta,0.)
        np.testing.assert_array_equal(t.force_at(x),f)

    def test_large_signed_background_near_zero_terminal_work(self):
        # Separate integrations of large cancelling loads lose more low bits
        # than integration of the residual. The loader must allow that normal
        # float64 discrepancy while retaining an exactly reproducible payload.
        x=np.linspace(0,1,101)
        f=1e12*(2*x-1)+.001*np.sin(np.pi*x)
        table=make_table(x,f,max_points=2)
        self.assertTrue(table.verify_reference(x,f))
        self.assertTrue(np.isfinite(table.certificate.prefix))


class InputAndPersistenceTests(unittest.TestCase):
    def test_invalid_inputs(self):
        cases=[([0,0],[1,2]),([1,0],[1,2]),([0,np.nan],[1,2]),([0,1],[1,np.inf]),
               ([0,1],[1]),([[0,1]],[[1,2]]),([0],[1]),([0,1],[0,1j])]
        for x,f in cases:
            with self.assertRaises(ValueError):
                make_table(x,f)
        for budget in (1,-1,3.2,True):
            with self.assertRaises(ValueError):
                make_table([0,1,2],[0,3,0],max_points=budget)
        with self.assertRaises(ValueError):
            make_table([0,1,2],[0,3,0],max_points=2)
        for ids in ([0,1.5,2],[2,0],[0,0,2],[0,1],[0,1,3]):
            with self.assertRaises(ValueError):
                certify([0,1,2],[0,3,0],ids)
        for kw in ({"method":"unknown"},{"certificate":"wrong"},{"tolerance":-1},
                   {"tolerance":np.nan},{"method":"uniform","tolerance":.1},
                   {"tolerance":"wrong"},{"tolerance":1j},{"provenance":[]}):
            with self.assertRaises(ValueError):
                make_table([0,1,2],[0,3,0],**kw)

    def test_zero_work_requires_absolute_tolerance(self):
        with self.assertRaises(ValueError):
            make_table([0,1,2],[-1,0,1],tolerance=.1,relative=True)
        a=make_table([0,1,2],[-1,0,1],tolerance=0.)
        self.assertTrue(a.metadata["tolerance_met"])

    def test_query_domains_and_shapes(self):
        t=make_table([2,3,4],[1,3,2],max_points=3)
        for q in (1.99,4.01,np.nan,np.inf,2+1j):
            with self.assertRaises(ValueError): t.work(q)
            with self.assertRaises(ValueError): t.force_at(q)
        with self.assertRaises(ValueError): t.window_work(3,2)
        self.assertEqual(t.work(np.ones((2,3))*3).shape,(2,3))
        self.assertEqual(t.window_work(2,np.array([2,3,4])).shape,(3,))
        self.assertEqual(t.window_work(3,3),0.)

    def test_save_load_reference_and_corruption(self):
        x=[0,1,2,3,4]
        f=[0,3,1,4,0]
        table=make_table(x,f,max_points=4,provenance={"dataset":"synthetic-test"})
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"table.json"
            table.save(p)
            loaded=ReducedResponse.load(p)
            self.assertEqual(table.to_bytes(),loaded.to_bytes())
            self.assertTrue(loaded.verify_reference(x,f))
            np.testing.assert_array_equal(table.work([.5,1.5,3.5]),loaded.work([.5,1.5,3.5]))
            with self.assertRaises(ValueError): loaded.verify_reference(x,[0,3,1,5,0])
            document=json.loads(p.read_text())
            document["payload"]["force"][1]+=1
            p.write_text(json.dumps(document))
            with self.assertRaisesRegex(ValueError,"checksum"):
                ReducedResponse.load(p)
            # Re-signing does not evade structural invariant checks, nor does a
            # checksum imply authenticity against deliberate re-signing.
            document["payload"]["certificate"]["window"]=-1
            canonical=json.dumps(document["payload"],sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
            document["payload_sha256"]=hashlib.sha256(canonical).hexdigest()
            p.write_text(json.dumps(document))
            with self.assertRaises(ValueError): ReducedResponse.load(p)

    def test_readonly_arrays_and_metadata_copy(self):
        t=make_table([0,1,2],[0,1,0],max_points=3,provenance={"key":"original"})
        with self.assertRaises(ValueError): t.x[0]=5
        original_work=t.work(np.array([.2,.8,1.5]))
        for array in (t.x,t.force,t.indices):
            with self.assertRaises(ValueError): array.setflags(write=True)
            self.assertTrue(memoryview(array).readonly)
        np.testing.assert_array_equal(t.work([.2,.8,1.5]),original_work)
        d=t.metadata;d["provenance"]["key"]="changed"
        self.assertEqual(t.metadata["provenance"]["key"],"original")


class CommandLineTests(unittest.TestCase):
    def run_cli(self,*args):
        return subprocess.run([sys.executable,"-m","workcert",*args],capture_output=True,text=True)

    def test_complete_csv_reduce_query_verify(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"input.csv";q=Path(folder)/"table.json"
            p.write_text("stroke_mm,force_kN\n0,0\n1,2\n2,1\n3,0\n")
            result=self.run_cli("reduce",str(p),str(q),"--max-points","3","--method","work")
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)["points"],3)
            result=self.run_cli("query",str(q),"--at","0.5","2.5")
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(len(json.loads(result.stdout)["work"]),2)
            result=self.run_cli("verify",str(q),str(p))
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue(json.loads(result.stdout)["verified"])
            result=self.run_cli("query",str(q),"--window","2","1")
            self.assertEqual(result.returncode,2)
            self.assertNotIn("Traceback",result.stderr)

    def test_bad_csv_and_missing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"bad.csv"
            p.write_text("a,b\n0,1\n")
            result=self.run_cli("reduce",str(p),str(Path(folder)/"out.json"),"--method","work")
            self.assertEqual(result.returncode,2)
            result=self.run_cli("inspect",str(Path(folder)/"missing.json"))
            self.assertEqual(result.returncode,2)
            self.assertNotIn("Traceback",result.stderr)


if __name__ == "__main__":
    unittest.main()
