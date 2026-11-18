import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib import rcParams

# --- Academic Plotting Configuration ---
rcParams['font.family'] = 'serif'
rcParams['font.serif'] = ['Times New Roman']
rcParams['axes.unicode_minus'] = False
rcParams['xtick.direction'] = 'in'
rcParams['ytick.direction'] = 'in'


class PY_Library:
    """Analytical and empirical p-y curve formulations for laterally loaded piles in sand."""
    
    def __init__(self, z, D, Dr, phi=31, gamma=15):
        self.z = max(z, 0.01)
        self.D = D
        self.Dr = Dr
        self.gamma = gamma
        self.sigma_v = self.gamma * self.z  # Effective vertical stress (kPa)
        
        phi_rad = np.radians(phi)
        c2 = np.tan(np.radians(45 + phi / 2)) ** 2
        c1 = c2 * np.tan(phi_rad)
        sf = 1.0 + 0.35 * (D / 2.0)  # Shape/diameter correction factor
        self.pu = sf * min((c1 * self.z + c2 * D) * self.gamma * self.z, c2 * D * self.gamma * self.z)

    def get_k_ini(self, m_name):
        """Calculate initial subgrade reaction modulus (kN/m^3) for selected models."""
        if m_name == "API (1983)":
            return (8000 if self.Dr <= 20 else 25000) * self.z
        elif m_name == "Hyperbolic":
            return 18000 * self.z
        elif m_name == "Zhang (2020)":
            return 18000 * (self.z / self.D) ** 0.4
        return None

    def get_p(self, m_name, y):
        """Compute lateral soil resistance p (kN/m) at lateral displacement y (m)."""
        eps = 1e-9
        if y <= 0:
            return 0
        if m_name == "API (1983)":
            k = 8000 if self.Dr <= 20 else 25000
            A = max(0.9, 3.0 - 0.8 * (self.z / self.D))
            return A * self.pu * np.tanh((k * self.z * y) / (A * self.pu + eps))
        elif m_name == "Reese (1974)":
            y_u = 3 * self.D / 80
            return self.pu * (y / y_u) ** 0.333 if y < y_u else self.pu
        elif m_name == "Hyperbolic":
            ki = 18000 * self.z
            return y / (1 / (ki + eps) + y / (self.pu + eps))
        elif m_name == "Jeanjean (2009)":
            k_j = 12000 * (self.z ** 0.5) * (self.D ** 0.5)
            return self.pu * (1 - np.exp(-k_j * y / (self.pu + eps)))
        elif m_name == "Zhang (2020)":
            n = 0.5 + self.z / (10 * self.D)
            k_z = 18000 * (self.z / self.D) ** 0.4
            return self.pu * (y / (y + self.pu / (k_z + eps))) ** n
        elif m_name == "Stevens (1979)":
            y50 = 0.005 * self.D
            return 0.5 * self.pu * (y / y50) ** 0.5 if y < y50 else self.pu
        return 0


class WeiSandApp:
    """GUI Application for benchmarking FEA-derived p-y curves against theoretical formulations."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("WeiSand p-y Visualizer v1.0 | Dimensionless & Stiffness Benchmarking")
        self.root.geometry("1550x950")
        
        # Line styles to distinguish analytical models
        self.line_styles = {
            "API (1983)": "-",
            "Reese (1974)": "--",
            "Hyperbolic": "-.",
            "Jeanjean (2009)": ":",
            "Zhang (2020)": (0, (3, 1, 1, 1)),
            "Stevens (1979)": (0, (5, 10))
        }
        self.markers = ['o', 's', '^', 'D', 'v', 'p', '*', 'h']
        
        # Default relative path for sample dataset
        self.default_data_path = os.path.join(os.path.dirname(__file__), "All_Cases_PY_Results.xlsx")
        self.data_path = self.default_data_path
        
        self.depth_mode = tk.StringVar(value="z/L")
        self.is_norm = tk.BooleanVar(value=False)  # Dimensionless normalization toggle
        self.show_k = tk.BooleanVar(value=False)   # Initial tangent stiffness toggle
        
        self.df_meta = pd.DataFrame()
        self.sheets = {}
        
        self.load_data()
        self.setup_ui()

    def load_data(self):
        """Load finite element p-y dataset from Excel workbook."""
        if not os.path.exists(self.data_path):
            selected_file = filedialog.askopenfilename(
                title="Select FEA p-y Results Excel File",
                filetypes=[("Excel files", "*.xlsx *.xls")]
            )
            if selected_file:
                self.data_path = selected_file
            else:
                messagebox.showwarning("Data Missing", "No dataset loaded. Please select a valid Excel file via 'Load Dataset'.")
                return

        try:
            self.sheets = pd.read_excel(self.data_path, sheet_name=None)
            parsed = []
            for n in self.sheets.keys():
                if "Index" in n:
                    continue
                match = re.search(r'D(\d+)L(\d+)Dr(\d+)', n)
                if match:
                    d, l, dr = map(int, match.groups())
                    parsed.append({'name': n, 'D': d, 'L': l, 'Dr': dr, 'LD': l / d})
            self.df_meta = pd.DataFrame(parsed)
        except Exception as e:
            messagebox.showerror("Load Error", f"Failed to parse Excel file:\n{str(e)}")

    def reload_dataset(self):
        """Allow users to dynamically load a new Excel dataset from the UI."""
        selected_file = filedialog.askopenfilename(
            title="Select FEA p-y Results Excel File",
            filetypes=[("Excel files", "*.xlsx *.xls")]
        )
        if selected_file:
            self.data_path = selected_file
            self.load_data()
            self.refresh_listboxes()
            self.run_plot()

    def refresh_listboxes(self):
        """Populate parameter listboxes with unique values from the loaded dataset."""
        if self.df_meta.empty:
            return
        for lb, col in [(self.lb_d, "D"), (self.lb_ld, "LD"), (self.lb_dr, "Dr")]:
            lb.delete(0, tk.END)
            for v in sorted(self.df_meta[col].unique()):
                lb.insert(tk.END, v)

    def setup_ui(self):
        """Construct the control sidebar and Matplotlib visualization canvas."""
        side = ttk.Frame(self.root, padding=10)
        side.pack(side=tk.LEFT, fill=tk.Y)

        # Dataset loader button
        ttk.Button(side, text="Load FEA Dataset (.xlsx)", command=self.reload_dataset).pack(fill=tk.X, pady=(0, 10))

        # 1. Geometric & Soil Parameter Listboxes
        self.lb_d = self.create_lb(side, "Pile Diameter D (m)", "D", h=8)
        self.lb_ld = self.create_lb(side, "Aspect Ratio L/D", "LD", h=5)
        self.lb_dr = self.create_lb(side, "Relative Density Dr (%)", "Dr", h=5)

        # 2. Analysis Mode Controls
        ttk.Label(side, text="\nAnalysis Controls:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        ttk.Checkbutton(side, text="Dimensionless (y/D, p/σ'vD)", variable=self.is_norm, command=self.run_plot).pack(anchor=tk.W)
        ttk.Checkbutton(side, text="Show Initial Tangent Stiffness", variable=self.show_k, command=self.run_plot).pack(anchor=tk.W)
        
        m_frame = ttk.Frame(side)
        m_frame.pack(fill=tk.X, pady=5)
        ttk.Radiobutton(m_frame, text="Normalized Depth (z/L)", variable=self.depth_mode, value="z/L", command=self.run_plot).pack(side=tk.LEFT)
        ttk.Radiobutton(m_frame, text="z/D", variable=self.depth_mode, value="z/D", command=self.run_plot).pack(side=tk.LEFT, padx=10)

        self.zl_s = tk.Scale(side, from_=0, to=1, resolution=0.01, orient=tk.HORIZONTAL, length=240, command=lambda x: self.run_plot())
        self.zl_s.set(0.2)
        self.zl_s.pack()

        # 3. Theoretical Formulations
        ttk.Label(side, text="\nTheoretical Formulations:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        self.m_names = list(self.line_styles.keys())
        self.m_vars = {n: tk.BooleanVar(value=(n in ["API (1983)", "Zhang (2020)"])) for n in self.m_names}
        for n in self.m_names:
            ttk.Checkbutton(side, text=n, variable=self.m_vars[n], command=self.run_plot).pack(anchor=tk.W)

        # Matplotlib Canvas
        self.fig, self.ax = plt.subplots(figsize=(10, 8), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    def create_lb(self, parent, label_text, col, h):
        """Helper method to generate multi-select parameter listboxes."""
        ttk.Label(parent, text=label_text).pack(anchor=tk.W)
        lb = tk.Listbox(parent, selectmode=tk.MULTIPLE, height=h, exportselection=0, width=32)
        if not self.df_meta.empty and col in self.df_meta.columns:
            for v in sorted(self.df_meta[col].unique()):
                lb.insert(tk.END, v)
        lb.bind('<<ListboxSelect>>', lambda e: self.run_plot())
        lb.pack(fill=tk.X, pady=2)
        return lb

    def run_plot(self):
        """Update the p-y curve comparison plot based on current UI selections."""
        if self.df_meta.empty:
            return
            
        self.ax.clear()
        self.ax.tick_params(direction='in', top=True, right=True, which='both')
        
        try:
            sel_d = [float(self.lb_d.get(i)) for i in self.lb_d.curselection()]
            sel_ld = [float(self.lb_ld.get(i)) for i in self.lb_ld.curselection()]
            sel_dr = [float(self.lb_dr.get(i)) for i in self.lb_dr.curselection()]
            if not (sel_d and sel_ld and sel_dr):
                self.canvas.draw_idle()
                return
            
            norm = self.is_norm.get()
            targets = self.df_meta[
                self.df_meta['D'].isin(sel_d) & 
                self.df_meta['LD'].isin(sel_ld) & 
                self.df_meta['Dr'].isin(sel_dr)
            ]
            colors = plt.colormaps['tab10'].colors

            for i, (_, row) in enumerate(targets.iterrows()):
                df = self.sheets[row['name']]
                mode, val = self.depth_mode.get(), self.zl_s.get()
                idx = (df['z_L'] - val).abs().idxmin() if mode == "z/L" else (df['Depth_z'] / row['D'] - val).abs().idxmin()
                
                z_act = df.loc[idx, 'Depth_z']
                y_v = df.loc[idx, [c for c in df.columns if 'y_F' in c]].values
                p_v = df.loc[idx, [c for c in df.columns if 'p_F' in c]].values
                mask = ~np.isnan(y_v) & ~np.isnan(p_v)
                y_v, p_v = y_v[mask], p_v[mask]

                # Normalization parameters
                lib = PY_Library(z_act, row['D'], row['Dr'])
                norm_y = row['D'] if norm else 1.0
                norm_p = (lib.sigma_v * row['D']) if norm else 1.0

                c = colors[i % 10]
                self.ax.plot(y_v / norm_y, p_v / norm_p, ls='None', marker=self.markers[i % 8], 
                             mfc='white', mec=c, label=f"FEA: {row['name']}")

                y_sim = np.linspace(0.001, max(y_v) * 1.2, 100)
                for m_n in self.m_names:
                    if self.m_vars[m_n].get():
                        p_sim = np.array([lib.get_p(m_n, yi) for yi in y_sim])
                        self.ax.plot(y_sim / norm_y, p_sim / norm_p, ls=self.line_styles[m_n], 
                                     color=c, lw=1.5, label=f"{m_n}")
                        
                        # Initial stiffness tangent line (first 10% of max displacement)
                        if self.show_k.get():
                            k_ini = lib.get_k_ini(m_n)
                            if k_ini:
                                y_k = np.array([0, max(y_v) * 0.1])
                                p_k = k_ini * y_k
                                self.ax.plot(y_k / norm_y, p_k / norm_p, ls=':', color='gray', alpha=0.5)

            self.ax.set_xlabel("$y/D$" if norm else "Lateral Displacement $y$ (m)")
            self.ax.set_ylabel("$p/(\\sigma'_v D)$" if norm else "Soil Resistance $p$ (kN/m)")
            self.ax.set_title(f"p-y Curve Benchmarking | {mode} = {val:.2f}")
            self.ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=8)
            self.fig.tight_layout()
            self.canvas.draw_idle()
        except Exception as e:
            print(f"Plotting error: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = WeiSandApp(root)
    root.mainloop()
