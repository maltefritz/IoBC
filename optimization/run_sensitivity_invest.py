import json
import os
from time import time

import pandas as pd
import postprocessing_invest

import optimization.energy_system_invest as energy_system_invest

# %% Simulation parameters
overwrite = True
only_high_gaps = False

energy_systems = ['IVgdh'] # ['pn']
scenarios = ['19']

# Heat Pumps

hps = ['HeatPumpPCEconOpen_R717']

# Relative gas prices
# gas_prices = [*range(100, 201, 1)]
gas_prices = [*range(10, 101, 1)]
el_prices = [*range(80, 140, 20)]

# %% simulation and postprocessing functions
es_funcs = {
    'pn': energy_system_invest.primary_network_invest,
    'IVgdh': energy_system_invest.IVgdh_network_invest
    }

pp_funcs = {
    'pn': postprocessing_invest.primary_network_invest,
    'IVgdh': postprocessing_invest.IVgdh_network_invest
    }

# Readability help
longnames = {
    'pn': 'primary_network', 'IVgdh': 'IVgdh_network'
    }

for es in energy_systems:
    if es == 'pn':
        gp_var = 'gas_price'
    elif es == 'IVgdh':
        gp_var = 'biogas_price'
    for scn in scenarios:
        for hp in hps:
            print(f'\n##### {es}{scn}: {hp} #####\n')

            # %% Read data
            inputpath = os.path.join(
                __file__, '..', longnames[es], 'input', es+scn
                )

            datafile = f'{inputpath}_invest_data_{hp}.csv'
            data = pd.read_csv(
                datafile, sep=';', index_col=0, parse_dates=True
                )

            base_gp = data[gp_var].copy()
            base_ep = data['el_spot_price'].copy()

            paramfile = f'{inputpath}_invest_param_{hp}.json'
            with open(paramfile, 'r', encoding='utf-8') as file:
                param = json.load(file)

            # %% Prepare output file structure
            rootoutputpath = os.path.join(
                __file__, '..', longnames[es],
                'output', f'{es}{scn}_sensitivity'
                )
            if not os.path.exists(rootoutputpath):
                os.mkdir(rootoutputpath)
            alloutputpath = os.path.join(rootoutputpath, f'{es}{scn}_invest')

            # %% Execute optimization
            param['param']['mipgap'] = 1e-3
            param['param']['TimeLimit'] = 60*60*20
            # param['param']['MIPFocus'] = 2
            param['param']['chp_bonus'] = 0
            param['param']['h_max_chp_bonus'] = 0
            param['param']['TEHG_bonus'] = 0
            param['param']['use_BEW_op_bonus'] = False
            param['param']['BEW'] = 0
            # param['st-tes']['inv_spez_m'] = 999999
            # param['st-tes']['op_cost_var'] = 9999
            # param['st-tes']['cap_min'] = 0

            # print(json.dumps(param, indent=4))

            # %% Read in or prepare meta result DataFrames
            multiindex = pd.MultiIndex.from_product([el_prices, gas_prices])
            captablepath = f'{alloutputpath}_ALLcapacities_{hp}.csv'
            if os.path.exists(captablepath):
                captable = pd.read_csv(
                    captablepath, sep=';',
                    index_col=['el_spot_price', gp_var]
                    )
            else:
                captable = pd.DataFrame(index=multiindex)
                captable.index.names = ['el_spot_price', gp_var]

            heattablepath = f'{alloutputpath}_ALLcoverages_{hp}.csv'
            if os.path.exists(heattablepath):
                heattable = pd.read_csv(
                    heattablepath, sep=';',
                    index_col=['el_spot_price', gp_var]
                    )
            else:
                heattable = pd.DataFrame(index=multiindex)
                heattable.index.names = ['el_spot_price', gp_var]

            # %% Sensitivity analysis loop
            for ep in el_prices:
                data['el_spot_price'] = ep * base_ep / 100
                print(
                    'Mean electricity price: '
                    + str(data['el_spot_price'].mean()) + ' €'
                )
                print(f'Relative to base electricity price: {ep}\n')

                eloutputpath = os.path.join(
                    rootoutputpath, f'{ep*100:.0f}xEL_PRICE'
                    )
                if not os.path.exists(eloutputpath):
                    os.mkdir(eloutputpath)

                for gp in gas_prices:
                    data[gp_var] = gp * base_gp / 100
                    print('Mean gas price: ' + str(data[gp_var].mean()) + ' €')
                    print(f'Relative to base gas price: {gp}\n')

                    gasoutputpath = os.path.join(
                        eloutputpath, f'{gp}xGAS_PRICE'
                        )
                    if not os.path.exists(gasoutputpath):
                        os.mkdir(gasoutputpath)

                    outputpath = os.path.join(
                        gasoutputpath,
                        f'{es}{scn}_{ep}xEL_PRICE_{gp}'
                        + f'xGAS_PRICE_{hp}'
                    )
                    if os.path.exists(f'{outputpath}_capacities.csv'):
                        if not overwrite:
                            continue
                        else:
                            if only_high_gaps:
                                sol_gap = captable.loc[
                                    (ep,
                                     gp),
                                    'MIPGap'
                                    ] / 100
                                if sol_gap < param['param']['mipgap']:
                                    continue
                    args = [data, param]
                    if es == 'pn':
                        use_hp = True
                        if hp == 'woHeatPump':
                            use_hp = False
                        print(f'##### use_hp set to `{use_hp}`!! #####\n')
                        args.append(use_hp)


                    time_start = time()
                    results, meta_results = es_funcs[es](*args)
                    time_end = time()

                    args = [results, meta_results, data, param]
                    if es == 'pn':
                        args.append(use_hp)
                    data_all, data_caps, key_params, cost_df = pp_funcs[es](*args)

                    # %% Meta Results
                    key_params['simulation_duration'] = time_end - time_start
                    postprocessing_invest.check_objective(
                        key_params, debug=True
                    )

                    for cap in data_caps.columns:
                        captable.loc[(ep, gp), cap] = data_caps.loc[0, cap]
                    captable.loc[(ep, gp), 'MIPGap'] = round(
                        key_params['gap'], 3
                    )
                    captable.sort_index(inplace=True)
                    captable.to_csv(captablepath, sep=';')

                    for col in data_all.columns:
                        if 'Q' in col:
                            heattable.loc[(ep, gp), col] = data_all[col].sum()
                    heattable.loc[(ep, gp), 'MIPGap'] = round(
                        key_params['gap'], 3
                    )
                    heattable.sort_index(inplace=True)
                    heattable.to_csv(heattablepath, sep=';')

                    # %% Setup specific results
                    capsfile = f'{outputpath}_capacities.csv'
                    data_caps.to_csv(capsfile, sep=';')

                    tsfile = f'{outputpath}_timeseries.csv'
                    data_all.to_csv(tsfile, sep=';')

                    keyparampath = (
                        f'{outputpath}_key_parameters.json'
                        )
                    with open(keyparampath, 'w', encoding='utf-8') as file:
                        json.dump(key_params, file, indent=4, sort_keys=True)

                    cost_df.to_csv(
                        f'{outputpath}_unit_cost.csv', sep=';'
                        )
