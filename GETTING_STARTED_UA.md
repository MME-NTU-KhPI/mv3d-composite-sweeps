# Як запустити проєкт і змінювати параметри

Інструкція для нового користувача: від клонування репозиторію до власного розрахунку.

---

## 1. Що потрібно встановити заздалегідь

| Що | Навіщо | Примітка |
| :--- | :--- | :--- |
| **Windows** | скрипти запуску написані на PowerShell | |
| **Python 3.10+** | сам інструмент | перевірено на 3.12 |
| **Git** | клонувати репозиторій | |
| **MatViz3D.exe** + його DLL (Qt, MinGW, HDF5) | генерація RVE і FFT-розв'язувач | потрібен завжди |
| **ANSYS** | розв'язувач МСЕ | лише якщо в сценарії є `"ansys"` |

---

## 2. Встановлення (один раз)

### Крок 1. Клонувати репозиторій

```powershell
git clone https://github.com/MME-NTU-KhPI/mv3d-composite-sweeps.git
cd mv3d-composite-sweeps
```

### Крок 2. Створити віртуальне середовище (рекомендовано)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Якщо PowerShell не дає активувати середовище, виконайте один раз:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### Крок 3. Встановити бібліотеки

```powershell
pip install numpy h5py matplotlib
pip install git+https://github.com/MME-NTU-KhPI/matviz3d-py.git
```

`pymv3d` (з репозиторію `matviz3d-py`) — це наш запускач MatViz3D. Через PyPI його не встановити.

### Крок 4. Вказати, де лежить MatViz3D

Тимчасово, лише для поточного вікна PowerShell:

```powershell
$env:MATVIZ3D_EXE      = "C:\path\to\MatViz3D.exe"
$env:MATVIZ3D_DLL_DIRS = "C:\Qt\Tools\mingw1310_64\bin;C:\Qt\6.x.x\mingw_64\bin;C:\HDF5\bin"
```

Назавжди (після цього відкрийте нове вікно терміналу):

```powershell
setx MATVIZ3D_EXE      "C:\path\to\MatViz3D.exe"
setx MATVIZ3D_DLL_DIRS "C:\Qt\Tools\mingw1310_64\bin;C:\Qt\6.x.x\mingw_64\bin;C:\HDF5\bin"
```

Підставте свої шляхи. Папки DLL розділяються крапкою з комою `;`.

### Крок 5. Перевірити встановлення

```powershell
python run.py vf_sweep_cf_epoxy --plot-only
```

Ця команда нічого не рахує: вона лише малює рисунки з уже готового `results.csv`.
Якщо в `runs\vf_sweep_cf_epoxy\` з'явилися `sweep.png` і `comparison.png`, Python і бібліотеки встановлені правильно.

---

## 3. Запуск розрахунків

```powershell
python run.py <назва_сценарію>             # розрахунок + рисунки
python run.py <назва_сценарію> --report    # + таблиця порівняння FFT vs ANSYS
python run.py <назва_сценарію> --plot-only # лише перемалювати рисунки
python run.py <назва_сценарію> --force     # перерахувати все з нуля
python run.py <назва_сценарію> --threads 8 # кількість потоків FFT
python run.py <назва_сценарію> --ansys-np 2 # кількість процесів ANSYS
```

Список усіх назв сценаріїв виводить `python run.py -h`. Їх також видно в `README.md` і `config.py`.

### Довгі розрахунки (незалежно від терміналу)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File run_detached.ps1 <назва_сценарію> --report
```

Стежити за ходом розрахунку:

```powershell
Get-Content runs\<назва_сценарію>\run.log -Wait -Tail 20
```

Зупинити чергу акуратно: створіть порожній файл `runs\STOP`. Нові сценарії не стартуватимуть, а поточний розрахунок дорахується до кінця.

### Перервали розрахунок?

Просто запустіть ту саму команду ще раз. Готові точки записані в `results.csv` і будуть пропущені.

---

## 4. Як змінювати параметри

Усі параметри задаються у файлі **`config.py`**. Кожен сценарій там — це окремий блок `SweepConfig(...)`.

### Спосіб 1 (рекомендований): новий сценарій

1. Відкрийте `config.py`.
2. Знайдіть сценарій, найближчий до потрібного, наприклад:

   ```python
   vf_sweep_cf_epoxy = _register(SweepConfig(
       name="vf_sweep_cf_epoxy",
       sweep_axis="vf", start=0.1, stop=0.6, step=0.1,
       matrix_material="Epoxy", fiber_material="C-fiber",
       composite_dim="1d", packing="square", fibers_per_row=2, size=32,
       solvers=COMPOSITE_SOLVERS, realizations=1,
       rundir="runs/vf_sweep_cf_epoxy",
   ))
   ```

3. Скопіюйте весь блок у кінець файлу.
4. У копії змініть **назву (у двох місцях)**, **`rundir`** і потрібні параметри:

   ```python
   my_test = _register(SweepConfig(
       name="my_test",
       sweep_axis="vf", start=0.2, stop=0.5, step=0.05,
       matrix_material="Epoxy", fiber_material="E-glass",
       composite_dim="1d", packing="hexagonal", fibers_per_row=4, size=32,
       solvers=["fft"], realizations=3,
       rundir="runs/my_test",
   ))
   ```

5. Збережіть файл і запустіть:

   ```powershell
   python run.py my_test
   ```

### Спосіб 2: змінити наявний сценарій

Можна змінити значення прямо в наявному блоці, але тоді **обов'язково запускайте з `--force`**:

```powershell
python run.py vf_sweep_cf_epoxy --force
```

> ⚠️ **Чому це важливо.** Програма вважає точку готовою за трьома ознаками: значення параметра,
> номер реалізації і розв'язувач. Матеріал, розмір сітки, укладку тощо вона **не враховує**.
> Якщо змінити, наприклад, матеріал і запустити без `--force`, старі точки не перерахуються
> і результати перемішаються. Водночас `--force` перезапише результати, що зберігаються в репозиторії,
> тому безпечніше створювати новий сценарій (спосіб 1).

### Параметри

| Параметр | Що задає | Можливі значення |
| :--- | :--- | :--- |
| `name` | назва для запуску | будь-яка, без пробілів |
| `rundir` | папка результатів | `"runs/<назва>"` |
| `sweep_axis` | який параметр змінюється | `vf`, `size`, `jitter`, `fiber_scatter`, `aspect` |
| `start`, `stop`, `step` | діапазон його значень | числа |
| `custom_values` | конкретні значення замість діапазону | `[0.1, 0.25, 0.4]` |
| `mode` | режим гомогенізації | `stiffness` (6 навантажень → C), `dataset` (+ випадкові навантаження, для ML) |
| `matrix_material` | матеріал матриці | `Epoxy`, … |
| `fiber_material` | матеріал волокон | `C-fiber`, `E-glass`, `SiC`, `Al2O3` |
| `composite_dim` | напрям волокон | `1d` (Z), `2d` (X+Y), `3d` (X+Y+Z) |
| `packing` | укладка | `square`, `hexagonal` |
| `vf` | об'ємна частка волокон | 0…1 |
| `fibers_per_row` | волокон у ряду комірки | ціле число |
| `fiber_aspect_ratio` | відношення півосей перерізу a/b | ≥ 1 (1 = коло) |
| `fiber_angle_scatter` | розкид кута повороту перерізу, ° | 0…180 (для еліпсів `0.001` замість `0`) |
| `fiber_center_jitter` | випадкове зміщення центрів, у півкроках | 0…1 |
| `fiber_allow_overlap` | дозволити перекриття волокон | `True` / `False` |
| `size` | сітка RVE N (N³ вокселів) | `16`, `32`, `64` (степені двійки для FFT найшвидші) |
| `solvers` | розв'язувачі | `["fft"]`, `["ansys"]`, `["fft", "ansys"]` |
| `realizations` | випадкових реалізацій на точку | ≥ 1 (≥ 2 для смуги розкиду) |
| `ansys_np` | процесів ANSYS | `1` при ~8 ГБ RAM |
| `threads` | потоків FFT | ціле число або `None` (авто) |

Параметр, вказаний у `sweep_axis`, бере значення з `start`/`stop`/`step` (або `custom_values`).
Усі інші параметри фіксовані. Значення за замовчуванням наведено на початку `config.py`, у класі `SweepConfig`.

### Часті приклади

| Хочу… | Що змінити |
| :--- | :--- |
| інший матеріал волокна | `fiber_material="E-glass"` |
| інший діапазон Vf | `start=0.2, stop=0.5, step=0.05` |
| конкретні значення | `custom_values=[0.15, 0.35, 0.55]` |
| рахувати без ANSYS | `solvers=["fft"]` |
| швидкий пробний розрахунок | `size=16`, `realizations=1` |
| еліптичні волокна | `fiber_aspect_ratio=2.0`, `fiber_angle_scatter=0.001` |
| розкид властивостей | `realizations=5` |

---

## 5. Де результати

У папці `runs\<назва_сценарію>\`:

| Файл | Вміст |
| :--- | :--- |
| `results.csv` | усі значення для кожної точки (ГПа) |
| `criteria_summary.txt` | перевірка критеріїв (Vf, межі Фойгта/Ройсса) |
| `comparison_summary.txt/.csv` | порівняння FFT та ANSYS |
| `sweep.png/.eps`, `comparison.png/.eps` | рисунки |
| `<назва>.hdf5` | усі сирі результати MatViz3D (у git не зберігаються) |
| `run.log` | журнал розрахунку (при запуску через `run_detached.ps1`) |

---

## 6. Типові проблеми

| Повідомлення / симптом | Причина і рішення |
| :--- | :--- |
| `MatViz3D executable not found` | не задано або неправильно задано `MATVIZ3D_EXE` (крок 4) |
| `ModuleNotFoundError: pymv3d` | не встановлено `pymv3d` або не активовано `.venv` (кроки 2–3) |
| MatViz3D одразу завершується без результату | бракує DLL: перевірте шляхи в `MATVIZ3D_DLL_DIRS` |
| ANSYS падає посеред серії | бракує оперативної пам'яті: `ansys_np=1`, менший `size` або закрийте інші програми |
| розрахунок «нічого не робить» | усі точки вже є в `results.csv`; потрібен `--force` або новий сценарій |
| `invalid choice` для назви сценарію | помилка в назві або сценарій не зареєстровано через `_register(...)` у `config.py` |
