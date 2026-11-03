"""
TESPy model of a combined cycle with extraction turbine for distric heating.

The model is based on TESPy Version 0.7.6 (see requirements.txt). TESPy 0.7.1
fails in the first iteration due to a bug in the temperature calculation of
mixtures.
"""

import json
import os
from time import time

import numpy as np
import pandas as pd
from CoolProp.CoolProp import PropsSI as PSI
from sklearn.linear_model import LinearRegression
from tespy.components import (CombustionChamber, Compressor, Condenser,
                              CycleCloser, Drum, HeatExchanger, Merge, Pump,
                              SimpleHeatExchanger, Sink, Source, Splitter,
                              Turbine, Valve)
from tespy.connections import Bus, Connection, Ref
from tespy.networks import Network
from tespy.tools.characteristics import CharLine
from tespy.tools.characteristics import load_default_char as ldc

dirpath = os.path.dirname(os.path.abspath(__file__))


class CCET:

    def __init__(self, params):
        """Initialize model and set necessary attributes."""
        self.params = params
        self.fluid_vec_water = {
            'Ar': 0, 'N2': 0, 'O2': 0,
            'H2O': 1, 'CH4': 0, 'CO2': 0
            }
        self.fluid_vec_air = {
            'Ar': 0.0129, 'N2': 0.7553, 'O2': 0.2314,
            'H2O': 0, 'CH4': 0, 'CO2': 0.0004
            }
        self.fluid_vec_fuel = {
            'Ar': 0, 'N2': 0, 'O2': 0,
            'H2O': 0, 'CH4': 0.96, 'CO2': 0.04
            }

        self.comps = dict()
        self.conns = dict()
        self.buses = dict()

        self.nw = Network(
            fluids=[fluid for fluid in self.fluid_vec_water],
            T_unit='C', p_unit='bar', h_unit='kJ / kg',
            m_unit='kg / s'
            )

        self.eta_th = np.nan
        self.eta_el = np.nan
        self.eta_tot = np.nan
        self.epsilon = np.nan

        self.solved_design = False
        self.subdirname = (
            f"ccet_{abs(self.params['cons']['Q']*1e-6):.0f}MW"
            )
        self.design_path = os.path.join(
            dirpath, 'stable', f'{self.subdirname}_design'
            )
        self.validate_dir()


    def generate_components(self):
        """Initialize components of combined cycle with extraction turbine."""
        # Gas Turbine
        self.comps['air_in'] = Source('Air Input')
        self.comps['comp_air'] = Compressor('Air Compressor')
        self.comps['fuel_in'] = Source('Fuel Input')
        self.comps['comp_fuel'] = Compressor('Fuel Compressor')
        self.comps['comb'] = CombustionChamber('Combustion Chamber')
        self.comps['turb_gas'] = Turbine('Gas Turbine')

        # Waste Heat Recovery
        self.comps['suph'] = HeatExchanger('Superheater')
        self.comps['evap'] = HeatExchanger('Evaporator')
        self.comps['drum'] = Drum('Drum')
        self.comps['econ'] = HeatExchanger('Economizer')
        self.comps['flue_out'] = Sink('Flue Gas Output')

        # Steam Turbine
        self.comps['cc_steam'] = CycleCloser('Steam Cycle Closer')
        self.comps['turb_steam_hp'] = Turbine('Steam Turbine High Pressure')
        self.comps['mid_split'] = Splitter('Intermediate Splitter')
        self.comps['mid_valve'] = Valve('Intermediate Valve')
        self.comps['turb_steam_lp'] = Turbine('Steam Turbine Low Pressure')
        self.comps['cond_cw'] = Condenser('Cooling Water Condenser')
        self.comps['pump_cd'] = Pump('Condensate Feed Water Pump')
        self.comps['cond_dh'] = Condenser('District Heating Condenser')
        self.comps['pump_ex'] = Pump('Extraction Feed Water Pump')
        self.comps['merge'] = Merge('Merge')

        # District Heating System
        self.comps['cc_cons'] = CycleCloser('Consumer Cycle Closer')
        self.comps['pump_cons'] = Pump('Consumer Recirculation Pump')
        self.comps['cons'] = SimpleHeatExchanger('Consumer')

        # Cooling Water System
        self.comps['cw_in'] = Source('Cooling Water Input')
        self.comps['cw_out'] = Sink('Cooling Water Output')
        self.comps['pump_cw'] = Pump('Cooling Water Recirculation Pump')


    def generate_connections(self):
        """Initialize and add connections to network."""
        # Gas Turbine
        self.conns['A1'] = Connection(
            self.comps['air_in'], 'out1', self.comps['comp_air'], 'in1', 'A1'
            )
        self.conns['A2'] = Connection(
            self.comps['comp_air'], 'out1',self.comps['comb'], 'in1', 'A2'
            )
        self.conns['B1'] = Connection(
            self.comps['fuel_in'], 'out1', self.comps['comp_fuel'], 'in1', 'B1'
            )
        self.conns['B2'] = Connection(
            self.comps['comp_fuel'], 'out1', self.comps['comb'], 'in2', 'B2'
            )
        self.conns['C1'] = Connection(
            self.comps['comb'], 'out1', self.comps['turb_gas'], 'in1', 'C1'
            )
        self.conns['C2'] = Connection(
            self.comps['turb_gas'], 'out1', self.comps['suph'], 'in1', 'C2'
            )

        # Waste Heat Recovery
        # Flue Gas Side
        self.conns['C3'] = Connection(
            self.comps['suph'], 'out1', self.comps['evap'], 'in1', 'C3'
            )
        self.conns['C4'] = Connection(
            self.comps['evap'], 'out1', self.comps['econ'], 'in1', 'C4'
            )
        self.conns['C5'] = Connection(
            self.comps['econ'], 'out1', self.comps['flue_out'], 'in1', 'C5'
            )

        # Water Side
        self.conns['D0'] = Connection(
            self.comps['cc_steam'], 'out1', self.comps['econ'], 'in2', 'D0'
            )
        self.conns['D1'] = Connection(
            self.comps['econ'], 'out2', self.comps['drum'], 'in1', 'D1'
            )
        self.conns['D2'] = Connection(
            self.comps['drum'], 'out1', self.comps['evap'], 'in2', 'D2'
            )
        self.conns['D3'] = Connection(
            self.comps['evap'], 'out2', self.comps['drum'], 'in2', 'D3'
            )
        self.conns['D4'] = Connection(
            self.comps['drum'], 'out2', self.comps['suph'], 'in2', 'D4'
            )

        # Steam Turbine
        self.conns['D5'] = Connection(
            self.comps['suph'], 'out2', self.comps['turb_steam_hp'], 'in1', 'D5'
            )
        self.conns['D6'] = Connection(
            self.comps['turb_steam_hp'], 'out1', self.comps['mid_split'], 'in1', 'D6'
            )
        self.conns['D7'] = Connection(
            self.comps['mid_split'], 'out1', self.comps['mid_valve'], 'in1', 'D7'
            )
        self.conns['D8'] = Connection(
            self.comps['mid_valve'], 'out1', self.comps['turb_steam_lp'], 'in1', 'D8'
            )
        self.conns['D9'] = Connection(
            self.comps['turb_steam_lp'], 'out1', self.comps['cond_cw'], 'in1', 'D9'
            )
        self.conns['D10'] = Connection(
            self.comps['cond_cw'], 'out1', self.comps['pump_cd'], 'in1', 'D10'
            )
        self.conns['D11'] = Connection(
            self.comps['pump_cd'], 'out1', self.comps['merge'], 'in1', 'D11'
            )
        self.conns['D12'] = Connection(
            self.comps['merge'], 'out1', self.comps['cc_steam'], 'in1', 'D12'
            )
        self.conns['D13'] = Connection(
            self.comps['mid_split'], 'out2', self.comps['cond_dh'], 'in1', 'D13'
            )
        self.conns['D14'] = Connection(
            self.comps['cond_dh'], 'out1', self.comps['pump_ex'], 'in1', 'D14'
            )
        self.conns['D15'] = Connection(
            self.comps['pump_ex'], 'out1', self.comps['merge'], 'in2', 'D15'
            )

        # District Heating System
        self.conns['E0'] = Connection(
            self.comps['cons'], 'out1', self.comps['cc_cons'], 'in1', 'E0'
            )
        self.conns['E1'] = Connection(
            self.comps['cc_cons'], 'out1', self.comps['pump_cons'], 'in1', 'E1'
            )
        self.conns['E2'] = Connection(
            self.comps['pump_cons'], 'out1', self.comps['cond_dh'], 'in2', 'E2'
            )
        self.conns['E3'] = Connection(
            self.comps['cond_dh'], 'out2', self.comps['cons'], 'in1', 'E3'
            )

        # Cooling Water System
        self.conns['F1'] = Connection(
            self.comps['cw_in'], 'out1', self.comps['cond_cw'], 'in2', 'F1'
            )
        self.conns['F2'] = Connection(
            self.comps['cond_cw'], 'out2', self.comps['pump_cw'], 'in1', 'F2'
            )
        self.conns['F3'] = Connection(
            self.comps['pump_cw'], 'out1', self.comps['cw_out'], 'in1', 'F3'
            )

        self.nw.add_conns(*list(self.conns.values()))


    def generate_buses(self):
        """Initialize and add buses to network."""
        # Motor Characteristic
        char_x = np.array([
            0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55,
            0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1, 1.05, 1.1, 1.15,
            1.2, 10
            ])
        char_y = (np.array([
            0.01, 0.3148, 0.5346, 0.6843, 0.7835, 0.8477, 0.8885, 0.9145,
            0.9318, 0.9443, 0.9546, 0.9638, 0.9724, 0.9806, 0.9878, 0.9938,
            0.9982, 1.0009, 1.002, 1.0015, 1, 0.9977, 0.9947, 0.9909, 0.9853,
            0.9644
            ]) * 0.97)
        mot = CharLine(x=char_x, y=char_y)

        # Generator Characteristic
        char_x = np.array([
            0.100, 0.345, 0.359, 0.383, 0.410, 0.432, 0.451, 0.504, 0.541,
            0.600, 0.684, 0.805, 1.000, 1.700, 10
            ])
        char_y = np.array([
            0.976, 0.989, 0.990, 0.991, 0.992, 0.993, 0.994, 0.995, 0.996,
            0.997, 0.998, 0.999, 1.000, 0.999, 0.99
            ]) * 0.984
        gen = CharLine(x=char_x, y=char_y)

        self.buses['net power output'] = Bus('net power output')
        self.buses['net power output'].add_comps(
            {'comp': self.comps['turb_gas'], 'char': gen, 'base': 'component'},
            {'comp': self.comps['comp_air'], 'char': 1, 'base': 'component'},
            {'comp': self.comps['comp_fuel'], 'char': mot, 'base': 'bus'},
            {'comp': self.comps['turb_steam_hp'], 'char': gen, 'base': 'component'},
            {'comp': self.comps['turb_steam_lp'], 'char': gen, 'base': 'component'},
            {'comp': self.comps['pump_cd'], 'char': mot, 'base': 'bus'},
            {'comp': self.comps['pump_ex'], 'char': mot, 'base': 'bus'},
            {'comp': self.comps['pump_cons'], 'char': mot, 'base': 'bus'},
            {'comp': self.comps['pump_cw'], 'char': mot, 'base': 'bus'}
            )

        # Net power of the gas turbine (turbine and compressor)
        self.buses['gt power output'] = Bus('gas turbine power output')
        self.buses['gt power output'].add_comps(
            {'comp': self.comps['turb_gas'], 'base': 'component'},
            {'comp': self.comps['comp_air'], 'base': 'component'}
            )

        self.buses['cons heat output'] = Bus('cons heat output')
        self.buses['cons heat output'].add_comps(
            {'comp': self.comps['cons'], 'base': 'component'}
            )

        self.buses['cw heat output'] = Bus('cw heat cond')
        self.buses['cw heat output'].add_comps(
            {'comp': self.comps['cond_cw'], 'base': 'component'}
            )

        self.buses['heat input'] = Bus('heat input')
        self.buses['heat input'].add_comps(
            {'comp': self.comps['comb'], 'base': 'component'}
            )

        self.nw.add_busses(*list(self.buses.values()))


    def init_simulation(self, **kwargs):
        """Perform initial parametrization with starting values."""
        # Components
        self.comps['comp_air'].set_attr(
            pr=self.params['comp_air']['pr'],
            eta_s=self.params['comp_air']['eta_s']
            )
        self.comps['comp_fuel'].set_attr(
            eta_s=self.params['comp_fuel']['eta_s']
            )
        self.comps['turb_gas'].set_attr(
            eta_s=self.params['turb_gas']['eta_s']
            )
        self.comps['turb_steam_hp'].set_attr(
            eta_s=self.params['turb_steam_hp']['eta_s']
            )
        self.comps['turb_steam_lp'].set_attr(
            eta_s=self.params['turb_steam_lp']['eta_s']
            )

        self.comps['pump_ex'].set_attr(
            eta_s=self.params['pump_ex']['eta_s']
            )
        self.comps['pump_cd'].set_attr(
            eta_s=self.params['pump_cd']['eta_s']
            )
        self.comps['pump_cw'].set_attr(
            eta_s=self.params['pump_cw']['eta_s']
            )
        self.comps['pump_cons'].set_attr(
            eta_s=self.params['pump_cons']['eta_s']
            )

        self.comps['comb'].set_attr(lamb=self.params['comb']['lamb'])

        self.comps['suph'].set_attr(
            pr1=self.params['suph']['pr1'], pr2=self.params['suph']['pr2'],
            ttd_u=self.params['suph']['ttd_u']
            )
        self.comps['evap'].set_attr(
            pr1=self.params['evap']['pr1'], ttd_l=self.params['evap']['ttd_l']
            )
        self.comps['econ'].set_attr(
            pr1=self.params['econ']['pr1'], pr2=self.params['econ']['pr2']
            )
        # self.comps['cond_dh'].set_attr(
        #     pr1=self.params['cond_dh']['pr1'],
        #     pr2=self.params['cond_dh']['pr2'],
        #     ttd_u=self.params['cond_dh']['ttd_u']
        #     )
        # self.comps['cond_cw'].set_attr(
        #     pr1=self.params['cond_cw']['pr1'],
        #     pr2=self.params['cond_cw']['pr2'],
        #     ttd_u=self.params['cond_cw']['ttd_u']
        #     )
        self.comps['cond_dh'].set_attr(
            pr1=self.params['cond_dh']['pr1'],
            pr2=self.params['cond_dh']['pr2']
            )
        self.comps['cond_cw'].set_attr(
            pr1=self.params['cond_cw']['pr1'],
            pr2=self.params['cond_cw']['pr2']
            )
        self.comps['cons'].set_attr(
            pr=self.params['cons']['pr'], Q=self.params['cons']['Q'],
            dissipative=False
            )

        self.comps['mid_valve'].set_attr(pr=self.params['mid_valve']['pr'])

        # Connections
        self.conns['A1'].set_attr(
            T=self.params['A1']['T'], p=self.params['A1']['p'],
            fluid=self.fluid_vec_air
            )
        # gt_in.set_attr(T=1315)
        # gt_out.set_attr(p=1.05)
        # self.conns['B1'].set_attr(
        #     T=Ref(self.conns['A1'],1, 0), p=Ref(self.conns['A1'],1, 0),
        #     fluid=self.fluid_vec_fuel
        #     )
        self.conns['B1'].set_attr(
            T=self.params['B1']['T'], p=self.params['B1']['p'],
            fluid=self.fluid_vec_fuel
            )
        self.conns['C5'].set_attr(
            T=self.params['C5']['T'], p=self.params['C5']['p']
            )
        self.conns['D3'].set_attr(
            m=Ref(self.conns['D4'], self.params['D3']['m_rel'], 0)
            )
        self.conns['D5'].set_attr(
            p=self.params['D5']['p'], fluid=self.fluid_vec_water
            )
        # mp.set_attr(p=5, design=['p'])
        self.conns['D8'].set_attr(
            m=Ref(self.conns['D6'], self.params['D8']['m_rel'], 0)
            )
        # lp_ws.set_attr(p=0.8, design=['p'])

        # District Heating System
        self.conns['E0'].set_attr(
            T=self.params['E0']['T'], fluid=self.fluid_vec_water
            )
        self.conns['E3'].set_attr(
            T=self.params['E3']['T'], p=self.params['E3']['p']
            )

        # Cooling Water System
        self.conns['F1'].set_attr(
            T=self.params['F1']['T'], p=self.params['F1']['p'],
            fluid=self.fluid_vec_water
            )
        self.conns['F3'].set_attr(
            T=self.params['F3']['T'], p=Ref(self.conns['F1'], 1, 0)
            )

        # STARTING VALUES
        p_cond_dh = PSI(
            'P', 'Q', 0, 'T',
            self.params['E3']['T'] + self.params['cond_dh']['ttd_u'] + 273.15,
            'water'
            ) * 1e-5
        p_cond_cw = PSI(
            'P', 'Q', 0, 'T',
            self.params['F3']['T'] + self.params['cond_cw']['ttd_u'] + 273.15,
            'water'
            ) * 1e-5
        self.conns['D14'].set_attr(p=p_cond_dh)
        self.conns['D10'].set_attr(p=p_cond_cw)
        self.set_starting_values()

        # Decouple gas turbine and steam cycle in the first solve by fixing
        # the air mass flow instead of the flue gas outlet temperature
        self.conns['A1'].set_attr(m=self.conns['A1'].m.val0)
        self.conns['C5'].set_attr(T=None)
        self._solve_model(**kwargs)

        self.conns['A1'].set_attr(m=None)
        self.conns['C5'].set_attr(T=self.params['C5']['T'])
        self._solve_model(**kwargs)

        self.conns['D14'].set_attr(p=None)
        self.conns['D10'].set_attr(p=None)
        self.comps['cond_dh'].set_attr(ttd_u=self.params['cond_dh']['ttd_u'])
        self.comps['cond_cw'].set_attr(ttd_u=self.params['cond_cw']['ttd_u'])

        # Design case 1
        self._solve_model(**kwargs)
        self.nw.save(f'{self.design_path}_maxQ')

        self.gt_power_design = self.buses['gt power output'].P.val
        self.m_lp_min = self.conns['D8'].m.val

        # Design case 2
        self.buses['gt power output'].set_attr(P=self.gt_power_design)
        # Set design and offdesign parameters before, so that the components
        # with local offdesign are switched to their offdesign parameters
        self.set_offdesign_attrs()
        # Minimum heat flow of 10 MW, independent of the nominal heat flow
        self.Q_min = -10e6
        self.comps['cons'].set_attr(Q=self.Q_min)

        self.comps['cond_dh'].set_attr(
            local_offdesign=True, design_path=f'{self.design_path}_maxQ'
            )
        self.comps['pump_ex'].set_attr(
            local_offdesign=True, design_path=f'{self.design_path}_maxQ'
            )
        self.conns['D13'].set_attr(
            local_offdesign=True, design_path=f'{self.design_path}_maxQ'
            )
        self.conns['D14'].set_attr(
            local_offdesign=True, design_path=f'{self.design_path}_maxQ'
            )
        self.conns['D15'].set_attr(
            local_offdesign=True, design_path=f'{self.design_path}_maxQ'
            )
        self.comps['cons'].set_attr(
            local_offdesign=True, design_path=f'{self.design_path}_maxQ'
            )
        self.comps['pump_cons'].set_attr(
            local_offdesign=True, design_path=f'{self.design_path}_maxQ'
            )
        self.conns['E0'].set_attr(
            local_offdesign=True, design_path=f'{self.design_path}_maxQ'
            )
        self.conns['E1'].set_attr(
            local_offdesign=True, design_path=f'{self.design_path}_maxQ'
            )
        self.conns['E2'].set_attr(
            local_offdesign=True, design_path=f'{self.design_path}_maxQ'
            )
        self.conns['E3'].set_attr(
            local_offdesign=True, design_path=f'{self.design_path}_maxQ'
            )

        self.conns['D8'].set_attr(m=None)

        self._solve_model(design_path=f'{self.design_path}_maxQ', **kwargs)

        self.nw.save(f'{self.design_path}_minQ')

        self.m_lp_max = self.conns['D8'].m.val
        self.solved_design = True


    def set_starting_values(self):
        """Set starting values for the first simulation.

        Without them, TESPy initializes the mass flows randomly and the
        solver does not converge reliably. The mass flows are estimated for a
        consumer heat flow of 50 MW and scaled with the actual heat flow.
        """
        m_scale = abs(self.params['cons']['Q']) / 50e6
        m0_branches = {
            157: ['A1', 'A2'],
            3.8: ['B1', 'B2'],
            161: ['C1', 'C2', 'C3', 'C4', 'C5'],
            29: ['D0', 'D1', 'D4', 'D5', 'D6', 'D12'],
            116: ['D2', 'D3'],
            5.8: ['D7', 'D8', 'D9', 'D10', 'D11'],
            23.2: ['D13', 'D14', 'D15'],
            300: ['E0', 'E1', 'E2', 'E3'],
            189: ['F1', 'F2', 'F3']
            }
        for m0, labels in m0_branches.items():
            for label in labels:
                self.conns[label].set_attr(m0=m0 * m_scale)

        # Flue gas composition at lambda = 2.5
        fluid_vec_flue = {
            'Ar': 0.0126, 'N2': 0.7375, 'O2': 0.1356,
            'H2O': 0.0509, 'CH4': 0, 'CO2': 0.0635
            }
        for label in ['C1', 'C2', 'C3', 'C4', 'C5']:
            self.conns[label].set_attr(fluid0=fluid_vec_flue)
        self.conns['D12'].set_attr(fluid0=self.fluid_vec_water)

        # Steam cycle enthalpies in kJ/kg
        h0 = {
            'D1': 1765, 'D3': 1821, 'D5': 3497, 'D6': 2540, 'D7': 2540,
            'D8': 2540, 'D9': 2200, 'D13': 2540
            }
        for label, h in h0.items():
            self.conns[label].set_attr(h0=h)


    def design_simulation(self, **kwargs):
        """Perform final parametrization and design simulation."""
        pass


    def set_offdesign_attrs(self):
        """Set design and offdesign parameters of components and connections."""
        # Characteristic lines
        char_x = np.array([0.000, 0.400, 1.000, 1.600, 2.000])
        char_y = np.array([0.500, 0.900, 1.000, 1.050, 0.9500])
        eta_s_char_comp = CharLine(x=char_x, y=char_y)

        char_x = np.array([
            0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2,
            1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 2.1, 2.2, 2.3, 2.4, 2.5
            ])
        char_y = np.array([
            0.7, 0.7667, 0.8229, 0.8698, 0.9081, 0.9387, 0.9623, 0.9796,
            0.9913, 0.9979, 1.0, 0.9981, 0.9926, 0.9839, 0.9725, 0.9586,
            0.9426, 0.9248, 0.9055, 0.8848, 0.8631, 0.8405, 0.8171, 0.7932,
            0.7689, 0.7444
            ])
        eta_s_char_gt = CharLine(x=char_x, y=char_y)

        eta_s_char_st = ldc('turbine', 'eta_s_char', 'TRAUPEL', CharLine)

        char_x = np.array([
            0, 0.0625, 0.125, 0.1875, 0.25, 0.3125, 0.375, 0.4375, 0.5,
            0.5625, 0.6375, 0.7125, 0.7875, 0.9, 0.9875, 1, 1.0625, 1.125,
            1.175, 1.2125, 1.2375, 1.25, 1.5
            ])
        char_y = np.array([
            0.008, 0.139, 0.273, 0.400, 0.519, 0.626, 0.722, 0.806, 0.875,
            0.931, 0.973, 1.001, 1.020, 1.016, 1.005, 1.000, 0.975, 0.929,
            0.883, 0.838, 0.784, 0.761, 0.2
            ])
        eta_s_char_pump = CharLine(x=char_x, y=char_y)

        char_x = np.array([
            0, 0.0001, 0.001, 0.01, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8,
            0.9, 1.0, 2.0
            ])
        char_y = np.array([
            0.025, 0.05, 0.1, 0.2, 0.4, 0.85, 0.89, 0.92, 0.945, 0.965, 0.98,
            0.99, 0.995, 1.000, 1.05
            ])
        kA_char1_cond_dh = CharLine(x=char_x, y=char_y)

        # Components
        self.comps['comp_air'].set_attr(
            eta_s_char={'char_func': eta_s_char_comp, 'param': 'm'},
            design=['pr', 'eta_s'], offdesign=['eta_s_char']
            )
        self.comps['comp_fuel'].set_attr(
            eta_s_char={'char_func': eta_s_char_comp, 'param': 'm'},
            design=['eta_s'], offdesign=['eta_s_char']
            )
        self.comps['turb_gas'].set_attr(
            eta_s_char={'char_func': eta_s_char_gt, 'param': 'm'},
            design=['eta_s'], offdesign=['eta_s_char', 'cone']
            )
        self.comps['turb_steam_hp'].set_attr(
            eta_s_char={'char_func': eta_s_char_st},
            design=['eta_s'], offdesign=['eta_s_char', 'cone']
            )
        self.comps['turb_steam_lp'].set_attr(
            eta_s_char={'char_func': eta_s_char_st},
            design=['eta_s'], offdesign=['eta_s_char', 'cone']
            )

        self.comps['pump_ex'].set_attr(
            eta_s_char={'char_func': eta_s_char_pump, 'param': 'm'},
            design=['eta_s'], offdesign=['eta_s_char']
            )
        self.comps['pump_cd'].set_attr(
            eta_s_char={'char_func': eta_s_char_pump, 'param': 'm'},
            design=['eta_s'], offdesign=['eta_s_char']
            )
        self.comps['pump_cw'].set_attr(
            design=['eta_s'], offdesign=['eta_s_char']
            )
        self.comps['pump_cons'].set_attr(
            design=['eta_s'], offdesign=['eta_s_char']
            )

        self.comps['suph'].set_attr(
            design=['pr1', 'pr2', 'ttd_u'],
            offdesign=['zeta1', 'zeta2', 'kA_char']
            )
        self.comps['evap'].set_attr(
            design=['pr1', 'ttd_l'], offdesign=['zeta1', 'kA_char']
            )
        self.comps['econ'].set_attr(
            design=['pr1', 'pr2'], offdesign=['zeta1', 'zeta2', 'kA_char']
            )
        self.comps['cond_dh'].set_attr(
            kA_char1={'char_func': kA_char1_cond_dh, 'param': 'm'},
            design=['ttd_u', 'pr2'], offdesign=['zeta2', 'kA_char']
            )
        self.comps['cond_cw'].set_attr(
            design=['ttd_u', 'pr2'], offdesign=['zeta2', 'kA_char']
            )

        self.comps['mid_valve'].set_attr(design=['pr'])

        # Connections
        self.conns['C5'].set_attr(design=['T'])
        self.conns['D5'].set_attr(design=['p'])

        # The cooling water mass flow is fixed at F1, as TESPy assigns the
        # mass flow variable of the cooling water branch to it
        self.conns['F1'].set_attr(offdesign=['m'])
        self.conns['F3'].set_attr(design=['T'])


    def offdesign_simulation(self, T_range=range(66, 125), **kwargs):
        """Perform offdesign simulation and derive the solph parameters.

        For each feed flow temperature in T_range, the border of the operating
        range is traversed: from minimum to maximum heat extraction at maximum
        gas turbine power, from maximum to minimum gas turbine power at
        maximum heat extraction and back to minimum heat extraction at minimum
        gas turbine power.
        """
        if not self.solved_design:
            raise RuntimeError(
                'CCET has not been designed via the "init_simulation" '
                + 'method. Therefore the offdesign simulation will fail.'
                )

        design_path = f'{self.design_path}_minQ'
        Q_N = self.params['cons']['Q']

        # No heat, full power
        self._solve_model(mode='offdesign', design_path=design_path, **kwargs)

        solph_params = dict()
        self.QP_data = dict()

        for T in T_range:
            start_time = time()
            results = []
            self.conns['E3'].set_attr(T=T)

            # From minimum to maximum heat extraction at maximum gt power
            # Intermediate steps (not recorded) limit the step size to 10 MW
            # for numerical stability
            self.buses['gt power output'].set_attr(P=self.gt_power_design)
            n_sub = int(np.ceil(abs(Q_N - self.Q_min) / 6 / 10e6))
            for i, Q in enumerate(
                    np.linspace(self.Q_min, Q_N, num=6 * n_sub + 1)):
                self.comps['cons'].set_attr(Q=Q)
                if i % n_sub == 0:
                    results.append(
                        self._solve_offdesign(design_path, **kwargs)
                        )
                else:
                    self._solve_model(
                        mode='offdesign', design_path=design_path, **kwargs
                        )

            # From maximum to minimum gt power at maximum heat extraction
            # The low pressure mass flow is fixed at D7, as TESPy assigns the
            # mass flow variable of the low pressure branch to it
            self.comps['cons'].set_attr(Q=None)
            self.conns['D7'].set_attr(m=self.conns['D7'].m.val)
            self._solve_model(
                mode='offdesign', design_path=design_path, **kwargs
                )
            for load in np.linspace(0.9, 0.3, num=7):
                self.buses['gt power output'].set_attr(
                    P=self.gt_power_design * load
                    )
                results.append(self._solve_offdesign(design_path, **kwargs))

            # From maximum to minimum heat extraction at minimum gt power
            self.conns['D7'].set_attr(m=None)
            Q_max = self.comps['cons'].Q.val
            for Q in np.linspace(Q_max, -1e5, num=9, endpoint=False):
                self.comps['cons'].set_attr(Q=Q)
                results.append(self._solve_offdesign(design_path, **kwargs))

            P, Q, Q_in = np.array(results).T
            self.QP_data[T] = {
                'Q': list(Q * 1e-6), 'P': list(P * 1e-6),
                'Laufzeit': time() - start_time
                }
            solph_params[T] = self._calc_solph_params(P, Q, Q_in)

        self.solph_params = pd.DataFrame.from_dict(
            solph_params, orient='index'
            )


    def _solve_offdesign(self, design_path, **kwargs):
        """Solve offdesign case and return power, heat and fuel heat input."""
        self._solve_model(mode='offdesign', design_path=design_path, **kwargs)
        if not self.nw.converged:
            print(
                'Warning: Offdesign simulation did not converge '
                + f"(T_feed = {self.conns['E3'].T.val:.0f})."
                )
        return (
            abs(self.buses['net power output'].P.val),
            abs(self.buses['cons heat output'].P.val),
            self.buses['heat input'].P.val
            )


    @staticmethod
    def _intercept(x, y):
        """Return intercept of the linear regression of y over x."""
        x = np.array(x).reshape((-1, 1))
        return LinearRegression().fit(x, y).intercept_


    def _calc_solph_params(self, P, Q, Q_in):
        """Derive solph parameters from P-Q data of one feed temperature."""
        # Extrapolation of upper (maximum gt power) and lower (minimum gt
        # power) border to operation without heat extraction
        P_max_woDH = self._intercept(Q[4:7], P[4:7])
        P_min_woDH = self._intercept(Q[14:], P[14:])
        Q_in_max = self._intercept(Q[4:7], Q_in[4:7])
        Q_in_min = self._intercept(Q[14:], Q_in[14:])

        # Points of maximum heat extraction (top right and bottom right)
        P_t_r, Q_t_r, Q_in_t_r = P[6], Q[6], Q_in[6]
        P_b_r, Q_b_r, Q_in_b_r = P[13], Q[13], Q_in[13]

        ratio = (Q_b_r - Q_t_r + P_b_r - P_t_r) / (Q_in_b_r - Q_in_t_r)
        beta_top = abs((P_t_r - P_max_woDH) / Q_t_r)
        beta_bottom = abs((P_b_r - P_min_woDH) / Q_b_r)

        return {
            'ccet_P_max_woDH': P_max_woDH * 1e-6,
            'ccet_eta_el_max': P_max_woDH / Q_in_max,
            'ccet_P_min_woDH': P_min_woDH * 1e-6,
            'ccet_eta_el_min': P_min_woDH / Q_in_min,
            'ccet_H_L_FG_share_max': 1 - ratio,
            'ccet_Q_CW_min': Q_in_t_r * ratio - P_t_r - Q_t_r,
            'ccet_beta': (beta_top + beta_bottom) / 2,
            'ccet_Q_in': Q_in_max * 1e-6
            }


    def _solve_model(self, **kwargs):
        """Solve the model (in design mode by default)."""
        if 'iterinfo' in kwargs:
            self.nw.set_attr(iterinfo=kwargs['iterinfo'])
        self.nw.solve(
            kwargs.get('mode', 'design'),
            kwargs.get('init_path', None),
            kwargs.get('design_path', None)
            )
        self.eta_el = (
            abs(self.buses['net power output'].P.val)
            / self.buses['heat input'].P.val
            )
        self.eta_th = (
            abs(self.buses['cons heat output'].P.val)
            / self.buses['heat input'].P.val
            )
        self.eta_tot = self.eta_th + self.eta_el

        if 'print_results' in kwargs:
            if kwargs['print_results']:
                self.nw.print_results()
        # if self.nw.residual_history[-1] < 1e-3:
        # if self.nw.res[-1] < 1e-3:
        #     self.solved_design = True
        #     self.nw.save(self.design_path)

        if 'print_etas' in kwargs:
            print(f'Thermal Efficiency = {self.eta_th:.3f}')
            print(f'Electrical Efficiency = {self.eta_el:.3f}')
            print(f'Total Efficiency = {self.eta_tot:.3f}')


    def run_model(self, **kwargs):
        """Run the initialization and design simulation routine."""
        self.generate_components()
        self.generate_connections()
        self.generate_buses()
        self.init_simulation(**kwargs)
        self.design_simulation(**kwargs)


    def validate_dir(self):
        """Check for a 'stable' directory and create it if necessary."""
        if not os.path.exists(os.path.join(dirpath, 'stable')):
            os.mkdir(os.path.join(dirpath, 'stable'))
        if not os.path.exists(os.path.join(dirpath, 'output')):
            os.mkdir(os.path.join(dirpath, 'output'))


if __name__ == '__main__':
    parampath = os.path.join(dirpath, '01_TESPy_input', 'params_ccet.json')
    with open(parampath, 'r', encoding='utf-8') as file:
        params = json.load(file)

    for Q_N in [70, 189]:
        params['cons']['Q'] = -Q_N * 1e6
        ccet = CCET(params)
        ccet.run_model(iterinfo=False)
        ccet.offdesign_simulation(iterinfo=False)

        outpath = os.path.join(dirpath, 'output')
        ccet.solph_params.to_csv(
            os.path.join(outpath, f'ccet_parameters_{Q_N}.csv'), sep=';'
            )
