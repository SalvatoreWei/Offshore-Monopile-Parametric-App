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
    """理论模型库：后续将在此增加切线刚度对比及无量纲计算"""
    def __init__(self, z, D, Dr, phi=31, gamma=15):
        self.z = max(z, 0.05)
        self.D, self.Dr, self.gamma = D, Dr, gamma
        phi_rad = np.radians(phi)
        c2 = np.tan(np.radians(45 + phi/2))**2
        c1 = c2 * np.tan(phi_rad)
        # 大直径桩极限抗力修正 (sf)
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
        self.root.title("Wei Sand p-y Visualizer v6.0 | Depth Control Expansion")
        self.root.geometry("1500x900")
        
        self.markers = ['o', 's', '^', 'D', 'v', 'p', '*', 'h']
        self.data_path = r"D:\OneDrive\3.海上风电\2026\0131数据\Original\static\Output\PY_Results\All_Cases_PY_Results.xlsx"
        
        self.depth_mode = tk.StringVar(value="z/L") # 默认 z/L 模式
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
        except Exception as e:
            messagebox.showerror("Error", f"Excel无法读取: {e}")

    def setup_ui(self):
        # --- 左侧控制面板 ---
        side = ttk.Frame(self.root, padding=10)
        side.pack(side=tk.LEFT, fill=tk.Y)

        self.lb_d = self.create_lb(side, "直径 D (m)", "D")
        self.lb_ld = self.create_lb(side, "长径比 L/D", "LD")
        self.lb_dr = self.create_lb(side, "相对密度 Dr (%)", "Dr")

        # --- 新增：深度控制模式切换 ---
        ttk.Label(side, text="\n深度控制基准:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        m_frame = ttk.Frame(side)
        m_frame.pack(fill=tk.X)
        ttk.Radiobutton(m_frame, text="z/L 模式", variable=self.depth_mode, value="z/L", command=self.update_slider).pack(side=tk.LEFT)
        ttk.Radiobutton(m_frame, text="z/D 模式", variable=self.depth_mode, value="z/D", command=self.update_slider).pack(side=tk.LEFT)

        self.zl_label = ttk.Label(side, text="当前 z/L: 0.20")
        self.zl_label.pack(anchor=tk.W, pady=(5,0))
        self.zl_s = tk.Scale(side, from_=0, to=1, resolution=0.01, orient=tk.HORIZONTAL, length=220, command=self.on_slider_move)
        self.zl_s.set(0.2); self.zl_s.pack()

        # --- 模型选择 ---
        ttk.Label(side, text="\n学者模型集成:").pack(anchor=tk.W)
        self.m_names = ["API (1983)", "Reese (1974)", "Hyperbolic", "Jeanjean (2009)", "Zhang (2020)", "Stevens (1979)"]
        self.m_vars = {n: tk.BooleanVar(value=(n in ["API (1983)", "Zhang (2020)"])) for n in self.m_names}
        for n in self.m_names:
            ttk.Checkbutton(side, text=n, variable=self.m_vars[n], command=self.run_plot).pack(anchor=tk.W)

        # --- 右侧绘图区 ---
        self.fig, self.ax = plt.subplots(figsize=(10, 8), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    def create_lb(self, p, txt, col):
        ttk.Label(p, text=txt).pack(anchor=tk.W)
        lb = tk.Listbox(p, selectmode=tk.MULTIPLE, height=4, exportselection=0)
        for v in sorted(self.df_meta[col].unique()): lb.insert(tk.END, v)
        lb.bind('<<ListboxSelect>>', lambda e: self.run_plot())
        lb.pack(fill=tk.X, pady=2); return lb

    def update_slider(self):
        """根据切换按钮改变滑动条范围"""
        if self.depth_mode.get() == "z/L":
            self.zl_s.configure(from_=0, to=1.0, resolution=0.01)
            self.zl_s.set(0.2)
        else:
            # z/D 模式，假设最大深度为 10 倍直径
            self.zl_s.configure(from_=0, to=10.0, resolution=0.1)
            self.zl_s.set(2.0)
        self.run_plot()

    def on_slider_move(self, val):
        self.zl_label.config(text=f"当前 {self.depth_mode.get()}: {float(val):.2f}")
        self.run_plot()

    def run_plot(self):
        self.ax.clear()
        self.ax.tick_params(direction='in', top=True, right=True, which='both')
        
        try:
            sel_d = [float(self.lb_d.get(i)) for i in self.lb_d.curselection()]
            sel_ld = [float(self.lb_ld.get(i)) for i in self.lb_ld.curselection()]
            sel_dr = [float(self.lb_dr.get(i)) for i in self.lb_dr.curselection()]
            if not (sel_d and sel_ld and sel_dr): return
            
            mode = self.depth_mode.get()
            val = self.zl_s.get()
            targets = self.df_meta[self.df_meta['D'].isin(sel_d) & self.df_meta['LD'].isin(sel_ld) & self.df_meta['Dr'].isin(sel_dr)]
            colors = plt.colormaps['tab10'].colors

            for i, (_, row) in enumerate(targets.iterrows()):
                df = self.sheets[row['name']]
                
                # 深度定位核心逻辑
                if mode == "z/L":
                    idx = (df['z_L'] - val).abs().idxmin()
                else:
                    # z/D 模式：计算 df 中每一行对应的 z/D，然后寻找最接近 val 的
                    current_zd = df['Depth_z'] / row['D']
                    idx = (current_zd - val).abs().idxmin()

                y_v = df.loc[idx, [c for c in df.columns if 'y_F' in c]].values
                p_v = df.loc[idx, [c for c in df.columns if 'p_F' in c]].values
                z_act = df.loc[idx, 'Depth_z']
                
                mask = ~np.isnan(y_v) & ~np.isnan(p_v)
                y_v, p_v = y_v[mask], p_v[mask]

                if len(y_v) > 0:
                    c = colors[i % 10]
                    m = self.markers[i % len(self.markers)]
                    # 绘制模拟点
                    self.ax.plot(y_v, p_v, ls='-', marker=m, mfc='white', mec=c, mew=1.5, 
                                 label=f"FEA: {row['name']} (z={z_act:.2f}m)", color=c)
                    
                    # 理论对比线
                    lib = PY_Library(z_act, row['D'], row['Dr'])
                    y_sim = np.linspace(0.001, max(y_v)*1.1, 80)
                    for m_n in self.m_names:
                        if self.m_vars[m_n].get():
                            p_sim = [lib.get_p(m_n, yi) for yi in y_sim]
                            self.ax.plot(y_sim, p_sim, ls='--', lw=1.2, color=c, label=f"{m_n} Ref")

            self.ax.set_title(f"p-y Response Comparison ({mode}={val})", fontsize=14, pad=15)
            self.ax.set_xlabel("Displacement $y$ (m)", fontsize=12)
            self.ax.set_ylabel("Resistance $p$ (kN/m)", fontsize=12)
            self.ax.grid(True, ls=':', alpha=0.4)
            self.ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=8, frameon=False)
            self.fig.tight_layout()
            self.canvas.draw_idle()
        except Exception as e:
            print(f"Plot Error: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = WeiSandApp(root)
    root.mainloop()