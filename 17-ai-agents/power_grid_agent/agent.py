import pandapower as pp
import pandapower.optimal_powerflow as opf

class PowerGridAgent:
    """Agent to read a PSSE RAW file, run contingency analysis and optimize generation."""

    def __init__(self, case_path: str):
        self.case_path = case_path
        self.net = self._read_psse(case_path)

    def _read_psse(self, path):
        """Minimal PSSE RAW parser for demonstration. Only handles a subset of the format."""
        net = pp.create_empty_network()
        bus_lookup = {}
        section = None
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith('0') and 'END OF BUS DATA' in line:
                    section = 'load'
                    continue
                if line.startswith('0') and 'END OF LOAD DATA' in line:
                    section = 'gen'
                    continue
                if line.startswith('0') and 'END OF GENERATOR DATA' in line:
                    section = 'branch'
                    continue
                if line.startswith('0') and 'END OF BRANCH DATA' in line:
                    break
                if section is None:
                    if '/' in line:
                        continue
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) < 4:
                        continue
                    bus_i = int(parts[0])
                    name = parts[1].strip("'")
                    basekv = float(parts[2])
                    btype = int(parts[3])
                    b = pp.create_bus(net, vn_kv=basekv, name=name)
                    bus_lookup[bus_i] = b
                    if btype == 3:
                        pp.create_ext_grid(net, b)
                elif section == 'load':
                    parts = [p.strip() for p in line.split(',')]
                    bus_i = int(parts[0])
                    p_mw = float(parts[5])
                    q_mvar = float(parts[6])
                    pp.create_load(net, bus_lookup[bus_i], p_mw=p_mw, q_mvar=q_mvar)
                elif section == 'gen':
                    parts = [p.strip() for p in line.split(',')]
                    bus_i = int(parts[0])
                    p_mw = float(parts[2])
                    pp.create_gen(net, bus_lookup[bus_i], p_mw=p_mw, vm_pu=1.0,
                                   min_p_mw=0, max_p_mw=p_mw + 50)
                    gen_idx = net.gen.index[-1]
                    pp.create_poly_cost(net, gen_idx, 'gen', cp1_eur_per_mw=10)
                elif section == 'branch':
                    parts = [p.strip() for p in line.split(',')]
                    from_bus = bus_lookup[int(parts[0])]
                    to_bus = bus_lookup[int(parts[1])]
                    r = float(parts[3])
                    x = float(parts[4])
                    b = float(parts[5])
                    pp.create_line_from_parameters(net, from_bus, to_bus, length_km=1.0,
                                                   r_ohm_per_km=r, x_ohm_per_km=x,
                                                   c_nf_per_km=b * 1e9, max_i_ka=1.0)
        return net

    def contingency_analysis(self):
        """Simulate single line outages and return max loading percentage for each."""
        results = {}
        for line_idx in list(self.net.line.index):
            self.net.line.at[line_idx, 'in_service'] = False
            try:
                pp.runpp(self.net)
                results[f'line_{line_idx}'] = self.net.res_line.loading_percent.max()
            except Exception:
                results[f'line_{line_idx}'] = None
            self.net.line.at[line_idx, 'in_service'] = True
        return results

    def optimize_generation(self):
        """Run an optimal power flow to optimize generation pattern."""
        pp.runopp(self.net)
        return self.net.res_gen.p_mw

if __name__ == '__main__':
    import argparse, json
    parser = argparse.ArgumentParser(description='Run contingency analysis and OPF on PSSE case.')
    parser.add_argument('case', help='Path to PSSE RAW case')
    args = parser.parse_args()

    agent = PowerGridAgent(args.case)
    pp.runpp(agent.net)
    print('Base case line loadings:', agent.net.res_line.loading_percent.values)
    cont = agent.contingency_analysis()
    print('Contingency results:', json.dumps(cont))
    opt = agent.optimize_generation()
    print('Optimized generation:', opt.values)
