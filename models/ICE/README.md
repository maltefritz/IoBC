# ICE – Internal combustion engine

This folder contains the TESPy model of an internal combustion engine for combined heat and power in district heating (ICE) and the workflow to derive the ICE parameters of the solph optimization model from it.

**Please note**: The parameter data sets for the three plant sizes (`02_TESPy_output/ice_parameters_{2.26,4.28,90}.csv`) stem from the predecessor project [SWSH](https://github.com/maltefritz/SWSH). There, they are located in the folder `Eingangsdaten`, `ice_parameters_90.csv` is named `ice_parameters.csv`, and the original model is `Anlagenmodelle/ice/ice_040.py`. The model `ice_076.py` reproduces these data sets and can be used to regenerate them.

## Workflow

1. `ice_076.py` runs the TESPy simulation with the parameters from `01_TESPy_input`. For each plant size and feed flow temperature it determines the operating range and derives the parameters for the solph model. A complete run takes approx. 40–50 min per plant size.
2. `ice_076.py` writes the resulting parameters per feed flow temperature to `output/ice_parameters_{2.26,4.28,90}.csv`. The parameter files used in the publication are located in `02_TESPy_output`. 
3. `conversion.py` converts the parameters from `02_TESPy_output` into time series for the solph model. It adds them to the hourly time series `02_TESPy_output/IVgdh19_invest_data_HeatPumpPCEconOpen_R717.csv`, which is an input and not a TESPy result, and writes the result to `03_solph_param_input/data.csv`.

`data.csv` does not contain any heat pump parameters, as they are not part of this workflow. The complete input data of the optimization model, including the heat pump parameters, are located in `../../optimization/IVgdh_network/input/IVgdh19_invest_data_HeatPumpPCEconOpen_R717.csv`.

Units in `ice_parameters_*.csv`: electrical power (`P_max_woDH`, `P_min_woDH`) and fuel heat input (`Q_in`) in MW, all other parameters dimensionless.

## Requirements

The model was tested with Python 3.11 and the package versions in `requirements.txt` (TESPy 0.7.6). Install the packages with:

```
pip install -r requirements.txt
```

## Reproducibility

`ice_076.py` reproduces the parameter files `ice_parameters_{2.26,4.28,90}.csv` in `02_TESPy_output`. For all plant sizes and feed flow temperatures, the parameters deviate by at most 0.012 %. Applying `conversion.py` to the regenerated parameters, the ICE columns of `data.csv` deviate by at most 0.0063 %.
