import os

import pandas as pd

dirpath = os.path.dirname(os.path.abspath(__file__))

Q_Ns = [2.26, 4.28, 90]

data = []
for i, Q_N in enumerate(Q_Ns):
    datapath = os.path.join(
        dirpath, '02_TESPy_output', f'ice_parameters_{Q_N}.csv'
        )
    data.append(pd.read_csv(datapath, sep=';', index_col=0))

abs_cols = ['P_max_woDH', 'P_min_woDH', 'Q_in']

for col in abs_cols:
    for i, Q_N in enumerate(Q_Ns):
        data[i][col] /= Q_N

for i, Q_N in enumerate(Q_Ns):
    data[i]['ice_eta_el'] = data[i]['P_max_woDH'] / data[i]['Q_in']
    data[i]['ice_eta_th'] = 1 / data[i]['Q_in']

    data[i]['ice_H_max'] = (
        data[i]['P_max_woDH'] / data[i]['eta_el_max']
        )
    data[i]['ice_H_min'] = (
        data[i]['P_min_woDH'] / data[i]['eta_el_min']
        )

simdatapath = os.path.join(
    dirpath, '02_TESPy_output',
    'IVgdh19_invest_data_HeatPumpPCEconOpen_R717.csv'
    )
simdata = pd.read_csv(
    simdatapath, sep=';', index_col=0, parse_dates=True,
    float_precision='round_trip'
    )

for idx in simdata.index:
    temp = int(simdata.loc[idx, 'T_cons_ff'])
    for col in ['ice_H_max', 'ice_H_min', 'ice_eta_el', 'ice_eta_th']:
        simdata.loc[idx, col] = (
            sum(d.loc[temp, col] for d in data) / len(data)
            )

datapath = os.path.join(dirpath, '03_solph_param_input', 'data.csv')
simdata.to_csv(datapath, sep=';')
