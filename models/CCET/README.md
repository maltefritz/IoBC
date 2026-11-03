# CCET – Combined cycle with extraction turbine

This folder contains the TESPy model of a combined cycle power plant with an extraction condensing turbine for district heating (CCET) and the workflow to derive the CCET parameters of the solph optimization model from it.

**Please note**: The parameter data sets for the plant sizes of 70 MW and 189 MW nominal heat flow (`02_TESPy_output/ccet_parameters_{70,189}.csv`) stem from the predecessor project [SWSH](https://github.com/maltefritz/SWSH). There, they are located in the folder `Eingangsdaten` with the column prefix `CCET_` instead of `ccet_`, and the original model is `Anlagenmodelle/cet/ccet_040.py`. The model `ccet_076.py` reproduces these data sets and can be used to regenerate them.

## Workflow

1. `ccet_076.py` runs the TESPy simulation with the parameters from `01_TESPy_input`. For each plant size and feed flow temperature it determines the operating range and derives the parameters for the solph model. A complete run takes several hours (approx. 2 h for 70 MW and 3–4 h for 189 MW).
2. `ccet_076.py` writes the resulting parameters per feed flow temperature to `output/ccet_parameters_{70,189}.csv`. The parameter files used in the publication are located in `02_TESPy_output`.
3. `conversion.py` converts the parameters from `02_TESPy_output` into time series for the solph model. It adds them to the hourly time series `02_TESPy_output/pn19_invest_data.csv`, which is an input and not a TESPy result, and writes the result to `03_solph_param_input/data.csv`.

`data.csv` does not contain any heat pump parameters, as they are not part of this workflow. The complete input data of the optimization model, including the heat pump parameters, are located in `../../optimization/IIIgdh_network/input/IIIgdh19_invest_data_HeatPumpPCEconOpen_R717.csv`.

Units in `ccet_parameters_{70,189}.csv`: electrical power (`ccet_P_max_woDH`, `ccet_P_min_woDH`) and fuel heat input (`ccet_Q_in`) in MW, minimum cooling water heat flow (`ccet_Q_CW_min`) in W, all other parameters dimensionless.

## Requirements

The model was tested with Python 3.11 and the package versions in `requirements.txt` (TESPy 0.7.6). Install the packages with:

```
pip install -r requirements.txt
```

## Reproducibility

`ccet_076.py` reproduces the parameter files `ccet_parameters_{70,189}.csv` in `02_TESPy_output`. Applying `conversion.py` to the regenerated parameters, the CCET columns of `data.csv` deviate from the published ones by at most 0.44 % (`ccet_eta_el`) and on average by less than 0.04 % over all hours of the year.
