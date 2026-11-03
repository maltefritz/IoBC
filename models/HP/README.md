# HP – Heat pump

This folder contains the TESPy model of a heat pump with parallel compression and open economizer (working fluid R717), from which the heat pump parameters of the solph optimization model were derived.

**Please note**: `HeatPumpBase.py` and `HeatPumpPC.py` stem from the project [heatpumps](https://github.com/jfreissmann/heatpumps) (MIT license, see `LICENSE`). They correspond to commit [`c1122bf`](https://github.com/jfreissmann/heatpumps/tree/c1122bf94452abbaaa7ef184a2aaaf27909e772e), folder `src/heatpumps/models`. Later versions of the project differ considerably. The model, the files in `input` and the heat pump parameters are also part of the project [HTWP](https://github.com/maltefritz/HTWP) ([DOI](https://zenodo.org/doi/10.5281/zenodo.10869215)).

## Workflow

1. `input/params_hp_pc_econ_open_R717_{IIIgdh,IVgdh}.json` contains the parameters of the heat pump. It is a template: The temperatures (connections `B` and `C`) and the part load range (`offdesign`) have to be adjusted to the respective district heating network. `input/CEPCI.json` contains the cost indices for the cost calculation.
2. `HeatPumpPC` (with `econ_type='open'`) runs the design simulation (`run_model`) and the offdesign simulation for all combinations of heat source feed flow temperature, consumer feed flow temperature and part load (`offdesign_simulation`). It writes the results to `output/HeatPumpPCEconOpen_R717_partload.csv`.
3. `calc_partload_char` interpolates the results in steps of 1 K and 1 % part load. For each temperature pair, `linearize_partload_char` derives the linear relation `Q = c_1 * P + c_0` between heat output `Q` and power input `P`.
4. `arrange_char_timeseries` assigns these parameters to the hours of the year based on `T_hs_ff` and `T_cons_ff`. This results in the columns `hp_Q_max`, `hp_Q_min`, `hp_c_1` and `hp_c_0` in the input data of the optimization model, `../../optimization/{IIIgdh,IVgdh}_network/input/{IIIgdh,IVgdh}19_invest_data_HeatPumpPCEconOpen_R717.csv`.

In addition to the heat pump parameters, these files contain the other time series and the parameters of the CCET (`IIIgdh`) or the ICE (`IVgdh`), see `../CCET` and `../ICE`.

All heat pump columns are dimensionless: `hp_Q_max`, `hp_Q_min` and `hp_c_0` refer to the heat output at the nominal temperature pair, `hp_c_1` is the ratio of heat output to power input.

## Requirements

The model was tested with Python 3.11 and the package versions in `requirements.txt` (TESPy 0.6.3). Install the packages with:

```
pip install -r requirements.txt
```
