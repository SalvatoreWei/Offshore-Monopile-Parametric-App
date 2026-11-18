import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib import rcParams

# --- 学术级绘图配置 ---
rcParams['font.family'] = 'serif'
rcParams['font.serif'] = ['Times New Roman']
rcParams['axes.unicode_minus'] = False
rcParams['xtick.direction'] = 'in' 
rcParams['ytick.direction'] = 'in'

class PY_Library:
    def __init__(self, z, D, Dr, phi=31, gamma=15):
        self.z = max(z, 0.01)
        self.D, self.Dr, self.gamma = D, Dr, gamma
        self.sigma_v = self.gamma * self.z # 竖向有效应力
        phi_rad = np.radians(phi)
        c2 = np.tan(np.radians(45 + phi/2))**2
        c1 = c2 * np.tan(phi_rad)
        sf = 1.0 + 0.35 * (D / 2.0)
        self.pu = sf * min((c1 * self.z + c2 * D) * self.gamma * self.z, c2 * D * self.gamma * self.z)

    def get_k_ini(self, m_name):
        """获取各学者定义的初始刚度 (kN/m^3)"""
        if m_name == "API (1983)":
            return (8000 if self.Dr <= 20 else 25000) * self.z
        elif m_name == "Hyperbolic":
            return 18000 * self.z
        elif m_name == "Zhang (2020)":
            return 18000 * (self.z / self.D)**0.4
        return None

    def get_p(self, m_name, y):
        eps = 1e-9
        if y <= 0: return 0
        if m_name == "API (1983)":
            k = 8000 if self.Dr <= 20 else 25000
            A = max(0.9, 3.0 - 0.8 * (self.z/self.D))
            return A * self.pu * np.tanh((k * self.z * y) / (A * self.pu + eps))
        elif m_name == "Reese (1974)":
            y_u = 3 * self.D / 80
            return self.pu * (y / y_u)**0.333 if y < y_u else self.pu
        elif m_name == "Hyperbolic":
            ki = 18000 * self.z
            return y / (1/(ki + eps) + y/(self.pu + eps))
        elif m_name == "Jeanjean (2009)":
            k_j = 12000 * (self.z**0.5) * (self.D**0.5)
            return self.pu * (1 - np.exp(-k_j * y / (self.pu + eps)))
        elif m_name == "Zhang (2020)":
            n = 0.5 + self.z / (10 * self.D)
            k_z = 18000 * (self.z / self.D)**0.4
            return self.pu * (y / (y + self.pu/(k_z + eps)))**n
        elif m_name == "Stevens (1979)":
            y50 = 0.005 * self.D
            return 0.5 * self.pu * (y / y50)**0.5 if y < y50 else self.pu
        return 0

class WeiSandApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Wei Sand p-y Visualizer v7.0 | Dimensionless & Stiffness Contrast")
        self.root.geometry("1550x950")
        
        # 线型定义：用于区分不同学者
        self.line_styles = {"API (1983)": "-", "Reese (1974)": "--", "Hyperbolic": "-.", 
                           "Jeanjean (2009)": ":", "Zhang (2020)": (0, (3, 1, 1, 1)), "Stevens (1979)": (0, (5, 10))}
        self.markers = ['o', 's', '^', 'D', 'v', 'p', '*', 'h']
        self.data_path = r"D:\OneDrive\3.海上风电\2026\0131数据\Original\static\Output\PY_Results\All_Cases_PY_Results.xlsx"
        
        self.depth_mode = tk.StringVar(value="z/L")
        self.is_norm = tk.BooleanVar(value=False) # 无量纲化开关
        self.show_k = tk.BooleanVar(value=False)  # 刚度对比开关
        
        self.load_data()
        self.setup_ui()

    def load_data(self):
        try:
            self.sheets = pd.read_excel(self.data_path, sheet_name=None)
            parsed = []
            for n in self.sheets.keys():
                if "Index" in n: continue
                match = re.search(r'D(\d+)L(\d+)Dr(\d+)', n)
                if match:
                    d, l, dr = map(int, match.groups())
                    parsed.append({'name': n, 'D': d, 'L': l, 'Dr': dr, 'LD': l/d})
            self.df_meta = pd.DataFrame(parsed)
        except: messagebox.showerror("Error", "Excel File Not Found!")

    def setup_ui(self):
        side = ttk.Frame(self.root, padding=10)
        side.pack(side=tk.LEFT, fill=tk.Y)

        # 1. 延长方框：Height设为8或10，减少滚动
        self.lb_d = self.create_lb(side, "直径 D (m)", "D", h=10)
        self.lb_ld = self.create_lb(side, "长径比 L/D", "LD", h=6)
        self.lb_dr = self.create_lb(side, "相对密度 Dr (%)", "Dr", h=6)

        # 2. 深度与模式控制
        ttk.Label(side, text="\n分析模式控制:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        ttk.Checkbutton(side, text="无量纲化 (y/D, p/σ'vD)", variable=self.is_norm, command=self.run_plot).pack(anchor=tk.W)
        ttk.Checkbutton(side, text="显示初始切线刚度对比", variable=self.show_k, command=self.run_plot).pack(anchor=tk.W)
        
        m_frame = ttk.Frame(side)
        m_frame.pack(fill=tk.X, pady=5)
        ttk.Radiobutton(m_frame, text="z/L", variable=self.depth_mode, value="z/L", command=self.run_plot).pack(side=tk.LEFT)
        ttk.Radiobutton(m_frame, text="z/D", variable=self.depth_mode, value="z/D", command=self.run_plot).pack(side=tk.LEFT)

        self.zl_s = tk.Scale(side, from_=0, to=1, resolution=0.01, orient=tk.HORIZONTAL, length=240, command=lambda x: self.run_plot())
        self.zl_s.set(0.2); self.zl_s.pack()

        # 3. 学者模型
        ttk.Label(side, text="\n理论模型 (不同线型):").pack(anchor=tk.W)
        self.m_names = list(self.line_styles.keys())
        self.m_vars = {n: tk.BooleanVar(value=(n in ["API (1983)", "Zhang (2020)"])) for n in self.m_names}
        for n in self.m_names:
            ttk.Checkbutton(side, text=n, variable=self.m_vars[n], command=self.run_plot).pack(anchor=tk.W)

        self.fig, self.ax = plt.subplots(figsize=(10, 8), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    def create_lb(self, p, txt, col, h):
        ttk.Label(p, text=txt).pack(anchor=tk.W)
        lb = tk.Listbox(p, selectmode=tk.MULTIPLE, height=h, exportselection=0, width=30)
        for v in sorted(self.df_meta[col].unique()): lb.insert(tk.END, v)
        lb.bind('<<ListboxSelect>>', lambda e: self.run_plot())
        lb.pack(fill=tk.X, pady=2); return lb

    def run_plot(self):
        self.ax.clear()
        self.ax.tick_params(direction='in', top=True, right=True, which='both')
        
        try:
            sel_d = [float(self.lb_d.get(i)) for i in self.lb_d.curselection()]
            sel_ld = [float(self.lb_ld.get(i)) for i in self.lb_ld.curselection()]
            sel_dr = [float(self.lb_dr.get(i)) for i in self.lb_dr.curselection()]
            if not (sel_d and sel_ld and sel_dr): return
            
            norm = self.is_norm.get()
            targets = self.df_meta[self.df_meta['D'].isin(sel_d) & self.df_meta['LD'].isin(sel_ld) & self.df_meta['Dr'].isin(sel_dr)]
            colors = plt.colormaps['tab10'].colors

            for i, (_, row) in enumerate(targets.iterrows()):
                df = self.sheets[row['name']]
                mode, val = self.depth_mode.get(), self.zl_s.get()
                idx = (df['z_L']-val).abs().idxmin() if mode=="z/L" else (df['Depth_z']/row['D']-val).abs().idxmin()
                
                z_act = df.loc[idx, 'Depth_z']
                y_v = df.loc[idx, [c for c in df.columns if 'y_F' in c]].values
                p_v = df.loc[idx, [c for c in df.columns if 'p_F' in c]].values
                mask = ~np.isnan(y_v) & ~np.isnan(p_v)
                y_v, p_v = y_v[mask], p_v[mask]

                # 归一化计算
                lib = PY_Library(z_act, row['D'], row['Dr'])
                norm_y = row['D'] if norm else 1.0
                norm_p = (lib.sigma_v * row['D']) if norm else 1.0

                c = colors[i % 10]
                self.ax.plot(y_v/norm_y, p_v/norm_p, ls='None', marker=self.markers[i%8], mfc='white', mec=c, label=f"FEA: {row['name']}")

                y_sim = np.linspace(0.001, max(y_v)*1.2, 100)
                for m_n in self.m_names:
                    if self.m_vars[m_n].get():
                        p_sim = np.array([lib.get_p(m_n, yi) for yi in y_sim])
                        self.ax.plot(y_sim/norm_y, p_sim/norm_p, ls=self.line_styles[m_n], color=c, lw=1.5, label=f"{m_n} Line")
                        
                        # 刚度线显示 (取前5%段)
                        if self.show_k.get():
                            k_ini = lib.get_k_ini(m_n)
                            if k_ini:
                                y_k = np.array([0, max(y_v)*0.1])
                                p_k = k_ini * y_k
                                self.ax.plot(y_k/norm_y, p_k/norm_p, ls=':', color='gray', alpha=0.5)

            self.ax.set_xlabel("$y/D$" if norm else "Displacement $y$ (m)")
            self.ax.set_ylabel("$p/(\sigma'_v D)$" if norm else "Resistance $p$ (kN/m)")
            self.ax.set_title(f"Analysis Version 7.0 | Mode: {mode}={val}")
            self.ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=8)
            self.fig.tight_layout()
            self.canvas.draw_idle()
        except Exception as e: print(e)

if __name__ == "__main__":
    root = tk.Tk(); app = WeiSandApp(root); root.mainloop()