# Fiber Composite Sweeps & Solver Comparison for MatViz3D

[English](#english) · [Українська](#українська)

<a id="english"></a>

Resumable parameter sweeps of fiber-reinforced composites built with MatViz3D's `Composite` algorithm.
For each sweep value and realization the tool generates a periodic 3D RVE, homogenizes it with the
**FFT** (Moulinec–Suquet) and/or **ANSYS** FEM solver, extracts the effective stiffness $C_{ij}$ and
engineering constants ($E_i, G_{ij}, \nu_{12}, \nu_{31}$), checks them against Voigt/Reuss bounds and
produces figures (PNG + EPS) and FFT vs ANSYS comparison tables.

---

## Key Features

1. **Scenarios in Python** — every computation is a `SweepConfig` in `config.py`; run it by name.
2. **FFT vs ANSYS** on identical geometry and seeds, with relative differences `|FFT − ANSYS| / ANSYS`.
3. **Acceptance criteria** — achieved vs target Vf, Reuss ≤ E, G ≤ Voigt, solver tolerance (`criteria_summary.txt`).
4. **Resumable** — finished units are checkpointed in `results.csv`; a re-run skips them.
5. **Two modes** — `stiffness` (6 load cases → C) and `dataset` (6 + Hill-distributed random load cases, for ML).

---

## Architecture

- **`config.py`** — `SweepConfig` dataclass and all scenarios.
- **`run.py`** — runs a scenario (computation + plotting).
- **`plot.py`** — figures and summaries of one scenario.
- **`plot_ellipse.py`** — overlay of the elliptical-fiber scenarios.
- **`composite_ref.py`** — constituent stiffnesses, Voigt/Reuss bounds, engineering constants.
- **`run_detached.ps1`**, **`run_ellipse.ps1`**, **`run_until.ps1`**, **`next_unit.py`** — long runs outside the IDE.

---

## Scenarios

| # | Name | Swept parameter | Fixed setup | Mode |
| :-: | :--- | :--- | :--- | :--- |
| 1 | `vf_sweep_cf_epoxy` | Vf 0.1…0.6 | C-fiber/Epoxy, square, 2/row, N = 32 | stiffness |
| 2 | `vf_sweep_glass_epoxy` | Vf 0.1…0.6 | E-glass/Epoxy, as 1 | stiffness |
| 3 | `jitter_sweep_cf_epoxy` | jitter 0…0.6 | hexagonal, 4/row, Vf 0.4, 5 real. | stiffness |
| 4 | `jitter_full_sweep_cf_epoxy` | jitter 0…1 | as 3 | stiffness |
| 5 | `size_sweep_cf_epoxy` | N = 16, 32, 64 | square, 2/row, Vf 0.4 | stiffness |
| 6 | `vf_dataset_cf_epoxy` | Vf 0.1…0.6 | as 1, N = 32 (ANSYS ran out of RAM) | dataset |
| 7 | `vf_dataset_cf_epoxy_n25` | Vf 0.1…0.6 | as 1, N = 25, ANSYS | dataset |
| 8 | `vf_dataset_cf_epoxy_n25_fft` | Vf 0.1…0.6 | as 7, FFT, compared with 7 | dataset |
| 9 | `aspect_sweep_cf_epoxy` | a/b 1…3 | elliptical, 1/row, Vf 0.2, N = 32 | stiffness |
| 10–12 | `fscatter_ab{15,2,3}_cf_epoxy` | rotation scatter 0.001…180° | a/b = 1.5 / 2 / 3, 5 real. | stiffness |
| 13 | `aspect_dataset_cf_epoxy_n25` | a/b = 1 | as 9, N = 25 | dataset |
| 14–16 | `fscatter_ab{15,2,3}_dataset_cf_epoxy_n25` | scatter 0.001, 90, 180° | as 10–12, N = 25 | dataset |
| — | `fft_bench_n25` | Vf 0.1 | FFT timing benchmark | stiffness |

---

## Usage

Set `MATVIZ3D_EXE` (path to `MatViz3D.exe`) and `MATVIZ3D_DLL_DIRS` (Qt/HDF5 DLL folders, `;`-separated), then:

```bash
python run.py vf_sweep_cf_epoxy              # compute (resumes) and plot
python run.py vf_sweep_cf_epoxy --plot-only  # redraw only
python run.py vf_sweep_cf_epoxy --report     # + FFT vs ANSYS table
python plot_ellipse.py [dataset]             # elliptical-fiber overlay
```

Long runs: `powershell -File run_detached.ps1 <scenario>` (log in `runs/<scenario>/run.log`).

### New scenario

Copy a scenario in `config.py` and change only what you need:

```python
my_sweep = _register(SweepConfig(
    name="my_sweep",
    sweep_axis="vf", start=0.1, stop=0.6, step=0.1,   # or custom_values=[...]
    matrix_material="Epoxy", fiber_material="C-fiber",
    composite_dim="1d", packing="square", fibers_per_row=2, size=32,
    solvers=["fft", "ansys"], realizations=1,
    rundir="runs/my_sweep",
))
```

### Composite parameters

| Parameter | Values | Description |
| :--- | :--- | :--- |
| `sweep_axis` | `vf`, `size`, `jitter`, `fiber_scatter`, `aspect` | Parameter varied along the sweep |
| `start`, `stop`, `step` / `custom_values` | numbers | Sweep values |
| `matrix_material` | `Epoxy`, … | Matrix material (MatViz3D DB) |
| `fiber_material` | `C-fiber`, `E-glass`, `SiC`, `Al2O3` | Fiber material |
| `composite_dim` | `1d`, `2d`, `3d` | Fibers along Z / X+Y / X+Y+Z |
| `packing` | `square`, `hexagonal` | Fiber arrangement |
| `vf` | 0…1 | Target fiber volume fraction |
| `fibers_per_row` | integer | Fibers per row of the cell |
| `fiber_aspect_ratio` | ≥ 1 | Cross-section semi-axes a/b (1 = circle) |
| `fiber_angle_scatter` | 0…180° | Rotation scatter of the cross-section (use 0.001 instead of 0 for ellipses) |
| `fiber_center_jitter` | 0…1 | Random shift of fiber centers, in half-pitches |
| `fiber_allow_overlap` | `True`/`False` | Allow jittered fibers to overlap |
| `size` | integer | RVE grid N (N³ voxels); powers of two are fastest for FFT |
| `mode` | `stiffness`, `dataset` | Homogenization mode |
| `solvers` | `["fft"]`, `["ansys"]`, both | Solvers |
| `realizations` | integer | Random seeds per point (≥ 2 for a scatter band) |
| `ansys_np` | integer | ANSYS processes |
| `rundir` | path | Output folder |

---

## Output Files

In `runs/<scenario>/`: `results.csv` (all values per unit, GPa), `criteria_summary.txt`,
`comparison_summary.txt/.csv`, `sweep.png/.eps`, `comparison.png/.eps`, and `<scenario>.hdf5`
(all raw MatViz3D results; not stored in git).

---

<a id="українська"></a>

# Серії розрахунків волокнистих композитів і порівняння розв'язувачів у MatViz3D

Відновлювані параметричні серії для волокнистих композитів, побудованих алгоритмом MatViz3D `Composite`.
Для кожного значення параметра й кожної реалізації генерується періодичний 3D RVE, який гомогенізується
розв'язувачем **FFT** (Moulinec–Suquet) та/або **ANSYS** (МСЕ). Обчислюються ефективна жорсткість $C_{ij}$ і
технічні сталі ($E_i, G_{ij}, \nu_{12}, \nu_{31}$), перевіряються межі Фойгта/Ройсса, будуються рисунки
(PNG + EPS) і таблиці порівняння FFT та ANSYS.

---

## Можливості

1. **Сценарії в Python** — кожен розрахунок задається як `SweepConfig` у `config.py` і запускається за назвою.
2. **FFT та ANSYS** на однаковій геометрії й зернах, з відносною розбіжністю `|FFT − ANSYS| / ANSYS`.
3. **Критерії прийнятності** — досягнута й цільова Vf, Ройсс ≤ E, G ≤ Фойгт, допуск розв'язувачів (`criteria_summary.txt`).
4. **Відновлення** — готові одиниці зберігаються в `results.csv`, повторний запуск їх пропускає.
5. **Два режими** — `stiffness` (6 навантажень → C) і `dataset` (6 + випадкові навантаження за розподілом Гілла, для ML).

---

## Структура

- **`config.py`** — клас `SweepConfig` і всі сценарії.
- **`run.py`** — запуск сценарію (розрахунок + рисунки).
- **`plot.py`** — рисунки й підсумки одного сценарію.
- **`plot_ellipse.py`** — зведений рисунок для еліптичних волокон.
- **`composite_ref.py`** — жорсткості компонентів, межі Фойгта/Ройсса, технічні сталі.
- **`run_detached.ps1`**, **`run_ellipse.ps1`**, **`run_until.ps1`**, **`next_unit.py`** — довгі розрахунки поза IDE.

---

## Сценарії

| № | Назва | Змінний параметр | Фіксовані параметри | Режим |
| :-: | :--- | :--- | :--- | :--- |
| 1 | `vf_sweep_cf_epoxy` | Vf 0.1…0.6 | вуглеволокно/епоксид, квадр., 2/ряд, N = 32 | stiffness |
| 2 | `vf_sweep_glass_epoxy` | Vf 0.1…0.6 | скловолокно/епоксид, як 1 | stiffness |
| 3 | `jitter_sweep_cf_epoxy` | зміщення 0…0.6 | гексаг., 4/ряд, Vf 0.4, 5 реал. | stiffness |
| 4 | `jitter_full_sweep_cf_epoxy` | зміщення 0…1 | як 3 | stiffness |
| 5 | `size_sweep_cf_epoxy` | N = 16, 32, 64 | квадр., 2/ряд, Vf 0.4 | stiffness |
| 6 | `vf_dataset_cf_epoxy` | Vf 0.1…0.6 | як 1, N = 32 (ANSYS вичерпав RAM) | dataset |
| 7 | `vf_dataset_cf_epoxy_n25` | Vf 0.1…0.6 | як 1, N = 25, ANSYS | dataset |
| 8 | `vf_dataset_cf_epoxy_n25_fft` | Vf 0.1…0.6 | як 7, FFT, порівняння з 7 | dataset |
| 9 | `aspect_sweep_cf_epoxy` | a/b 1…3 | еліптичні, 1/ряд, Vf 0.2, N = 32 | stiffness |
| 10–12 | `fscatter_ab{15,2,3}_cf_epoxy` | розкид кута 0.001…180° | a/b = 1.5 / 2 / 3, 5 реал. | stiffness |
| 13 | `aspect_dataset_cf_epoxy_n25` | a/b = 1 | як 9, N = 25 | dataset |
| 14–16 | `fscatter_ab{15,2,3}_dataset_cf_epoxy_n25` | розкид 0.001, 90, 180° | як 10–12, N = 25 | dataset |
| — | `fft_bench_n25` | Vf 0.1 | тест швидкості FFT | stiffness |

---

## Використання

Задайте `MATVIZ3D_EXE` (шлях до `MatViz3D.exe`) і `MATVIZ3D_DLL_DIRS` (папки DLL Qt/HDF5 через `;`), потім:

```bash
python run.py vf_sweep_cf_epoxy              # розрахунок (з відновленням) і рисунки
python run.py vf_sweep_cf_epoxy --plot-only  # лише перемалювати
python run.py vf_sweep_cf_epoxy --report     # + таблиця FFT vs ANSYS
python plot_ellipse.py [dataset]             # зведений рисунок еліптичних волокон
```

Довгі розрахунки: `powershell -File run_detached.ps1 <scenario>` (журнал у `runs/<scenario>/run.log`).

### Новий сценарій

Скопіюйте сценарій у `config.py` і змініть лише потрібне (приклад — див. англійський розділ вище).

### Параметри композиту

| Параметр | Значення | Опис |
| :--- | :--- | :--- |
| `sweep_axis` | `vf`, `size`, `jitter`, `fiber_scatter`, `aspect` | Параметр, що змінюється в серії |
| `start`, `stop`, `step` / `custom_values` | числа | Значення серії |
| `matrix_material` | `Epoxy`, … | Матеріал матриці (БД MatViz3D) |
| `fiber_material` | `C-fiber`, `E-glass`, `SiC`, `Al2O3` | Матеріал волокон |
| `composite_dim` | `1d`, `2d`, `3d` | Волокна вздовж Z / X+Y / X+Y+Z |
| `packing` | `square`, `hexagonal` | Укладка волокон |
| `vf` | 0…1 | Цільова об'ємна частка волокон |
| `fibers_per_row` | ціле | Волокон у ряду комірки |
| `fiber_aspect_ratio` | ≥ 1 | Відношення півосей перерізу a/b (1 = коло) |
| `fiber_angle_scatter` | 0…180° | Розкид кута повороту перерізу (для еліпсів 0.001 замість 0) |
| `fiber_center_jitter` | 0…1 | Випадкове зміщення центрів волокон, у півкроках |
| `fiber_allow_overlap` | `True`/`False` | Дозволити перетин зміщених волокон |
| `size` | ціле | Розмір сітки RVE N (N³ вокселів); для FFT найшвидші степені двійки |
| `mode` | `stiffness`, `dataset` | Режим гомогенізації |
| `solvers` | `["fft"]`, `["ansys"]`, обидва | Розв'язувачі |
| `realizations` | ціле | Кількість випадкових реалізацій на точку (≥ 2 для смуги розкиду) |
| `ansys_np` | ціле | Процеси ANSYS (при ~8 ГБ RAM — 1) |
| `rundir` | шлях | Папка результатів |

---

## Вихідні файли

У `runs/<scenario>/`: `results.csv` (усі величини для кожної одиниці, ГПа), `criteria_summary.txt`,
`comparison_summary.txt/.csv`, `sweep.png/.eps`, `comparison.png/.eps` і `<scenario>.hdf5`
