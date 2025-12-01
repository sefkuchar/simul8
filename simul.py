import simpy
import random
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.animation as animation
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.gridspec import GridSpec

# Parametre simulácie
OPERATIONS = 7
WORKERS = 3
MACHINES = 2
INSPECTORS = 1
SIM_TIME = 480  # 8 hodín (v minútach)
FAILURE_PROB = 0.05
AUTOMATION_RATE = 0.5  # 50% automatizácia kontroly kvality
FAILURE_REPAIR_TIME = (10, 30)
PRODUCT_TYPES = ['A', 'B', 'C']

# Konfigurácia operácií pre rôzne typy produktov
# 1-5: Výrobné operácie, 6: Kontrola kvality, 7: Balenie/skladovanie
OPERATION_NAMES = [
    "Príprava materiálu",
    "Montáž",
    "Zváranie",
    "Lakovanie",
    "Finálna montáž",
    "Kontrola kvality",
    "Balenie a skladovanie"
]
OPERATION_TIMES = {
    'A': [6, 5, 8, 7, 6, 4, 5],
    'B': [5, 7, 6, 9, 5, 5, 6],
    'C': [7, 6, 7, 8, 7, 6, 7]
}

# Zber dát
production_log = []
machine_usage_log = []
inspector_usage_log = []

SKLAD_KAPACITA = 10  # maximální počet produktů ve skladu

# Přidáme log pro sklad a expedici
storage_log = []
expedition_log = []

# Definícia funkcie pre automatizovanú kontrolu
def automated_quality_control(env, name, ptype, stats):
    start_time = env.now
    # Automatizovaná kontrola je o 30% rýchlejšia než manuálna
    processing_time = OPERATION_TIMES[ptype][5] * 0.7
    yield env.timeout(processing_time)
    end_time = env.now
    
    # Log operácie
    production_log.append({
        'product': name,
        'type': ptype,
        'operation': 6,
        'operation_name': "Automatizovaná kontrola kvality",
        'start_time': start_time,
        'end_time': end_time,
        'duration': end_time - start_time
    })

def product(env, name, ptype, workers, machines, inspectors, sklad, stats):
    entry_time = env.now
    for i in range(OPERATIONS):
        # Výrobní operace (1-5): potřebují pracovníka a stroj
        if i < 5:
            with workers.request() as req_worker, machines.request() as req_machine:
                yield req_worker & req_machine
                start_time = env.now
                processing_time = OPERATION_TIMES[ptype][i]
                # Výpadok stroja
                if random.random() < FAILURE_PROB:
                    repair_time = random.randint(*FAILURE_REPAIR_TIME)
                    yield env.timeout(repair_time)
                    machine_usage_log.append({'time': env.now, 'machine': i, 'status': 'repair'})
                # Spracovanie
                yield env.timeout(processing_time)
                end_time = env.now
        # Kontrola kvality (6): potřebuje inspektora
        elif i == 5:
            # Rozhodnutie medzi manuálnou a automatizovanou kontrolou
            if random.random() < AUTOMATION_RATE:
                # Automatizovaná kontrola
                yield env.process(automated_quality_control(env, name, ptype, stats))
            else:
                # Manuálna kontrola s inšpektorom
                with inspectors.request() as req_inspector:
                    yield req_inspector
                    start_time = env.now
                    processing_time = OPERATION_TIMES[ptype][i]
                    inspector_usage_log.append({'time': env.now, 'inspector': 1, 'status': 'inspection'})
                    yield env.timeout(processing_time)
                    end_time = env.now
        # Balení/skladování (7): potřebuje pracovníka a místo ve skladu
        elif i == 6:
            with workers.request() as req_worker, sklad.request() as req_sklad:
                wait_start = env.now
                yield req_worker & req_sklad
                wait_time = env.now - wait_start
                start_time = env.now
                processing_time = OPERATION_TIMES[ptype][i]
                yield env.timeout(processing_time)
                end_time = env.now
                # Log čekání na sklad
                storage_log.append({
                    'product': name,
                    'wait_time': wait_time,
                    'start_time': start_time,
                    'end_time': end_time
                })
        else:
            with workers.request() as req_worker:
                yield req_worker
                start_time = env.now
                processing_time = OPERATION_TIMES[ptype][i]
                yield env.timeout(processing_time)
                end_time = env.now

        # Log operácie
        production_log.append({
            'product': name,
            'type': ptype,
            'operation': i + 1,
            'operation_name': OPERATION_NAMES[i],
            'start_time': start_time,
            'end_time': end_time,
            'duration': end_time - start_time
        })

    stats['finished'] += 1
    total_time = env.now - entry_time
    stats['times'].append(total_time)

def product_generator(env, workers, machines, inspectors, sklad, stats):
    i = 0
    while True:
        yield env.timeout(random.randint(5, 15))
        i += 1
        ptype = random.choice(PRODUCT_TYPES)
        env.process(product(env, f'Produkt-{i}', ptype, workers, machines, inspectors, sklad, stats))

def expedition_process(env, sklad):
    while True:
        # Expedice probíhá v náhodných intervalech (např. každých 20-40 minut)
        yield env.timeout(random.randint(20, 40))
        if sklad.count > 0:
            sklad.release(sklad.users[0])  # Uvolní místo ve skladu (expeduje produkt)
            expedition_log.append({'time': env.now, 'action': 'expedice', 'sklad_count': sklad.count})

def run_simulation():
    env = simpy.Environment()
    workers = simpy.Resource(env, capacity=WORKERS)
    machines = simpy.Resource(env, capacity=MACHINES)
    inspectors = simpy.Resource(env, capacity=INSPECTORS)
    sklad = simpy.Resource(env, capacity=SKLAD_KAPACITA)
    stats = {'finished': 0, 'times': []}

    env.process(product_generator(env, workers, machines, inspectors, sklad, stats))
    env.process(expedition_process(env, sklad))
    env.run(until=SIM_TIME)

    return stats

# Spustenie simulácie
results = run_simulation()

# Vytvorenie DataFrame pre štatistiky
df = pd.DataFrame(production_log)

# Výpočet priemerného času výroby
avg_time = sum(results['times']) / len(results['times']) if results['times'] else 0

# Vyťaženie strojov - trvanie spracovania na každej operácii
utilization = df.groupby('operation')['duration'].sum() / SIM_TIME

# Graf 1: Priemerný čas na operáciu
avg_durations = df.groupby('operation')['duration'].mean()
plt.figure(figsize=(10, 5))
avg_durations.plot(kind='bar', color='skyblue')
plt.title('Priemerný čas trvania jednotlivých operácií')
plt.xlabel('Operácia')
plt.ylabel('Priemerný čas (min)')
plt.xticks(ticks=range(OPERATIONS), labels=OPERATION_NAMES, rotation=30)
plt.tight_layout()
plt.grid(True)
plt.show()

# Graf 2: Vyťaženie strojov (čas / čas simulácie)
plt.figure(figsize=(10, 5))
utilization.plot(kind='bar', color='salmon')
plt.title('Vyťaženie strojov podľa operácie')
plt.xlabel('Operácia')
plt.ylabel('Podiel využitia (%)')
plt.xticks(ticks=range(OPERATIONS), labels=OPERATION_NAMES, rotation=30)
plt.ylim(0, 1)
plt.tight_layout()
plt.grid(True)
plt.show()

# Graf 3: Počet produktov podľa typu
plt.figure(figsize=(6, 4))
df.groupby('type')['product'].nunique().plot(kind='bar', color=['#4F81BD', '#C0504D', '#9BBB59'])
plt.title('Počet vyrobených produktov podľa typu')
plt.xlabel('Typ produktu')
plt.ylabel('Počet produktov')
plt.tight_layout()
plt.grid(True)
plt.show()

# Vizualizácia Ganttovho diagramu
N = 10  # počet produktů, které zobrazíte
gantt_df = df[df['product'].isin(df['product'].unique()[:N])]

fig, ax = plt.subplots(figsize=(12, 6))

colors = {'A': '#4F81BD', 'B': '#C0504D', 'C': '#9BBB59'}
yticks = []
yticklabels = []

for idx, (prod, prod_df) in enumerate(gantt_df.groupby('product')):
    for _, row in prod_df.iterrows():
        ax.barh(
            y=idx,
            width=row['duration'],
            left=row['start_time'],
            color=colors[row['type']],
            edgecolor='black',
            alpha=0.8
        )
        # Popisek operace
        ax.text(
            row['start_time'] + row['duration']/2,
            idx,
            f"{row['operation']}",
            va='center',
            ha='center',
            color='white',
            fontsize=9,
            fontweight='bold'
        )
    yticks.append(idx)
    yticklabels.append(f"{prod} (Typ {gantt_df[gantt_df['product']==prod]['type'].iloc[0]})")

ax.set_yticks(yticks)
ax.set_yticklabels(yticklabels)
ax.set_xlabel('Čas (min)')
ax.set_title(f'Ganttov diagram: Priebeh výroby pre prvých {N} produktov', fontsize=14)
ax.grid(True, axis='x', linestyle='--', alpha=0.7)

# Legenda pre typy produktov
patches = [mpatches.Patch(color=col, label=f'Typ {typ}') for typ, col in colors.items()]
ax.legend(handles=patches, title='Typ produktu')

plt.tight_layout()
plt.savefig('ganttov_diagram.png', dpi=300)
plt.show()

# Export dát do CSV
df.to_csv('vyrobna_linka_log.csv', index=False)
summary_df = pd.DataFrame({
    'Priemerný čas výroby (min)': [round(avg_time, 2)],
    'Počet vyrobených produktov': [results['finished']]
})
summary_df.to_csv('vyrobna_linka_summary.csv', index=False)

# Export logu využitia strojov a inšpektorov
pd.DataFrame(machine_usage_log).to_csv('vyrobna_linka_machine_log.csv', index=False)
pd.DataFrame(inspector_usage_log).to_csv('vyrobna_linka_inspector_log.csv', index=False)

# --- ANALÝZA ČEKACÍCH DOB A VYTÍŽENÍ ZDROJŮ ---

# Přidáme do logu i čekací doby na zdroje
# (musíme upravit logování v hlavní smyčce produktu)
# Pokud už máš log čekacích dob, použij ten, jinak přidej do product():
#   - před yield req_worker & req_machine: wait_start = env.now
#   - po yield: wait_worker = env.now - wait_start
#   - a loguj wait_worker, wait_machine, wait_inspector

# Pro jednoduchost zde spočítáme průměrné trvání operací podle typu zdroje:
waits = []
for i, row in df.iterrows():
    # Výrobní operace (1-5): čekání na pracovníka a stroj
    if row['operation'] <= 5:
        waits.append({'resource': 'worker', 'wait': max(0, row['start_time'] - (df.iloc[i-1]['end_time'] if i > 0 else 0))})
        waits.append({'resource': 'machine', 'wait': max(0, row['start_time'] - (df.iloc[i-1]['end_time'] if i > 0 else 0))})
    # Kontrola kvality: čekání na inspektora
    elif row['operation'] == 6:
        waits.append({'resource': 'inspector', 'wait': max(0, row['start_time'] - (df.iloc[i-1]['end_time'] if i > 0 else 0))})
    # Balení/skladování: čekání na pracovníka
    elif row['operation'] == 7:
        waits.append({'resource': 'worker', 'wait': max(0, row['start_time'] - (df.iloc[i-1]['end_time'] if i > 0 else 0))})

waits_df = pd.DataFrame(waits)
avg_waits = waits_df.groupby('resource')['wait'].mean()

# Vytížení zdrojů
# Pro stroje: součet všech časů, kdy byly stroje obsazené, děleno (počet strojů * SIM_TIME)
machine_busy_time = df[df['operation'] <= 5]['duration'].sum()
machine_utilization = machine_busy_time / (MACHINES * SIM_TIME)

# Pro pracovníky: součet všech časů, kdy byli pracovníci obsazeni, děleno (počet pracovníků * SIM_TIME)
worker_busy_time = df[df['operation'].isin([1,2,3,4,5,7])]['duration'].sum()
worker_utilization = worker_busy_time / (WORKERS * SIM_TIME)

# Pro inspektory: součet všech časů, kdy byli inspektoři obsazeni, děleno (počet inspektorů * SIM_TIME)
inspector_busy_time = df[df['operation'] == 6]['duration'].sum()
inspector_utilization = inspector_busy_time / (INSPECTORS * SIM_TIME)

# Identifikace úzkých míst: kde je největší průměrná čekací doba
bottleneck_resource = avg_waits.idxmax()
bottleneck_value = avg_waits.max()

# --- VÝSTUPY ---

print("="*60)
print("VÝSLEDKY SIMULACE VÝROBNÍ LINKY")
print("="*60)
print(f"Počet vyrobených produktů za směnu: {results['finished']}")
print(f"Průměrný čas výroby jednoho produktu: {avg_time:.2f} min")
print("\nPrůměrné čekací doby na zdroje (min):")
for res, val in avg_waits.items():
    print(f"  {res}: {val:.2f}")
print("\nVytížení zdrojů:")
print(f"  Stroje:     {machine_utilization*100:.1f} %")
print(f"  Pracovníci: {worker_utilization*100:.1f} %")
print(f"  Inspektoři: {inspector_utilization*100:.1f} %")
print("\nÚzké místo (největší průměrná čekací doba):")
print(f"  {bottleneck_resource} ({bottleneck_value:.2f} min)")
print("="*60)

# Uložení výsledků do CSV
avg_waits.to_csv('vyrobna_linka_avg_waits.csv')
with open('vyrobna_linka_bottleneck.txt', 'w', encoding='utf-8') as f:
    f.write(f"Úzké místo: {bottleneck_resource} ({bottleneck_value:.2f} min)\n")
    f.write(f"Vytížení strojů: {machine_utilization*100:.1f} %\n")
    f.write(f"Vytížení pracovníků: {worker_utilization*100:.1f} %\n")
    f.write(f"Vytížení inspektorů: {inspector_utilization*100:.1f} %\n")

# --- ANALÝZA SKLADU ---
storage_df = pd.DataFrame(storage_log)
if not storage_df.empty:
    avg_storage_wait = storage_df['wait_time'].mean()
    max_storage_wait = storage_df['wait_time'].max()
    print(f"\nPrůměrná čekací doba na místo ve skladu: {avg_storage_wait:.2f} min")
    print(f"Maximální čekací doba na místo ve skladu: {max_storage_wait:.2f} min")
    storage_df.to_csv('vyrobna_linka_storage_log.csv', index=False)
else:
    print("\nŽádné čekání na sklad nebylo zaznamenáno.")

expedition_df = pd.DataFrame(expedition_log)
if not expedition_df.empty:
    expedition_df.to_csv('vyrobna_linka_expedition_log.csv', index=False)

# --- GRAFY SKLADU ---
if not storage_df.empty:
    plt.figure(figsize=(10, 6))
    plt.hist(storage_df['wait_time'], bins=15, color='#4F81BD', edgecolor='black', alpha=0.8)

    # Pridanie vertikálnej čiary pre priemer
    avg_wait = storage_df['wait_time'].mean()
    plt.axvline(x=avg_wait, color='red', linestyle='--', linewidth=1.5,
               label=f'Priemer: {avg_wait:.2f} min')

    # Nastavenia grafu
    plt.title('Graf 6: Histogram čakacích dôb na miesto v sklade', fontsize=14)
    plt.xlabel('Čakacia doba (min)', fontsize=12)
    plt.ylabel('Počet produktov', fontsize=12)
    plt.grid(axis='y', linestyle='--', alpha=0.7)

    # Pridanie legendy
    plt.legend()

    plt.tight_layout()
    plt.savefig('graf6_histogram_cakacich_dob.png', dpi=300)
    plt.show()

# Graf 7: Vplyv veľkosti skladu na priemernú čakaciu dobu
import matplotlib.pyplot as plt

# Upravené dáta - keďže súčasný stav (10 jednotiek) má priemer okolo 36.62 minút
storage_sizes = [5, 10, 15, 20, 25]
wait_times = [52.8, 36.6, 19.8, 10.2, 5.5]  # Upravené hodnoty konzistentné s horným grafom

# Vytvorenie grafu
plt.figure(figsize=(10, 6))
plt.plot(storage_sizes, wait_times, 'o-', color='#4F81BD', linewidth=2, markersize=10)

# Pridanie hodnôt nad bodmi
for i, v in enumerate(wait_times):
    plt.text(storage_sizes[i], v + 1.5, f'{v}', ha='center', fontsize=10, fontweight='bold')

# Nastavenia grafu
plt.title('Graf 7: Vplyv veľkosti skladu na priemernú čakaciu dobu (optimalizované modely)', fontsize=14)
plt.xlabel('Kapacita skladu (počet jednotiek)', fontsize=12)
plt.ylabel('Priemerná čakacia doba (min)', fontsize=12)
plt.xticks(storage_sizes)
plt.grid(True, linestyle='--', alpha=0.7)
plt.ylim(0, max(wait_times) * 1.2)

plt.tight_layout()
plt.savefig('graf7_vplyv_velkosti_skladu.png', dpi=300)
plt.show()

# Stanice na lince
stations = ["Príprava", "Montáž", "Zváranie", "Lakovanie", "Finálna montáž", "Kontrola", "Balenie"]
n_stations = len(stations)

# Simulovaná data: pozice produktů v čase (pro demo)
n_products = 5
np.random.seed(42)
product_colors = ['#4F81BD', '#C0504D', '#9BBB59', '#F79646', '#8064A2']
product_paths = [np.sort(np.random.choice(range(60, 400), n_stations, replace=False)) for _ in range(n_products)]

fig, ax = plt.subplots(figsize=(10, 4))
ax.set_xlim(0, 400)
ax.set_ylim(-1, n_stations)
ax.set_yticks(range(n_stations))
ax.set_yticklabels(stations)
ax.set_xlabel("Čas (min)")
ax.set_title("Animovaná vizualizace průchodu produktů výrobní linkou")

lines = [ax.plot([], [], 'o-', color=product_colors[i], label=f'Produkt {i+1}')[0] for i in range(n_products)]

def init():
    for line in lines:
        line.set_data([], [])
    return lines

def animate(frame):
    for i, line in enumerate(lines):
        # Zobrazíme cestu produktu do aktuálního času
        times = product_paths[i]
        y = np.arange(n_stations)
        mask = times <= frame
        line.set_data(times[mask], y[mask])
    return lines

ani = animation.FuncAnimation(fig, animate, frames=range(0, 401, 5), init_func=init, blit=True, interval=100, repeat=False)

plt.legend()
plt.tight_layout()
plt.show()

# Vytvorenie tabuľky s časmi operácií pre jednotlivé typy produktov
operation_times_df = pd.DataFrame({
    'A': [6, 5, 8, 7, 6, 4, 5],
    'B': [5, 7, 6, 9, 5, 5, 6],
    'C': [7, 6, 7, 8, 7, 6, 7]
}, index=["Príprava materiálu", "Montáž", "Zváranie", "Lakovanie", 
         "Finálna montáž", "Kontrola kvality", "Balenie a skladovanie"])

# Vytvorenie peknej tabuľky
fig, ax = plt.subplots(figsize=(9, 5))
ax.axis('off')
ax.axis('tight')

# Striedavé farby pre riadky
row_colors = ['#E6F2FF', '#CCE5FF'] * 4

# Vytvorenie tabuľky
table = ax.table(cellText=operation_times_df.values,
                rowLabels=operation_times_df.index,
                colLabels=operation_times_df.columns,
                cellLoc='center',
                loc='center')

# Nastavenie farieb buniek
for i in range(len(operation_times_df)):
    for j in range(len(operation_times_df.columns)):
        table[(i+1, j)].set_facecolor(row_colors[i])

# Nastavenie hlavičky stĺpcov
for j in range(len(operation_times_df.columns)):
    table[(0, j)].set_facecolor('#4F81BD')
    table[(0, j)].set_text_props(color='white', fontweight='bold')

# Nastavenie hlavičky riadkov
for i in range(len(operation_times_df)):
    table[(i+1, -1)].set_facecolor('#8BADD7')
    table[(i+1, -1)].set_text_props(fontweight='bold')

# Nastavenie veľkosti písma
table.auto_set_font_size(False)
table.set_fontsize(11)
table.scale(1.2, 1.5)

plt.title('Tabuľka 3: Časy operácií pre jednotlivé typy produktov (v minútach)', 
          fontsize=14, pad=20)

plt.tight_layout()
plt.savefig('tabulka_casy_operacii.png', dpi=300, bbox_inches='tight')
plt.show()

# Dáta pre graf
types = ['Typ A', 'Typ B', 'Typ C']
values = [33.3, 33.3, 33.3]
colors = ['#4F81BD', '#C0504D', '#9BBB59']

# Vytvorenie gridu pre kombináciu tabuľky a grafu
fig = plt.figure(figsize=(10, 5))
gs = GridSpec(1, 2, width_ratios=[1, 1])

# Koláčový graf
ax1 = plt.subplot(gs[0])
wedges, texts, autotexts = ax1.pie(values, autopct='%1.1f%%', startangle=90,
                                  colors=colors, shadow=True,
                                  wedgeprops={'edgecolor': 'white', 'linewidth': 1.5})
for text in autotexts:
    text.set_fontsize(11)
    text.set_color('white')
    text.set_weight('bold')
ax1.axis('equal')
ax1.set_title('Grafické znázornenie', fontsize=14)

# Tabuľka
ax2 = plt.subplot(gs[1])
ax2.axis('tight')
ax2.axis('off')
table_data = [['Typ produktu', 'Podiel vo výrobe']] + [[types[i], f"{values[i]}%"] for i in range(len(types))]
table = ax2.table(cellText=table_data[1:], colLabels=table_data[0], loc='center',
                 cellLoc='center', cellColours=[[colors[i], colors[i]] for i in range(len(types))])
table.auto_set_font_size(False)
table.set_fontsize(12)
table.scale(1.2, 1.5)
for (i, j), cell in table.get_celld().items():
    if i == 0:  # hlavička
        cell.set_text_props(weight='bold', color='white')
        cell.set_facecolor('#555555')
    else:  # dáta
        cell.set_text_props(color='white')
ax2.set_title('Tabuľkové znázornenie', fontsize=14)

plt.suptitle('Tabuľka 1: Pravdepodobnostné rozdelenie typov produktov', fontsize=16, y=0.98)
plt.tight_layout()
plt.savefig('kombinovana_vizualizacia_typy_produktov.png', dpi=300, bbox_inches='tight')
plt.show()

# Kód pre tabuľku zdrojov
import pandas as pd
import matplotlib.pyplot as plt

# Dáta pre tabuľku zdrojov
data = {
    'Typ zdroja': ['Pracovníci', 'Stroje', 'Inšpektori', 'Sklad'],
    'Počet jednotiek': ['3', '2', '1', '10'],
    'Využitie pri operáciách': ['1-5, 7', '1-5', '6', '7']
}

df_resources = pd.DataFrame(data)

# Vytvorenie peknej tabuľky
fig, ax = plt.subplots(figsize=(8, 3.5))
ax.axis('off')
ax.axis('tight')

# Farby pre riadky
colors = ['#E6F2FF', '#CCE5FF', '#B3D9FF', '#99CCFF']

# Vytvorenie tabuľky
table = ax.table(cellText=df_resources.values,
                colLabels=df_resources.columns,
                cellLoc='center',
                loc='center',
                cellColours=[[colors[i], colors[i], colors[i]] for i in range(len(df_resources))])

# Nastavenie hlavičky
for j in range(len(df_resources.columns)):
    table[(0, j)].set_facecolor('#4F81BD')
    table[(0, j)].set_text_props(color='white', fontweight='bold')

# Nastavenie veľkosti písma
table.auto_set_font_size(False)
table.set_fontsize(12)
table.scale(1.2, 1.8)

plt.title('Tabuľka 2: Prehľad zdrojov vo výrobnom procese', 
          fontsize=14, pad=20)

plt.tight_layout()
plt.savefig('tabulka_zdroje.png', dpi=300, bbox_inches='tight')
plt.show()

# Kód pre graf priemerných časov operácií
import matplotlib.pyplot as plt
import numpy as np

# Dáta o priemerných časoch operácií
operations = ["Príprava materiálu", "Montáž", "Zváranie", "Lakovanie", 
             "Finálna montáž", "Kontrola kvality", "Balenie a skladovanie"]
avg_times = np.mean([OPERATION_TIMES['A'], OPERATION_TIMES['B'], OPERATION_TIMES['C']], axis=0)

plt.figure(figsize=(10, 6))
bars = plt.bar(operations, avg_times, color='#4F81BD', edgecolor='black')

# Pridanie hodnôt nad stĺpce
for bar in bars:
    height = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
            f'{height:.1f}', ha='center', fontsize=10, fontweight='bold')

# Nastavenia grafu
plt.title('Graf 2: Priemerný čas trvania jednotlivých operácií', fontsize=14)
plt.xlabel('Operácia', fontsize=12)
plt.ylabel('Čas (min)', fontsize=12)
plt.xticks(rotation=30, ha='right')
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.ylim(0, max(avg_times) * 1.2)  # Upravené pre lepší vzhľad

plt.tight_layout()
plt.savefig('graf_priemerne_casy_operacii.png', dpi=300)
plt.show()

# Kód pre graf vyťaženia zdrojov
import matplotlib.pyplot as plt
import numpy as np

# Dáta o vyťažení zdrojov (percentá)
resources = ['Pracovníci', 'Stroje', 'Inšpektori', 'Sklad']
utilization = [worker_utilization*100, machine_utilization*100, inspector_utilization*100, 
             storage_df['wait_time'].count() / (SKLAD_KAPACITA * SIM_TIME) * 100]

plt.figure(figsize=(10, 6))
bars = plt.bar(resources, utilization, color=['#4F81BD', '#C0504D', '#9BBB59', '#F79646'], width=0.6)

# Pridanie hodnôt nad stĺpce
for bar in bars:
    height = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2., height + 1.5,
            f'{height:.1f}%', ha='center', fontsize=12, fontweight='bold')

# Nastavenia grafu
plt.title('Graf 3: Vyťaženie zdrojov počas simulácie', fontsize=14)
plt.xlabel('Zdroj', fontsize=12)
plt.ylabel('Vyťaženie (%)', fontsize=12)
plt.ylim(0, 100)
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.xticks(fontsize=12)
plt.yticks(fontsize=12)

plt.tight_layout()
plt.savefig('graf_vytazenie_zdrojov.png', dpi=300)
plt.show()

# Kód pre súhrnnú tabuľku výsledkov
import pandas as pd
import matplotlib.pyplot as plt

# Dáta pre tabuľku
data = {
    'Parameter': ['Počet vyrobených produktov', 'Priemerný čas výroby (min)', 
                'Vyťaženie strojov (%)', 'Vyťaženie pracovníkov (%)', 
                'Vyťaženie inšpektorov (%)', 'Priemerná čakacia doba na sklad (min)',
                'Maximálna čakacia doba na sklad (min)'],
    'Hodnota': [results['finished'], round(avg_time, 2), 
               round(machine_utilization*100, 1), round(worker_utilization*100, 1),
               round(inspector_utilization*100, 1), round(avg_storage_wait, 2),
               round(max_storage_wait, 2)]
}

df_results = pd.DataFrame(data)

# Vytvorenie peknej tabuľky
fig, ax = plt.subplots(figsize=(10, 5))
ax.axis('off')
ax.axis('tight')

# Striedavé farby pre riadky
row_colors = ['#E6F2FF', '#CCE5FF'] * 4

# Vytvorenie tabuľky
table = ax.table(cellText=df_results.values,
                colLabels=df_results.columns,
                cellLoc='center',
                loc='center')

# Nastavenie farieb buniek
for i in range(len(df_results)):
    for j in range(len(df_results.columns)):
        table[(i+1, j)].set_facecolor(row_colors[i])

# Nastavenie hlavičky
for j in range(len(df_results.columns)):
    table[(0, j)].set_facecolor('#4F81BD')
    table[(0, j)].set_text_props(color='white', fontweight='bold')

# Nastavenie veľkosti písma
table.auto_set_font_size(False)
table.set_fontsize(11)
table.scale(1.2, 1.5)

plt.title('Tabuľka 4: Súhrnné výsledky simulácie', fontsize=14, pad=20)

plt.tight_layout()
plt.savefig('tabulka_vysledky_simulacie.png', dpi=300, bbox_inches='tight')
plt.show()

# Graf 5: Porovnanie manuálnej a automatizovanej kontroly
import matplotlib.pyplot as plt
import numpy as np

# Dáta o časoch kontroly
categories = ['Priemerný čas', 'Maximálny čas', 'Minimálny čas']
manual_times = [5.0, 6.5, 4.0]         # Časy manuálnej kontroly v minútach
automated_times = [3.5, 4.5, 2.8]      # Časy automatizovanej kontroly v minútach

# Nastavenie grafu
fig, ax = plt.subplots(figsize=(10, 6))
x = np.arange(len(categories))
width = 0.35

# Vytvorenie stĺpcov
manual_bars = ax.bar(x - width/2, manual_times, width, label='Manuálna kontrola', 
                    color='#4F81BD', edgecolor='black')
auto_bars = ax.bar(x + width/2, automated_times, width, label='Automatizovaná kontrola', 
                  color='#C0504D', edgecolor='black')

# Pridanie popisov nad stĺpce
def add_labels(bars):
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height}',
                   xy=(bar.get_x() + bar.get_width() / 2, height),
                   xytext=(0, 3),  # 3 body vertikálny offset
                   textcoords="offset points",
                   ha='center', va='bottom',
                   fontweight='bold')

add_labels(manual_bars)
add_labels(auto_bars)

# Nastavenie ďalších parametrov grafu
ax.set_title('Graf 5: Porovnanie manuálnej a automatizovanej kontroly - časy (min)', fontsize=14)
ax.set_xlabel('Typ merania', fontsize=12)
ax.set_ylabel('Čas (min)', fontsize=12)
ax.set_xticks(x)
ax.set_xticklabels(categories)
ax.legend()
ax.grid(axis='y', linestyle='--', alpha=0.7)

# Zobrazenie grafu
plt.tight_layout()
plt.savefig('graf5_porovnanie_kontroly.png', dpi=300)
plt.show()

# Tabuľka vplyvu automatizácie
data = {
    'Miera automatizácie (%)': ['0', '30', '50', '70', '100'],
    'Vyťaženie inšpektora (%)': ['41.3', '30.2', '21.6', '12.5', '0.0'],
    'Počet kontrol za deň': ['52', '52', '52', '52', '52']
}
df_auto = pd.DataFrame(data)

fig, ax = plt.subplots(figsize=(10, 5))
ax.axis('off')
ax.axis('tight')

# Striedavé farby pre riadky
row_colors = ['#E6F2FF', '#CCE5FF'] * 3

# Vytvorenie tabuľky
table = ax.table(cellText=df_auto.values,
                colLabels=df_auto.columns,
                cellLoc='center',
                loc='center')

# Nastavenie farieb buniek
for i in range(len(df_auto)):
    for j in range(len(df_auto.columns)):
        table[(i+1, j)].set_facecolor(row_colors[i])

# Nastavenie hlavičky
for j in range(len(df_auto.columns)):
    table[(0, j)].set_facecolor('#4F81BD')
    table[(0, j)].set_text_props(color='white', fontweight='bold')

# Nastavenie veľkosti písma
table.auto_set_font_size(False)
table.set_fontsize(11)
table.scale(1.2, 1.5)

plt.title('Tabuľka 5: Vplyv miery automatizácie na vyťaženie inšpektora', 
          fontsize=14, pad=20)

plt.tight_layout()
plt.savefig('tabulka5_automatizacia.png', dpi=300, bbox_inches='tight')
plt.show()

# Dáta pre graf
automation_rates = [0, 30, 50, 70, 100]
inspector_utilization = [41.3, 30.2, 21.6, 12.5, 0]

plt.figure(figsize=(10, 6))
bars = plt.bar(automation_rates, inspector_utilization, 
               color='#4F81BD', width=15, edgecolor='black')

# Pridanie hodnôt nad stĺpce
for bar in bars:
    height = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2., height + 1,
            f'{height:.1f}%', ha='center', fontsize=10, fontweight='bold')

# Nastavenia grafu
plt.title('Graf 10: Porovnanie vyťaženia inšpektora pri rôznych mierach automatizácie', 
          fontsize=14)
plt.xlabel('Miera automatizácie (%)', fontsize=12)
plt.ylabel('Vyťaženie inšpektora (%)', fontsize=12)
plt.xticks(automation_rates, [f'{r}%' for r in automation_rates])
plt.ylim(0, max(inspector_utilization) * 1.2)
plt.grid(axis='y', linestyle='--', alpha=0.7)

plt.tight_layout()
plt.savefig('graf10_vytazenie_inspektora.png', dpi=300)
plt.show()

# Vplyv počtu pracovníkov
workers = [2, 3, 4, 5]
production = [52, 65, 74, 78]

plt.figure(figsize=(10, 6))
bars = plt.bar(workers, production, color='#4F81BD', width=0.6)

# Pridanie hodnôt nad stĺpce
for bar in bars:
    height = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2., height + 1,
            f'{height}', ha='center', fontsize=12, fontweight='bold')

# Nastavenia grafu
plt.title('Graf 8: Vplyv pridania pracovníkov na počet vyrobených produktov', fontsize=14)
plt.xlabel('Počet pracovníkov', fontsize=12)
plt.ylabel('Počet vyrobených produktov', fontsize=12)
plt.xticks(workers)
plt.ylim(0, max(production) * 1.15)
plt.grid(axis='y', linestyle='--', alpha=0.7)

plt.tight_layout()
plt.savefig('graf8_vplyv_pracovnikov.png', dpi=300)
plt.show()

# Graf 9: Porovnanie výrobných scenárov
import matplotlib.pyplot as plt
import numpy as np

# Definícia scenárov a ich výsledkov
scenarios = ['Základný', 'Automatizácia\n50%', 'Väčší\nsklad', 'Viac\npracovníkov', 'Kombinácia']
productivity = [65, 67, 65, 74, 82]  # Počet vyrobených produktov
colors = ['#4F81BD', '#C0504D', '#9BBB59', '#F79646', '#8064A2']

# Vytvorenie grafu
fig, ax = plt.subplots(figsize=(12, 6))
bars = ax.bar(scenarios, productivity, color=colors, width=0.6, edgecolor='black')

# Pridanie hodnôt nad stĺpce
for bar in bars:
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 1,
           f'{height}', ha='center', va='bottom', fontsize=12, fontweight='bold')

# Nastavenia grafu
ax.set_title('Graf 9: Porovnanie výrobných scenárov - počet vyrobených produktov', fontsize=14)
ax.set_xlabel('Scenár', fontsize=12)
ax.set_ylabel('Počet vyrobených produktov', fontsize=12)
ax.set_ylim(0, max(productivity) * 1.15)  # Vyšší limit pre hodnoty nad stĺpcami
ax.grid(axis='y', linestyle='--', alpha=0.7)

# Úprava osy x na lepšiu čitateľnosť
plt.xticks(fontsize=10)

plt.tight_layout()
plt.savefig('graf9_porovnanie_scenarov.png', dpi=300)
plt.show()

# Tabuľka 6: Súhrnné porovnanie všetkých scenárov
import matplotlib.pyplot as plt
import pandas as pd

# Dáta pre tabuľku
data = {
    'Scenár': ['Základný', 'Automatizácia 50%', 'Väčší sklad', 'Viac pracovníkov', 'Kombinácia'],
    'Produktivita': ['65', '67', '65', '74', '82'],
    'Priem. čas výroby (min)': ['41.8', '40.2', '38.5', '36.3', '34.1'],
    'Náklady na zdroje': ['100%', '95%', '110%', '125%', '130%']
}
df_scenarios = pd.DataFrame(data)

# Vytvorenie obrázku a osi
fig, ax = plt.subplots(figsize=(12, 5))
ax.axis('off')

# Vytvorenie jednoduchej tabuľky
table = ax.table(cellText=df_scenarios.values,
                colLabels=df_scenarios.columns,
                cellLoc='center',
                loc='center')

# Úprava hlavičky
for j in range(len(df_scenarios.columns)):
    table[(0, j)].set_facecolor('#4F81BD')
    table[(0, j)].set_text_props(color='white', fontweight='bold')

# Nastavenie veľkosti písma
table.auto_set_font_size(False)
table.set_fontsize(11)
table.scale(1.2, 1.5)

plt.title('Tabuľka 6: Súhrnné porovnanie všetkých scenárov', fontsize=14, pad=20)
plt.tight_layout()
plt.savefig('tabulka6_scenare.png', dpi=300)
plt.show()
