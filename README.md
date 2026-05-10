# Manufacturing Line Simulation: SimPy Discrete-Event Model

This project implements a discrete-event simulation (DES) using the `SimPy` library to model an industrial production line. It tracks resource constraints, machine failures, and various product types over an 8-hour shift.

---

## 1. Project Overview
The simulation models a manufacturing environment where products of different types (A, B, and C) pass through a sequence of operations. The system's performance is limited by available workers, machines, and storage capacity.

### Production Stages
*   **Stage 1: Material Preparation**
*   **Stage 2: Assembly**[cite: 1]
*   **Stage 3: Welding**[cite: 1]
*   **Stage 4: Painting**[cite: 1]
*   **Stage 5: Final Assembly**[cite: 1]
*   **Stage 6: Quality Control** (Manual vs. Automated)[cite: 1]
*   **Stage 7: Packaging and Storage**[cite: 1]

---

## 2. Simulation Architecture

### Resource Configuration
The model manages four primary resource categories with defined capacities:[cite: 1]
*   **Workers (3):** Required for all production and packaging tasks.[cite: 1]
*   **Machines (2):** Shared resources utilized during the first five manufacturing stages.[cite: 1]
*   **Inspectors (1):** Dedicated to manual quality control checks.[cite: 1]
*   **Warehouse (10):** A finite buffer for finished goods waiting for expedition.[cite: 1]

### Key Logic and Events
*   **Failure Modeling:** Machines have a 5% probability of failure during any production step. Repairs take between 10 to 30 minutes, during which both the machine and the assigned worker are occupied.[cite: 1]
*   **Automated Quality Control:** The simulation implements a hybrid QC process. 50% of items undergo automated inspection, which is 30% faster than the manual process and does not require a human inspector.[cite: 1]
*   **Expedition:** A separate process releases products from the warehouse at random intervals (20-40 minutes) to prevent storage overflows.[cite: 1]

---

## 3. Data Collection and Analysis
The script records detailed logs for every event within the simulation:[cite: 1]

*   **Production Log:** Records start times, end times, and durations for every operation per product.[cite: 1]
*   **Machine/Inspector Logs:** Tracks specific status changes, including repairs and inspections.[cite: 1]
*   **Storage Log:** Captures wait times for products attempting to enter a full warehouse.[cite: 1]

### Statistical Outputs
The model automatically calculates and prints:[cite: 1]
*   **Total Output:** Number of finished products per shift.[cite: 1]
*   **Average Lead Time:** Average time taken to complete all 7 stages.[cite: 1]
*   **Resource Utilization:** Percentage of time workers, machines, and inspectors are busy.[cite: 1]
*   **Bottleneck Analysis:** Identifies the resource responsible for the highest average wait time.[cite: 1]

---

## 4. Visualizations
The simulation generates the following graphical reports:[cite: 1]
*   **Gantt Chart:** A horizontal timeline showing the progression of individual products.[cite: 1]
*   **Utilization Bar Charts:** Comparisons of resource usage and operation durations.[cite: 1]
*   **Warehouse Histogram:** Distribution of wait times for storage space.[cite: 1]
*   **Optimal Capacity Curve:** A plot showing how warehouse size impacts average wait times.[cite: 1]
*   **Animated View:** A dynamic visualization using `matplotlib.animation` to show product flow through stations.[cite: 1]

---

## 5. Requirements and Setup
To run the simulation, install the necessary Python libraries:[cite: 1]

```bash
pip install simpy pandas matplotlib numpy
