"""TESPy model of an internal combustion engine for district heating.

The model is based on TESPy Version 0.7.6 (see requirements.txt).
"""

import json
import os
from time import time

import numpy as np
import pandas as pd
from tespy.components import (CombustionEngine, CycleCloser, HeatExchanger,
                              Merge, Pump, SimpleHeatExchanger, Sink, Source,
                              Splitter)
from tespy.connections import Bus, Connection, Ref
from tespy.networks import Network
from tespy.tools.characteristics import CharLine

dirpath = os.path.dirname(os.path.abspath(__file__))


class ICE:

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
            'H2O': 0, 'CH4': 1, 'CO2': 0
            }

        self.comps = dict()
        self.conns = dict()
        self.buses = dict()

        self.nw = Network(
            T_unit='C', p_unit='bar', h_unit='kJ / kg', m_unit='kg / s'
            )

        self.eta_el = np.nan
        self.eta_th = np.nan
        self.eta_tot = np.nan

        self.solved_design = False
        self.subdirname = (
            f"ice_{abs(self.params['cons']['Q']*1e-6):g}MW"
            )
        self.design_path = os.path.join(
            dirpath, 'stable', f'{self.subdirname}_design'
            )
        self.validate_dir()


    def generate_components(self):
        """Initialize components of the internal combustion engine."""
        # Combustion Engine Sytem
        self.comps['air_in'] = Source('Air Input')
        self.comps['fuel_in'] = Source('Fuel Input')
        self.comps['ice'] = CombustionEngine('Internal Combustion Engine')
        self.comps['split_flue'] = Splitter('Flue Gas Splitter')
        self.comps['cooler'] = HeatExchanger('flue gas cooler')
        self.comps['cons'] = SimpleHeatExchanger('Consumer')
        self.comps['flue_out'] = Sink('Flue Gas Output')
        self.comps['bypass_out'] = Sink('Bypass Output')

        # Cooling water System
        self.comps['cc_cw'] = CycleCloser('Cooling Cycle Closer')
        self.comps['pump_cw'] = Pump('Cooling Water Recirculation Pump')
        self.comps['split_cw'] = Splitter('Cooling Water Splitter')
        self.comps['merge_cw'] = Merge('Cooling Water Merge')


    def generate_connections(self):
        """Initialize and add connections to network."""
        # Combustion Engine Sytem
        self.conns['A1'] = Connection(
            self.comps['air_in'], 'out1', self.comps['ice'], 'in3', 'A1'
            )
        self.conns['A2'] = Connection(
            self.comps['fuel_in'], 'out1', self.comps['ice'], 'in4', 'A2'
            )
        self.conns['A3'] = Connection(
            self.comps['ice'], 'out3', self.comps['split_flue'], 'in1', 'A3'
            )
        self.conns['A4'] = Connection(
            self.comps['split_flue'], 'out1', self.comps['cooler'], 'in1', 'A4'
            )
        self.conns['A5'] = Connection(
            self.comps['cooler'], 'out1', self.comps['flue_out'], 'in1', 'A5'
            )
        self.conns['A6'] = Connection(
            self.comps['split_flue'], 'out2', self.comps['bypass_out'], 'in1', 'A6'
            )

        # Cooling water System
        self.conns['B0'] = Connection(
            self.comps['cc_cw'], 'out1', self.comps['pump_cw'], 'in1', 'B0'
            )
        self.conns['B1'] = Connection(
            self.comps['pump_cw'], 'out1', self.comps['split_cw'], 'in1', 'B1'
            )
        self.conns['B2'] = Connection(
            self.comps['split_cw'], 'out1', self.comps['ice'], 'in1', 'B2'
            )
        self.conns['B3'] = Connection(
            self.comps['split_cw'], 'out2', self.comps['ice'], 'in2', 'B3'
            )
        self.conns['B4'] = Connection(
            self.comps['ice'], 'out1', self.comps['merge_cw'], 'in1', 'B4'
            )
        self.conns['B5'] = Connection(
            self.comps['ice'], 'out2', self.comps['merge_cw'], 'in2', 'B5'
            )
        self.conns['B6'] = Connection(
            self.comps['merge_cw'], 'out1', self.comps['cooler'], 'in2', 'B6'
            )
        self.conns['B7'] = Connection(
            self.comps['cooler'], 'out2', self.comps['cons'], 'in1', 'B7'
            )
        self.conns['B8'] = Connection(
            self.comps['cons'], 'out1', self.comps['cc_cw'], 'in1', 'B8'
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
        char_y = 1 / (np.array([
            0.01, 0.3148, 0.5346, 0.6843, 0.7835, 0.8477, 0.8885, 0.9145,
            0.9318, 0.9443, 0.9546, 0.9638, 0.9724, 0.9806, 0.9878, 0.9938,
            0.9982, 1.0009, 1.002, 1.0015, 1, 0.9977, 0.9947, 0.9909, 0.9853,
            0.9644
            ]) * 0.97)
        mot = CharLine(x=char_x, y=char_y)

        # Generator Characteristic (negative, as the engine power is negative)
        char_x = np.array([
            0.100, 0.345, 0.359, 0.383, 0.410, 0.432, 0.451, 0.504, 0.541,
            0.600, 0.684, 0.805, 1.000, 1.700, 10
            ])
        char_y = np.array([
            0.976, 0.989, 0.990, 0.991, 0.992, 0.993, 0.994, 0.995, 0.996,
            0.997, 0.998, 0.999, 1.000, 0.999, 0.99
            ]) * -0.984
        gen = CharLine(x=char_x, y=char_y)

        self.buses['net power output'] = Bus('net power output')
        self.buses['net power output'].add_comps(
            {'comp': self.comps['pump_cw'], 'char': mot},
            {'comp': self.comps['ice'], 'param': 'P', 'char': gen}
            )

        self.buses['ice power output'] = Bus('ice power output')
        self.buses['ice power output'].add_comps(
            {'comp': self.comps['ice'], 'param': 'P', 'char': gen}
            )

        self.buses['total heat output'] = Bus('total heat output')
        self.buses['total heat output'].add_comps(
            {'comp': self.comps['ice'], 'param': 'Q'},
            {'comp': self.comps['cooler']}
            )

        self.buses['ice heat input'] = Bus('ice heat input')
        self.buses['ice heat input'].add_comps(
            {'comp': self.comps['ice'], 'param': 'TI'}
            )

        self.nw.add_busses(*list(self.buses.values()))


    def design_simulation(self, **kwargs):
        """Perform parametrization and design simulation."""
        # Characteristic lines
        # Thermal input to power
        x = np.array([0.50, 0.75, 0.90, 1.00, 1.05])
        y = np.array([2.3, 2.18, 2.14, 2.1, 2.15])
        tiP_char = {'char_func': CharLine(x, y)}

        # Heat to power
        x = np.array([0.550, 0.660, 0.770, 0.880, 0.990, 1.100])
        y = np.array([0.238, 0.219, 0.203, 0.190, 0.180, 0.173])
        Q1_char = {'char_func': CharLine(x, y)}
        Q2_char = {'char_func': CharLine(x, y)}

        # Heat loss to power
        x = np.array([0.50, 0.7500, 0.90, 1.000, 1.050])
        y = np.array([0.32, 0.3067, 0.30, 0.295, 0.293])
        Qloss_char = {'char_func': CharLine(x, y)}

        # Pump isentropic efficiency
        x = np.array([
            0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2,
            1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 2.1, 2.2, 2.3, 2.4, 2.5
            ])
        y = np.array([
            0.7, 0.7667, 0.8229, 0.8698, 0.9081, 0.9387, 0.9623, 0.9796,
            0.9913, 0.9979, 1.0, 0.9981, 0.9926, 0.9839, 0.9725, 0.9586,
            0.9426, 0.9248, 0.9055, 0.8848, 0.8631, 0.8405, 0.8171, 0.7932,
            0.7689, 0.7444
            ])
        eta_s_char = {'char_func': CharLine(x, y), 'param': 'm'}

        # Flue gas cooler heat transfer
        x = np.array([
            0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1, 1.1, 1.2, 1.3,
            1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2, 2.1, 2.2, 2.3, 2.4, 2.5
            ])
        y1 = np.array([
            0.000, 0.164, 0.283, 0.389, 0.488, 0.581, 0.670, 0.756, 0.840,
            0.921, 1.000, 1.078, 1.154, 1.228, 1.302, 1.374, 1.446, 1.516,
            1.585, 1.654, 1.722, 1.789, 1.855, 1.921, 1.986, 2.051
            ])
        y2 = np.array([
            0.000, 0.245, 0.375, 0.480, 0.572, 0.655, 0.732, 0.804, 0.873,
            0.938, 1.000, 1.060, 1.118, 1.174, 1.228, 1.281, 1.332, 1.382,
            1.431, 1.479, 1.526, 1.572, 1.618, 1.662, 1.706, 1.749
            ])
        kA_char1 = {'char_func': CharLine(x, y1), 'param': 'm'}
        kA_char2 = {'char_func': CharLine(x, y2), 'param': 'm'}

        # Components
        self.comps['pump_cw'].set_attr(
            eta_s=self.params['pump_cw']['eta_s'], eta_s_char=eta_s_char,
            design=['eta_s'], offdesign=['eta_s_char']
            )
        self.comps['ice'].set_attr(
            pr1=self.params['ice']['pr1'], lamb=self.params['ice']['lamb'],
            tiP_char=tiP_char, Q1_char=Q1_char, Q2_char=Q2_char,
            Qloss_char=Qloss_char, design=['pr1'], offdesign=['zeta1']
            )
        self.comps['cooler'].set_attr(
            pr1=self.params['cooler']['pr1'],
            pr2=self.params['cooler']['pr2'],
            kA_char1=kA_char1, kA_char2=kA_char2,
            design=['pr1', 'pr2'], offdesign=['zeta1', 'zeta2', 'kA_char']
            )
        self.comps['cons'].set_attr(pr=self.params['cons']['pr'])

        # Connections
        self.conns['A1'].set_attr(
            p=self.params['A1']['p'], T=self.params['A1']['T'],
            fluid=self.fluid_vec_air
            )
        self.conns['A2'].set_attr(
            T=self.params['A2']['T'], fluid=self.fluid_vec_fuel
            )
        self.conns['A5'].set_attr(T=self.params['A5']['T'], design=['T'])
        self.conns['A6'].set_attr(m=self.params['A6']['m'])
        self.conns['B0'].set_attr(
            T=self.params['B0']['T'], p=self.params['B0']['p'],
            fluid=self.fluid_vec_water
            )
        self.conns['B7'].set_attr(T=self.params['B7']['T'])
        # Equal split of the cooling water to both engine cooling circuits
        self.conns['B2'].set_attr(m=Ref(self.conns['B3'], 1, 0))

        self.set_starting_values()

        # Solve with a fixed fuel mass flow (approx. 0.0605 kg/s per MW
        # nominal heat flow) first, then with the nominal heat flow
        self.conns['A2'].set_attr(
            m=0.0605 * abs(self.params['cons']['Q']) / 1e6
            )
        self._solve_model(**kwargs)

        self.conns['A2'].set_attr(m=None)
        self.buses['total heat output'].set_attr(P=self.params['cons']['Q'])
        self._solve_model(**kwargs)
        self.nw.save(self.design_path)
        self.solved_design = self.nw.converged

        self.Q_in_design = self.buses['ice heat input'].P.val
        self.P_design = self.comps['ice'].P.val


    def set_starting_values(self):
        """Set starting values for the design simulation.

        Without them, the solver does not converge. The mass flows are given
        per MW nominal heat flow and scaled with the actual heat flow.
        """
        m_scale = abs(self.params['cons']['Q']) / 1e6
        m0_branches = {
            1.04: ['A1'],
            0.0605: ['A2'],
            1.10: ['A3', 'A4', 'A5'],
            5.97: ['B0', 'B1', 'B6', 'B7', 'B8'],
            2.985: ['B2', 'B3', 'B4', 'B5']
            }
        for m0, labels in m0_branches.items():
            for label in labels:
                self.conns[label].set_attr(m0=m0 * m_scale)

        # Flue gas composition at lambda = 1
        fluid_vec_flue = {
            'Ar': 0.0122, 'N2': 0.7139, 'O2': 0,
            'H2O': 0.1231, 'CH4': 0, 'CO2': 0.1508
            }
        for label in ['A3', 'A4', 'A5', 'A6']:
            self.conns[label].set_attr(fluid0=fluid_vec_flue)
        for label in ['B6', 'B7', 'B8']:
            self.conns[label].set_attr(fluid0=self.fluid_vec_water)

        # Pressures in bar
        p0 = {'A2': 1.05, 'A3': 1.05, 'A4': 1.05, 'A5': 1.04, 'A6': 1.05}
        for label, p in p0.items():
            self.conns[label].set_attr(p0=p)

        # Pressures in bar and enthalpies in kJ/kg of the cooling water
        p0_h0 = {
            'B1': (10.41, 210), 'B2': (10.41, 210), 'B3': (10.41, 210),
            'B4': (10.2, 297), 'B5': (10.2, 297), 'B6': (10.2, 297),
            'B7': (10.1, 378)
            }
        for label, (p, h) in p0_h0.items():
            self.conns[label].set_attr(p0=p, h0=h)

        # Power output and heat loss of the engine are variables of the
        # system; their starting values are given in W
        self.comps['ice'].P.val = -1.44e6 * m_scale
        self.comps['ice'].Qloss.val = -0.425e6 * m_scale


    def offdesign_simulation(self, T_range=range(64, 125), **kwargs):
        """Perform offdesign simulation and derive the solph parameters.

        For each feed flow temperature, the border of the operating range is
        traversed: opening of the flue gas bypass at maximum power, reduction
        of power with opened bypass, closing of the bypass at minimum power
        and increase of power with closed bypass.

        As in the original model, the engine power is not reset to its design
        value at the beginning of each temperature. Except for the first
        temperature, the first phase therefore runs at the power of the last
        point of the previous temperature (approx. 93 % of the design power).
        The parameters of the first temperature are not stored.
        """
        if not self.solved_design:
            raise RuntimeError(
                'ICE has not been designed via the "design_simulation" '
                + 'method. Therefore the offdesign simulation will fail.'
                )

        self.comps['ice'].set_attr(P=self.P_design)
        self.buses['total heat output'].set_attr(P=None)
        self._solve_model(
            mode='offdesign', design_path=self.design_path, **kwargs
            )

        P_range = np.linspace(
            self.P_design * 0.5, self.P_design, 7, endpoint=False
            )

        solph_params = dict()
        self.QP_data = dict()

        for i, T in enumerate(T_range):
            start_time = time()
            results = []
            self.conns['B7'].set_attr(T=T)

            # Opening of the bypass at maximum power
            # The flue gas mass flow through the cooler is set at A4, as TESPy
            # assigns the mass flow variable of this branch to it
            self.conns['A6'].set_attr(m=None)
            self.conns['A4'].set_attr(m=None)
            for ratio in [0, 1/3, 1, 3, 10, 30]:
                self.conns['A6'].set_attr(m=Ref(self.conns['A4'], ratio, 0))
                results.append(self._solve_offdesign(**kwargs))
            Q_in_tl = self.buses['ice heat input'].P.val

            # Reduction of power with opened bypass
            self.conns['A6'].set_attr(m=None)
            self.conns['A4'].set_attr(m=0.01)
            for P in P_range[::-1]:
                self.comps['ice'].set_attr(P=P)
                results.append(self._solve_offdesign(**kwargs))
            Q_in_bl = self.buses['ice heat input'].P.val

            # Closing of the bypass at minimum power
            self.comps['ice'].set_attr(P=self.P_design * 0.5)
            m_bypass = np.linspace(
                0, self.conns['A6'].m.val_SI, 7, endpoint=False
                )[::-1]
            self.conns['A4'].set_attr(m=None)
            for m in m_bypass:
                self.conns['A6'].set_attr(m=m)
                results.append(self._solve_offdesign(**kwargs))
            Q_in_br = self.buses['ice heat input'].P.val

            # Increase of power with closed bypass
            self.conns['A6'].set_attr(m=0)
            for P in P_range[1:]:
                self.comps['ice'].set_attr(P=P)
                results.append(self._solve_offdesign(**kwargs))

            if i == 0:
                continue

            P, Q = np.array(results).T
            self.QP_data[T] = {
                'Q': list(Q * 1e-6), 'P': list(P * 1e-6),
                'Laufzeit': time() - start_time
                }
            solph_params[T] = self._calc_solph_params(
                P, Q, Q_in_tl, Q_in_bl, Q_in_br
                )

        self.solph_params = pd.DataFrame.from_dict(
            solph_params, orient='index'
            )


    def _solve_offdesign(self, **kwargs):
        """Solve offdesign case and return power and heat output."""
        self._solve_model(
            mode='offdesign', design_path=self.design_path, **kwargs
            )
        if not self.nw.converged:
            print(
                'Warning: Offdesign simulation did not converge '
                + f"(T_feed = {self.conns['B7'].T.val:.0f})."
                )
        return (
            abs(self.buses['net power output'].P.val),
            abs(self.buses['total heat output'].P.val)
            )


    def _calc_solph_params(self, P, Q, Q_in_tl, Q_in_bl, Q_in_br):
        """Derive solph parameters from P-Q data of one feed temperature."""
        # Flue gas loss shares at the corners of the operating range
        H_L_FG_max_tr = 1 - (P[0] + Q[0]) / Q_in_tl
        H_L_FG_min_tl = 1 - (P[5] + Q[5]) / Q_in_tl
        H_L_FG_min_bl = 1 - (P[12] + Q[12]) / Q_in_bl
        H_L_FG_max_br = 1 - (P[19] + Q[19]) / Q_in_br

        P_max_woDH = np.mean(P[:6])
        P_min_woDH = np.mean(P[13:20])

        return {
            'P_max_woDH': P_max_woDH * 1e-6,
            'eta_el_max': P_max_woDH / Q_in_tl,
            'P_min_woDH': P_min_woDH * 1e-6,
            'eta_el_min': P_min_woDH / Q_in_br,
            'H_L_FG_share_max': np.mean([H_L_FG_max_tr, H_L_FG_max_br]),
            'H_L_FG_share_min': np.mean([H_L_FG_min_tl, H_L_FG_min_bl]),
            'Q_in': self.Q_in_design * 1e-6
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
            / self.buses['ice heat input'].P.val
            )
        self.eta_th = (
            abs(self.buses['total heat output'].P.val)
            / self.buses['ice heat input'].P.val
            )
        self.eta_tot = self.eta_el + self.eta_th

        if 'print_results' in kwargs:
            if kwargs['print_results']:
                self.nw.print_results()

        if 'print_etas' in kwargs:
            print(
                f'Electrical Efficiency: {self.eta_el:.3f}\n'
                + f'Thermal Efficiency: {self.eta_th:.3f}\n'
                + f'Total Efficiency: {self.eta_tot:.3f}'
                )


    def run_model(self, **kwargs):
        """Run the initialization and design simulation routine."""
        self.generate_components()
        self.generate_connections()
        self.generate_buses()
        self.design_simulation(**kwargs)


    def validate_dir(self):
        """Check for a 'stable' directory and create it if necessary."""
        if not os.path.exists(os.path.join(dirpath, 'stable')):
            os.mkdir(os.path.join(dirpath, 'stable'))
        if not os.path.exists(os.path.join(dirpath, 'output')):
            os.mkdir(os.path.join(dirpath, 'output'))


if __name__ == '__main__':
    parampath = os.path.join(dirpath, '01_TESPy_input', 'params_ice.json')
    with open(parampath, 'r', encoding='utf-8') as file:
        params = json.load(file)

    for Q_N in [2.26, 4.28, 90]:
        params['cons']['Q'] = -Q_N * 1e6
        ice = ICE(params)
        ice.run_model(iterinfo=False)
        ice.offdesign_simulation(iterinfo=False)

        outpath = os.path.join(dirpath, 'output')
        ice.solph_params.to_csv(
            os.path.join(outpath, f'ice_parameters_{Q_N:g}.csv'), sep=';'
            )
