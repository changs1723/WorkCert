"""Hou-role independent acceptance, groups 1--3 (AI-assisted, 2026-11-03).

All expected numbers originate in rational integration or listed hand values.
No selector ranking or monotonic-error-under-refinement assertion is used.
"""
from fractions import Fraction as Q
import importlib.util
import os
from pathlib import Path
import unittest

from workcert import from_indices, reduce_response
from hou_support import AcceptanceCase, exact_errors, pl_integral, pl_value, prefix_peak


class HouFormulaTests(AcceptanceCase):
    def evaluate(self,x,f,ids,hand):
        expected, extrema = exact_errors(x,f,ids)
        # Check the independent oracle against hand-derived constants BEFORE
        # creating the object under test.
        for name,value in hand.items():
            self.check('oracle hand '+name,value,expected[name],atol=0)
        table = from_indices(x,f,ids)
        for name,value in expected.items():
            self.check('certificate '+name,value,getattr(table.certificate,name))
        rx,rf = [x[i] for i in ids],[f[i] for i in ids]
        for q,d in extrema.items():
            self.check('D witness x='+str(q),d, float(pl_integral(x,f,x[0],q))-table.work(float(q)))
            self.check('retained W x='+str(q),pl_integral(rx,rf,rx[0],q),table.work(float(q)))
        return table,expected,extrema

    def test_shifted_affine_line(self):
        self.evaluate([2,3,5,7],[-1,1,5,9],[0,3],
                      dict(eta=0,xi=0,prefix=0,window=0,delta=0,reference_work=20))

    def test_positive_triangle(self):
        self.evaluate([0,2,5],[0,6,0],[0,2],
                      dict(eta=15,xi=15,prefix=15,window=15,delta=6,signed_terminal_error=15))

    def test_negative_nonuniform_triangle(self):
        self.evaluate([-2,-1,3],[0,-3,0],[0,2],
                      dict(eta=Q(15,2),xi=Q(15,2),prefix=Q(15,2),window=Q(15,2),delta=3,signed_terminal_error=Q(-15,2)))

    def test_required_interior_extremum(self):
        table,expected,extrema=self.evaluate([0,1,2,3],[0,2,-1,0],[0,3],
                      dict(eta=Q(7,3),xi=Q(5,3),prefix=Q(5,3),window=Q(5,3),delta=2,
                           signed_terminal_error=1,min_cumulative_error=0,max_cumulative_error=Q(5,3)))
        self.check('critical abscissa',Q(5,3),max(extrema,key=extrema.get),atol=0)
        self.check_true('critical point is between original nodes',Q(5,3) not in [0,1,2,3])
        self.check('node-only maximum would miss extremum',Q(3,2),max(extrema[Q(i)] for i in range(4)),atol=0)

    def test_required_window_prefix_separation(self):
        x,f=[0,1,2,3,4,5,6],[0,2,0,-4,0,2,0]
        table,_,_=self.evaluate(x,f,[0,6],dict(eta=8,xi=4,prefix=2,window=4,delta=4,
                                      signed_terminal_error=0,min_cumulative_error=-2,max_cumulative_error=2))
        self.check('window witness [2,4]',-4,float(pl_integral(x,f,2,4))-table.window_work(2,4))
        self.check('zero terminal work',0,table.work(6))

    def test_nonzero_chord_multiple_retained_segments(self):
        # Residuals 0,3,-2,0,-3,0 on unequal-width intervals.
        # Positive lobe 33/10, negative lobes 63/10; eta=48/5, xi=63/10.
        self.evaluate([0,1,3,4,6,7],[1,5,2,5,4,8],[0,3,5],
                      dict(eta=Q(48,5),xi=Q(63,10),prefix=Q(33,10),window=Q(63,10),delta=3,
                           signed_terminal_error=-3,min_cumulative_error=-3,max_cumulative_error=Q(33,10)))


class HouWorkTests(AcceptanceCase):
    def test_piecewise_queries_at_endpoints_nodes_and_interior(self):
        x,f,ids=[-2,-1,1,4,6],[3,-2,5,1,-3],[0,2,3,4]
        rx,rf=[x[i] for i in ids],[f[i] for i in ids]
        queries=[Q(-2),Q(-3,2),Q(-1),Q(1,3),Q(1),Q(5,2),Q(4),Q(19,4),Q(6)]
        expected=[pl_integral(rx,rf,rx[0],q) for q in queries]
        table=from_indices(x,f,ids)
        actual=table.work([float(q) for q in queries])
        for q,e,a in zip(queries,expected,actual):
            self.check('vector prefix '+str(q),e,a)
            self.check('scalar prefix '+str(q),e,table.work(float(q)))
            self.check('force '+str(q),pl_value(rx,rf,q),table.force_at(float(q)))

    def test_window_queries_zero_length_nonnode_and_multisegment(self):
        x,f=[-2,-1,1,4,6],[3,-2,5,1,-3]
        ids=[0,2,3,4];rx,rf=[x[i] for i in ids],[f[i] for i in ids]
        windows=[(-2,-2),(6,6),(-2,6),(-2,1),(1,4),(Q(-3,2),Q(11,2)),(Q(1,3),Q(2,3)),(Q(5,2),Q(19,4))]
        expected=[pl_integral(rx,rf,a,b) for a,b in windows]
        table=from_indices(x,f,ids)
        for (a,b),e in zip(windows,expected):
            self.check('window '+str((a,b)),e,table.window_work(float(a),float(b)))
        broadcast=table.window_work([[-2],[1]],[[4,6]])
        for i,a in enumerate([-2,1]):
            for j,b in enumerate([4,6]):
                self.check('broadcast '+str((a,b)),pl_integral(rx,rf,a,b),broadcast[i,j])


class HouPeakTests(AcceptanceCase):
    def peak_checks(self,x,f,ids,queries,retained_global):
        expected=[prefix_peak(x,f,q) for q in queries]
        rx,rf=[x[i] for i in ids],[f[i] for i in ids]
        retained=[prefix_peak(rx,rf,q) for q in queries]
        table=from_indices(x,f,ids)
        global_peak=max(f);first=x[f.index(global_peak)]
        for q,p,hp in zip(queries,expected,retained):
            self.check('retained signed peak '+str(q),hp,table.peak_force(float(q)))
            lo,hi=table.peak_bounds(float(q))
            self.check_true('true source prefix covered '+str(q),lo-1e-12<=float(p)<=hi+1e-12,
                            expected=str(p)+' within bounds',actual=(lo,hi))
            if retained_global and q>=first:
                self.check('postpeak lower '+str(q),p,lo)
                self.check('postpeak upper '+str(q),p,hi)
        return table

    def test_mixed_force_global_signed_peak_retained(self):
        self.peak_checks([0,1,2,3,4,5],[0,2,1,6,-3,1],[0,3,5],
                         [0,Q(1,2),1,Q(3,2),Q(5,2),3,4,5],True)

    def test_signed_global_peak_omitted(self):
        self.peak_checks([0,1,2,3,4],[-2,3,-5,6,1],[0,2,4],
                         [0,Q(1,2),1,Q(3,2),Q(5,2),3,Q(7,2),4],False)

    def test_all_negative_signed_maximum(self):
        self.peak_checks([0,1,2,3,4],[-8,-2,-6,-3,-7],[0,1,4],
                         [0,Q(1,2),1,Q(3,2),3,4],True)

    def test_absolute_peak_is_not_signed_maximum(self):
        x,f=[0,1,2,3,4],[0,-9,2,4,0]
        for mode,index in [('absolute',1),('negative',1),('positive',3)]:
            table=reduce_response(x,f,method='uniform',max_points=3,preserve_peak=True,peak_mode=mode)
            self.check_true(mode+' selected peak present',index in table.indices,expected=index,actual=table.indices.tolist())
            lo,hi=table.peak_bounds(4)
            self.check_true(mode+' signed maximum covered',lo<=4<=hi,expected=4,actual=(lo,hi))
            if mode=='positive':
                self.check('positive lower exact',4,lo)
                self.check('positive upper exact',4,hi)

    def test_cfe_consumer_postpeak_and_prepeak(self):
        root=Path(os.environ.get('WORKCERT_RESEARCH_ROOT',Path(__file__).resolve().parents[2]))
        spec=importlib.util.spec_from_file_location('hou_query_client',root/'examples/query_exchange.py')
        client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
        x,f,ids=[0,1,2,3,4,5],[0,3,2,7,5,4],[0,1,3,5]
        e,_=exact_errors(x,f,ids)
        rx,rf=[x[i] for i in ids],[f[i] for i in ids]
        table=from_indices(x,f,ids,x_unit='mm',force_unit='kN')
        for q in [2,3,4,5]:
            row=client.query_metrics(table,10,[q])[0]
            w=pl_integral(rx,rf,0,q);p=prefix_peak(rx,rf,q)
            true_cfe=pl_integral(x,f,0,q)/q/prefix_peak(x,f,q)
            self.check('CFE central '+str(q),w/q/p,row['CFE'])
            self.check_true('CFE true covered '+str(q),row['CFE_lower']-1e-12<=float(true_cfe)<=row['CFE_upper']+1e-12,
                            expected=str(true_cfe)+' within interval',actual=(row['CFE_lower'],row['CFE_upper']))
            if q>=3:
                self.check('CFE postpeak lower '+str(q),(w-e['prefix'])/q/7,row['CFE_lower'])
                self.check('CFE postpeak upper '+str(q),(w+e['prefix'])/q/7,row['CFE_upper'])


if __name__=='__main__':
    unittest.main(verbosity=2)
