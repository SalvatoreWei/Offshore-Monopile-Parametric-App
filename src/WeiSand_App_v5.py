import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib import rcParams

# --- 学术级配置：刻度向内 & 字体 ---
rcParams['font.family'] = 'serif'
rcParams['font.serif'] = ['Times New Roman']
rcParams['axes.unicode_minus'] = False
rcParams['xtick.direction'] = 'in'  # 全局刻度向内
rcParams['ytick.direction'] = 'in'

class PY_Library:
    """完整集成所有学者模型，严禁删除"""
    def __init__(self, z, D, Dr, phi=31, gamma=15):
        self.z = max(z, 0.05)
        self.D, self.Dr, self.gamma = D, Dr, gamma
        phi_rad = np.radians(phi)
        c2 = np.tan(np.radians(45 + phi/2))**2
        c1 = c2 * np.tan(phi_rad)
        # 魏砂大直径修正系数
        sf = 1.0 + 0.35 * (D / 2.0)
        self.pu = sf * min((c1 * self.z + c2 * D) * self.gamma * self.z, c2 * D * self.gamma * self.z)

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
        self.root.title("Wei Sand p-y Visualizer Extreme v5.0")
        self.root.geometry("1450x850")
        
        self.markers = ['o', 's', '^', 'D', 'v', 'p', '*', 'h']
        self.data_path = "All_Cases_PY_Results.xlsx"
        if not os.path.exists(self.data_path):
            self.data_path = r"D:\OneDrive\3.海上风电\2026\0131数据\Original\static\Output\PY_Results\All_Cases_PY_Results.xlsx"

        self.load_data()
        self.setup_ui()

    def load_data(self):
        try:
            self.sheets = pd.read_excel(self.data_path, sheet_name=None)
            parsed = [{'name': n, 'D': int(re.search(r'D(\d+)', n).group(1)), 
                       'L': int(re.search(r'L(\d+)', n).group(1)), 
                       'Dr': int(re.search(r'Dr(\d+)', n).group(1)), 
                       'LD': int(re.search(r'L(\d+)', n).group(1))/int(re.search(r'D(\d+)', n).group(1))} 
                      for n in self.sheets.keys() if "Index" not in n]
            self.df_meta = pd.DataFrame(parsed)
        except: messagebox.showerror("错误", "数据加载失败")

    def setup_ui(self):
        # 布局控制
        left = ttk.Frame(self.root, padding=10)
        left.pack(side=tk.LEFT, fill=tk.Y)

        self.lb_d = self.create_lb(left, "直径 D (m)", "D")
        self.lb_ld = self.create_lb(left, "长径比 L/D", "LD")
        self.lb_dr = self.create_lb(left, "相对密度 Dr (%)", "Dr")

        ttk.Label(left, text="\n深度比 z/L:").pack(anchor=tk.W)
        self.zl_s = tk.Scale(left, from_=0, to=1, resolution=0.01, orient=tk.HORIZONTAL, length=200, command=lambda x: self.run_plot())
        self.zl_s.set(0.2); self.zl_s.pack()

        ttk.Label(left, text="\n学者模型集成:").pack(anchor=tk.W)
        self.m_names = ["API (1983)", "Reese (1974)", "Hyperbolic", "Jeanjean (2009)", "Zhang (2020)", "Stevens (1979)"]
        self.m_vars = {n: tk.BooleanVar(value=(n in ["API (1983)", "Zhang (2020)"])) for n in self.m_names}
        for n in self.m_names:
            ttk.Checkbutton(left, text=n, variable=self.m_vars[n], command=self.run_plot).pack(anchor=tk.W)

        # 绘图面板
        self.fig, self.ax = plt.subplots(figsize=(10, 8), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    def create_lb(self, p, txt, col):
        ttk.Label(p, text=txt).pack(anchor=tk.W)
        lb = tk.Listbox(p, selectmode=tk.MULTIPLE, height=4, exportselection=0)
        for v in sorted(self.df_meta[col].unique()): lb.insert(tk.END, v)
        lb.bind('<<ListboxSelect>>', lambda e: self.run_plot())
        lb.pack(fill=tk.X, pady=2); return lb

    def run_plot(self):
        """极速绘图逻辑：由交互事件直接触发"""
        self.ax.clear()
        # 再次确保刻度向内
        self.ax.tick_params(direction='in', top=True, right=True, which='both')
        
        try:
            sel_d = [float(self.lb_d.get(i)) for i in self.lb_d.curselection()]
            sel_ld = [float(self.lb_ld.get(i)) for i in self.lb_ld.curselection()]
            sel_dr = [float(self.lb_dr.get(i)) for i in self.lb_dr.curselection()]
            if not (sel_d and sel_ld and sel_dr): return
            
            zl = self.zl_s.get()
            targets = self.df_meta[self.df_meta['D'].isin(sel_d) & self.df_meta['LD'].isin(sel_ld) & self.df_meta['Dr'].isin(sel_dr)]
            colors = plt.colormaps['tab10'].colors

            for i, (_, row) in enumerate(targets.iterrows()):
                df = self.sheets[row['name']]
                idx = (df['z_L'] - zl).abs().idxmin()
                y_v = df.loc[idx, [c for c in df.columns if 'y_F' in c]].values
                p_v = df.loc[idx, [c for c in df.columns if 'p_F' in c]].values
                
                mask = ~np.isnan(y_v) & ~np.isnan(p_v)
                y_v, p_v = y_v[mask], p_v[mask]

                if len(y_v) > 0:
                    c = colors[i % 10]
                    m = self.markers[i % len(self.markers)]
                    # FEA 曲线：学术空心点
                    self.ax.plot(y_v, p_v, ls='-', marker=m, mfc='white', mec=c, mew=1.5, label=f"FEA: {row['name']}", color=c)
                    
                    # 理论模型：严禁缩减
                    lib = PY_Library(df.loc[idx, 'Depth_z'], row['D'], row['Dr'])
                    y_sim = np.linspace(0.001, max(y_v)*1.1, 80)
                    for m_n in self.m_names:
                        if self.m_vars[m_n].get():
                            p_sim = [lib.get_p(m_n, yi) for yi in y_sim]
                            self.ax.plot(y_sim, p_sim, ls='--', lw=1.2, color=c, label=f"{m_n} Ref")

            self.ax.set_title(f"Wei Sand p-y Comparison (z/L={zl})", fontsize=14, pad=15)
            self.ax.set_xlabel("Displacement $y$ (m)", fontsize=12)
            self.ax.set_ylabel("Resistance $p$ (kN/m)", fontsize=12)
            self.ax.grid(True, ls=':', alpha=0.4)
            self.ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=8, frameon=False)
            self.fig.tight_layout()
            self.canvas.draw_idle() # 极速重绘
        except: pass

if __name__ == "__main__":
    root = tk.Tk()
    app = WeiSandApp(root)
    root.mainloop()