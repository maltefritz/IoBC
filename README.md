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
