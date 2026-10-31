"""Client-side crashworthiness queries from a received table and a measured mass.

No dense reference or source workbook is read. The table must explicitly carry
mm/kN units and use the positive-compression convention of this example.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from workcert import ReducedResponse


def query_metrics(table, mass_g, strokes):
    if table.x_unit!='mm' or table.force_unit!='kN':
        raise ValueError('This engineering example requires explicit mm/kN table units')
    if not np.isfinite(mass_g) or mass_g<=0:
        raise ValueError('Measured mass must be positive and finite')
    rows=[]
    for q in np.atleast_1d(strokes).astype(float):
        if q<=table.x[0]:raise ValueError('Stroke must exceed the response origin')
        ea=table.work(q);span=q-table.x[0]
        if ea<=0:raise ValueError('Use the positive-compression convention for these crashworthiness metrics')
        peak=float(max(np.max(table.force[table.x<=q]),table.force_at(q)))
        e=table.certificate.prefix;d=table.certificate.delta
        elo,ehi=ea-e,ea+e;plo,phi=peak-d,peak+d
        rows.append({'stroke_mm':float(q),'EA_J':ea,'EA_lower_J':elo,'EA_upper_J':ehi,
                     'SEA_kJ_kg':ea/mass_g,'SEA_lower_kJ_kg':elo/mass_g,'SEA_upper_kJ_kg':ehi/mass_g,
                     'MCF_kN':ea/span,'MCF_lower_kN':elo/span,'MCF_upper_kN':ehi/span,
                     'PCF_kN':peak,'CFE':ea/span/peak,
                     'CFE_lower':elo/span/phi if plo>0 and elo>=0 else None,
                     'CFE_upper':ehi/span/plo if plo>0 and elo>=0 else None})
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('table',type=Path)
    parser.add_argument('--mass-g',type=float,required=True)
    parser.add_argument('--strokes',type=float,nargs='+',required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    table=ReducedResponse.load(args.table)
    result={'input_table':args.table.name,'measured_mass_g':args.mass_g,
            'reference_sha256':table.certificate.reference_sha256,
            'metrics':query_metrics(table,args.mass_g,args.strokes)}
    content=json.dumps(result,indent=2,allow_nan=False)+'\n'
    if args.output:args.output.write_text(content,encoding='utf8')
    else:print(content,end='')

if __name__=='__main__':main()
