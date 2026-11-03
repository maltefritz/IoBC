import os

import pandas as pd

dirpath = os.path.dirname(os.path.abspath(__file__))

Q_Ns= [70, 189]

data = []
for i, Q_N in enumerate(Q_Ns):
    datapath = os.path.join(
        dirpath, '02_TESPy_output', f'ccet_parameters_{Q_N}.csv'
        )
    data.append(pd.read_csv(datapath, sep=';', index_col=0))

    data[i]['ccet_Q_CW_min'] *= 1e-6

abs_cols = ['ccet_P_max_woDH', 'ccet_P_min_woDH', 'ccet_Q_CW_min', 'ccet_Q_in']

for col in abs_cols:
    for i, Q_N in enumerate(Q_Ns):
        data[i][col] /= Q_N

rel_error = pd.DataFrame(index=data[0].index, columns=data[0].columns)

for col in data[0].columns:
    rel_error[col] = (data[1][col] - data[0][col]) / data[0][col]

for i, Q_N in enumerate(Q_Ns):
    P_el_N_rel = (
        data[i]['ccet_P_max_woDH']
        - data[i]['ccet_beta']
        )

    data[i]['ccet_eta_el'] = P_el_N_rel / data[i]['ccet_Q_in']
    data[i]['ccet_eta_th'] = 1 / data[i]['ccet_Q_in']

    # data[i]['ccet_H_max'] = data[i]['ccet_Q_in']
    data[i]['ccet_H_max'] = (
        data[i]['ccet_P_max_woDH'] / data[i]['ccet_eta_el_max']
        )
    data[i]['ccet_H_min'] = (
        data[i]['ccet_P_min_woDH'] / data[i]['ccet_eta_el_min']
        )

simdatapath = os.path.join(dirpath, '02_TESPy_output', 'pn19_invest_data.csv')
simdata = pd.read_csv(simdatapath, sep=';', index_col=0, parse_dates=True)

for idx in simdata.index:
    temp = int(simdata.loc[idx, 'temp_feed_flow'])
    for col in ['ccet_H_max', 'ccet_H_min', 'ccet_eta_el', 'ccet_eta_th']:
        simdata.loc[idx, col] = (
            (data[0].loc[temp, col] + data[1].loc[temp, col]) / 2
            )

datapath = os.path.join(dirpath, '03_solph_param_input', 'data.csv')
simdata.to_csv(datapath, sep=';')
