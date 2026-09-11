# valora-etl-pipeline

Pipeline ETL que extrae anuncios de inmuebles residenciales de metrocuadrado.com, los
sanea contra un conjunto de reglas de calidad y deja dos datasets listos para análisis:
lo confiable y lo rechazado, cada rechazo con su motivo.

Todo corre en Docker. No hace falta instalar Python, ni Playwright, ni Chromium en la
máquina anfitriona.

---

## Arranque rápido

Tres comandos desde cero en una máquina nueva:

```bash
git clone <url-del-repo> valora-etl-pipeline
cd valora-etl-pipeline
docker compose run --rm pipeline
```

Eso construye la imagen la primera vez (5–10 min: instala Chromium), corre el **extract**
y encadena el **transform**.

**Verificación** — al terminar debe existir esto:

```bash
ls data/processed/
# anuncios.csv  anuncios.parquet  cuarentena.csv  cuarentena.parquet  transform_resumen.json
```

Y el resumen de la corrida:

```bash
cat data/processed/transform_resumen.json
```

> **Ojo con el tiempo.** El extract son seis barridos contra el sitio real y tarda
> **3–4 horas**. Si sólo querés probar que el entorno funciona, corré un barrido chico:
>
> ```bash
> docker compose run --rm scraper python src/extract.py --tipos apartaestudio \
>   --operaciones arriendo --max-paginas 2 --sin-excel
> docker compose run --rm transform
> ```

---

## Requisitos

| | Versión | Nota |
|---|---|---|
| Docker Engine | 20.10+ | Con el plugin `compose` v2 (`docker compose`, sin guion) |
| Espacio en disco | ~3 GB | La imagen con Chromium pesa ~1,5 GB |
| Python | *(opcional)* 3.11 | Sólo si querés correr sin Docker |

Comprobá que tenés lo necesario:

```bash
docker --version && docker compose version
```

---

## Los servicios

Todos comparten la misma imagen y montan `./data` como volumen, así que los archivos
quedan en tu disco, no dentro del contenedor.

| Servicio | Comando | Qué hace | Cuánto tarda |
|---|---|---|---|
| `pipeline` | `docker compose run --rm pipeline` | Extract + transform + enrich encadenados | 3–4 h |
| `scraper` | `docker compose run --rm scraper` | Sólo etapa 1: scrapea a `data/raw/` | 3–4 h |
| `transform` | `docker compose run --rm transform` | Sólo etapa 2: `data/raw/` → `data/processed/` | segundos |
| `enrich` | `docker compose run --rm enrich` | Sólo etapa 3: agrega el contexto del barrio | 1–2 h la 1.ª vez, segundos después |
| `db` | `docker compose up -d db` | Postgres 16, para la futura etapa de carga | — |
| `pipeline-periodico` | ver abajo | El pipeline en bucle, cada N horas | permanente |

### Ejecución periódica

```bash
docker compose --profile periodico up -d pipeline-periodico
docker compose logs -f pipeline-periodico   # seguir la corrida
docker compose --profile periodico down     # detener
```

El intervalo se cambia con `INTERVALO_HORAS` en `docker-compose.yml` (por defecto 24).
Si el extract falla, el transform **no** corre: no tiene sentido reprocesar datos viejos.
Y si el transform falla, tampoco corre el enrich: no hay stage limpio que enriquecer.

### El enriquecimiento y su caché

La etapa 3 le pega a cuatro servicios públicos (OpenStreetMap, Nominatim, el servicio de
estrato de Esri Colombia y el de delitos de la SCJ de Bogotá). La **primera** corrida tarda
una o dos horas; las siguientes son de segundos, porque **cada respuesta queda cacheada en
`data/external/`**.

Ese caché es lo que hace la etapa reanudable: si la corrida se corta a mitad —o Overpass
devuelve 504, que pasa seguido—, volver a lanzarla **retoma donde quedó** en vez de
re-descargar todo. Borrar `data/external/` es válido pero cuesta otra corrida completa.

```bash
docker compose run --rm enrich                    # 15 ciudades (85 % de los anuncios)
docker compose run --rm enrich --ciudades 5       # más rápido, menos cobertura
docker compose run --rm enrich --sin-pois         # omite los puntos de interés
```

### La base de datos

`db` levanta un Postgres 16 en `localhost:5432` (usuario `gpa`, contraseña `gpa`, base
`metrocuadrado`). **Hoy ningún código lo usa** — queda listo para la etapa de carga (Load),
que todavía no existe.

---

## Qué produce

```
data/
├── raw/                      ← etapa 1 (extract), se versiona
│   ├── anuncios_arriendo.{csv,xlsx}
│   ├── anuncios_venta.{csv,xlsx}
│   ├── ultima_extraccion.json    manifiesto de la corrida
│   └── historico/                snapshots con fecha (--snapshot), NO se versiona
├── processed/                ← etapas 2 y 3, NO se versiona: se regenera
│   ├── anuncios.{csv,parquet}          stage limpio: salida del transform
│   ├── cuarentena.{csv,parquet}        rechazadas, con `motivo_rechazo`
│   ├── transform_resumen.json          conteos de la corrida
│   ├── anuncios_enriquecido.{csv,parquet}  stage limpio + contexto del barrio
│   └── enrich_resumen.json             cobertura y salud del enriquecimiento
└── external/                 ← caché de las APIs públicas, NO se versiona
    ├── bbox_*.json                     bounding box por ciudad (Nominatim)
    ├── osm_*.json                      barrios y jerarquía administrativa (Overpass)
    ├── pois_*.json                     puntos de interés por ciudad (Overpass)
    ├── estrato_*.json                  estrato por barrio (Esri Colombia)
    └── crimen_bogota_*.json            delitos por localidad (SCJ Bogotá)
```

**La cuarentena no es un descarte, es una separación.** Queda en disco, auditable, y si
una regla resulta demasiado estricta se reprocesa desde ahí.

**Parquet además de CSV** porque preserva los tipos (enteros nullable, booleanos, fechas)
que el CSV degrada a texto y obliga a re-inferir en cada lectura.

### Las dos alarmas que hay que mirar en cada corrida

En `transform_resumen.json`:

| Campo | Si se mueve de golpe |
|---|---|
| `tasa_rechazo_%` | O el sitio cambió, o una regla de parseo se rompió |
| `acuerdo_slug_barrido_%` | El filtro de la fuente se está degradando: el problema está en el **extract**, no en el transform |

Son las dos alarmas más baratas del pipeline.

---

## Correr sin Docker

Útil para desarrollar o para trabajar los notebooks. Necesitás Python 3.11.

**Linux / macOS**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install --with-deps chromium    # sólo si vas a correr el extract
```

**Windows (PowerShell)**

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

Después:

```bash
python src/extract.py --snapshot
python src/transform.py
```

Los comandos se corren **desde la raíz del repo**: las rutas por defecto (`data/raw`,
`data/processed`) son relativas al directorio actual.

### Notebooks

El análisis exploratorio vive en `notebooks/` y necesita dependencias extra:

```bash
pip install -r requirements-dev.txt
jupyter lab
```

| Notebook | Contenido |
|---|---|
| `eda.ipynb` | Análisis exploratorio: de acá salen las reglas R2–R12 y D0–D7 |
| `transform.ipynb` | Boceto del flujo de transformación, ya portado a `src/transform.py` |
| `scraper_metrocuadrado.ipynb` | Prototipo original del scraper |

Los notebooks son **exploración**, no el pipeline. Lo que corre en producción es `src/`.

---

## Opciones de línea de comandos

Ambas etapas se configuran por CLI. `--help` en cualquiera lista todo.

**`src/extract.py`**

| Opción | Para qué |
|---|---|
| `--tipos apartaestudio apartamento casa` | Qué tipos barrer |
| `--operaciones arriendo venta` | Qué operaciones barrer |
| `--max-paginas N` | Techo de páginas del paginador (`0` = sin límite) |
| `--sin-excel` | No generar los `.xlsx` (más rápido) |
| `--snapshot` | Guardar además una copia con fecha en `data/raw/historico/` |

**`src/transform.py`**

| Opción | Para qué |
|---|---|
| `--entrada-dir` / `--salida-dir` | Cambiar las carpetas por defecto |
| `--operaciones arriendo venta` | Qué operaciones procesar |
| `--sin-validar` | Escribir las salidas aunque alguna validación falle |

También se controla con la variable de entorno `HEADLESS=true|false`, que decide si
Chromium abre ventana. En Docker siempre va en `true`.

**Códigos de salida:** `0` si todo salió bien, `1` si un barrido volvió vacío (extract) o
si alguna validación falló (transform). Sirven para encadenar en cron o CI.

---

**`src/enrich.py`**

| Flag | Por defecto | Para qué |
|---|---|---|
| `--ciudades N` | 15 | Cuántas ciudades enriquecer, por volumen de anuncios |
| `--radio-poi` | 1000 | Radio en metros para contar puntos de interés |
| `--radio-estrato` | 400 | Radio del envelope de estrato. **No bajarlo a 0**: el centroide de un barrio suele caer en una calle y el servicio devuelve cero manzanas |
| `--sin-pois` | — | Omite los puntos de interés |
| `--sin-criminalidad` | — | Omite los delitos por localidad |
| `--cache-dir` | `data/external` | Dónde viven las respuestas cacheadas |

## Cómo está armado el transform

El orden de las etapas no es negociable, y la razón está documentada en el código:

```
1. Normalizar esquema      →  contrato único de columnas + tipo desde el slug de la URL
2. Operación y duales      →  separa precio_venta / precio_arriendo
3. Saneamiento de precio   →  rellenos primero, rangos después
4. Saneamiento de área     →  rango + detección de área de lote
5. Derivar precio_m2       →  sólo sobre lo que sobrevivió a 3 y 4
6. Outliers IQR log        →  vallas por (operación, tipo)
7. Consolidar y separar    →  compuerta de calidad
```

Calcular `precio_m2` antes del paso 2 es el error clásico: se divide un precio de venta
que estaba en el feed de arriendo y el indicador nace roto.

Al final, `transform.py` corre **24 validaciones** sobre su propia salida (unicidad de la
llave, rangos, conservación de filas entre stages). Si alguna falla, sale con código 1.

---

## Estado y pendientes

- [x] Etapa 1 — Extract
- [x] Etapa 2 — Transform
- [x] Etapa 3 — Enrich (contexto geoespacial del barrio)
- [ ] Etapa 4 — Load a un lakehouse con MinIO + ClickHouse
- [ ] Convertir las validaciones de `transform.py` en tests con pytest
- [ ] Decidir si las vallas de outliers se congelan contra una línea base: hoy se
      recalculan en cada corrida, así que dos corridas pueden clasificar distinto la
      misma fila

**Deuda conocida en el extract:** sigue trayendo oficinas y bodegas que el transform
descarta después. Arreglarlo es eficiencia (horas de scraping desperdiciadas), no
corrección: el dato que llega al análisis ya está bien.
