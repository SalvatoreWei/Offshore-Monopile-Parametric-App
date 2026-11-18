# Offshore Wind Power Parametric Analysis Software (V1.0)

**National Copyright Administration of China Registration No.: 2023SR1558657**

## Overview
This standalone desktop application is developed in Python to streamline the geotechnical design and finite element post-processing of offshore wind turbine monopile foundations. It bridges complex 3D finite element numerical outputs with practical engineering design standards.

## Key Features
* **Automated FE Data Querying:** Efficiently retrieves pile deflection, bending moment, shear force, and rotation profiles across hundreds of parametric simulation scenarios.
* **Numerical $p\text{-}y$ Curve Construction:** Implements numerical differentiation algorithms to derive soil reaction forces and construct site-specific $p\text{-}y$ curves.
* **Design Code Benchmarking:** Integrates classical theoretical $p\text{-}y$ formulations for instantaneous comparison between numerical predictions and established offshore guidelines.
* **Surrogate Capacity Prediction:** Incorporates a trained machine-learning surrogate model ($R^2 = 0.99$) to rapidly predict the ultimate lateral bearing capacity (based on the $0.1D$ criterion) without computationally expensive 3D simulations.

## Quick Start (Standalone Executable)
For users who wish to run the software directly without configuring a Python environment:
1. Navigate to the **[Releases](../../releases)** section on the right-hand panel of this repository.
2. Download the latest executable package (`v1.0.0`).
3. Extract and run the `.exe` file directly on Windows.

## Source Code & Dependencies
The complete Python source code is available in the `src/` directory. To run from source:
```bash
pip install -r requirements.txt
python src/main.py
