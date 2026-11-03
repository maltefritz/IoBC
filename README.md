# Overview

This repository contains additional information and data relating to the publication “Impact of techno-economic and political boundary conditions on the integration of heat pumps into multivalent district heating systems” by authors M. Fritz, J. Freißmann, and I. Tuschy. It serves to enable the reproduction of the results achieved.

# Description of contents

## Optimization

This folder contains the files for carrying out the combined design and dispatch optimization. This requires auxiliary files such as those for the economic functions and helpers. It also contains a postprocessing file for processing the results. In addition to control files, the folders for the various district heating systems (primary network and 4GDH network) are also stored.

### Primary and IVgdh network

This folder contains the input and output data for the destrict heating systems being considered.

**Please note**: The results of the IIIgdh network are stored in this repository as the primary network, since they are based on research results of “Hochtemperaturwärmepumpen in der Nah- und Fernwärmeversorgung - Technologieperspektive für den kurz- und mittelfristigen Einsatz in multivalenten Systemen” (see: [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.13946407.svg)](https://doi.org/10.5281/zenodo.13946407))

### Input data

This folder contains the necessary input data for the combined design and dispatch optimization. Generally, this includes a JSON file of the constant parameters (no variation throughout the observed period) and a CSV file of the time dependent data.

### Output data

This folder contains the output data of the combined design and dispatch optimization. For each subsidy and sensenstivity analysis, there are the unit commitment time series, as well as key parameters and unit cost. Additionally, the results are visualized in plots, that allow an even more detailed analysis than provided in the paper.

## Models

This folder contains the TESPy models of the plants from which the characteristics for the combined design and dispatch optimization are derived. Each model folder contains a README file describing the workflow and a requirements file listing the necessary Python packages.

### CCET and ICE

These folders contain the models of the combined cycle power plant with an extraction condensing turbine (CCET) of the IIIgdh network and of the internal combustion engine (ICE) of the IVgdh network.

### HP

This folder contains the model of the heat pump with parallel compression and open economizer (working fluid R717), from which the heat pump parameters of both district heating systems were derived.

**Please note**: The model stems from the project [heatpumps](https://github.com/jfreissmann/heatpumps).

### Input data

The folders `01_TESPy_input` (CCET and ICE) and `input` (HP) contain the parameters of the models.

### Output data

The folder `02_TESPy_output` (CCET and ICE) contains the parameter data sets of the plants for each feed flow temperature as well as the hourly time series to which they are added. The script `conversion.py` converts the parameter data sets into time series and writes the result to `03_solph_param_input`. The heat pump parameters are part of the input data of the optimization.
