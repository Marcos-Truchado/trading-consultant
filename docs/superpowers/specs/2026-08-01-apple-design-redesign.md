# Rediseño estilo Apple — Dashboard IBKR (trading-consultant)

Fecha: 2026-08-01

## Contexto

`dashboard_ibkr.py` es una app Streamlit 1.36 de análisis técnico + operativa manual con IBKR.
La lógica (8 motores: Elliott, Regime, Momentum, SMC, Volume Profile, MTF, Scoring, Risk)
vive en `pipeline.py` y módulos hermanos y NO se toca. El rediseño es exclusivamente de la
capa de presentación, más dos ampliaciones de funcionalidad aprobadas.

## Objetivos

1. Rediseñar la interfaz al estilo Apple: dark mode profundo, materiales translúcidos,
   tipografía de sistema con tracking/leading correctos, jerarquía clara, motion respetuosa.
2. Mantener el 100% de las funcionalidades actuales (conexión IBKR, cuenta, posiciones,
   análisis, gráfico, niveles Fibonacci, tabs de desglose, envío manual de órdenes).
3. Ampliar con: **Panel Resumen Ejecutivo** (tarjetas glassmorphism) y **Historial de
   Análisis** (persistencia SQLite + tab de comparación/carga).

## No-objetivos

- No tocar `pipeline.py` ni los motores (`elliott/`, `regime_detector.py`, etc.).
- No cambiar la arquitectura de conexión IBKR ni la semántica de envío de órdenes
  (confirmación manual obligatoria, mapeo de puertos real/paper intacto).
- No migrar fuera de Streamlit.

## Sección 1 — Tema visual y estructura

### config.toml (`.streamlit/config.toml`)

- `[theme]` con base dark: primaryColor `#0a84ff`, backgroundColor `#0a0a0f`,
  secondaryBackgroundColor `#16161c`, textColor `#f5f5f7`, font sans-serif.
- `[server] headless = true` no se cambia; layout wide ya configurado en código.
- Font: `-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif`.

### CSS global (inyectado al inicio del script)

- Background `#0a0a0f`; superficies `#16161c` con radios generosos (12-14px).
- Sidebar como barra translúcida: `background: rgba(22,22,28,0.85)` +
  `backdrop-filter: blur(20px) saturate(180%)`.
- Tipografía: títulos `-0.02em` tracking, pesos 600/700; cuerpo 400, line-height 1.5.
- Números tabulares (`font-variant-numeric: tabular-nums`) en métricas y precios.
- Métricas: label pequeña (11-12px, `#98989d`), valor grande (28-32px, semibold),
  sin cajas, delta con color semántico. Override de `.stMetric`.
- Botones: `border-radius: 10px`, `:active { transform: scale(0.97) }`,
  `transition: transform 100ms ease-out` (feedback en pointer-down).
- Tabs: barra inferior de acento (2px, `#0a84ff`), sin border duro, hover sutil.
- Inputs/selects: fondos `#1c1c22`, borders `#2c2c33`, focus ring azul.
- Scrollbars finos estilo macOS.
- `@media (prefers-reduced-motion: reduce)`: desactivar transiciones/animaciones.

### Plotly

- `chart_engine_v4.py` recibe un `template`/colores del tema: fondos transparentes,
  grid `#2c2c33`, texto `#f5f5f7`. Se pasa `theme="dark"` desde el dashboard sin
  cambiar la lógica de cálculo (solo la paleta al construir la figura).

## Sección 2 — Panel Resumen Ejecutivo

Tarjetas HTML custom (`unsafe_allow_html` + CSS de utilidad) sobre el gráfico:

| Card | Contenido |
| --- | --- |
| Score | Número 0-100 grande + anillo/cono de progreso + label veredicto |
| Dirección | Flecha Elliott (↑/↓/—) + estado de onda + gap velas |
| Precio | Precio actual + % riesgo al stop |
| RR | RR1 + badge "Válido" (verde) / "Bajo" (ámbar) |

- Alertas STALE y REGIMEN BLOQUEA como chips de aviso compactos (ámbar/rojo),
  no bloques `st.error` a pantalla completa.
- Aparición con `transition: opacity 200ms`; sin animación bajo reduced-motion.
- Solo se renderiza tras un análisis exitoso.

## Sección 3 — Historial de Análisis

- Módulo nuevo `analysis_history.py`: peewee + SQLite `analisis_history.db` junto al proyecto.
  Modelo `AnalysisRecord`: ticker, ts (datetime), score, veredicto, action, precio,
  rr, dirección (bull/bear/neutral), estado onda, deviation, period, bar_size.
- En cada análisis exitoso se inserta una fila (dedupe por ticker+ts).
- Tab "Historial" (se añade a los 5 tabs existentes): tabla con color semántico por
  veredicto, orden desc por fecha, y botón "Cargar" que restaura ese snapshot
  (ticker/periodo/desviación) y re-ejecuta el análisis.
- Creación de tabla idempotente (`create_table()` en arranque).

## Sección 4 — Verificación

1. `bun`/python: `streamlit run dashboard_ibkr.py` arranca sin errores.
2. `git diff` de `pipeline.py` y motores = vacío (lógica intacta).
3. Test sin IBKR: script de prueba que alimenta el pipeline con datos sintéticos
   (pandas OHLCV aleatorio) y verifica que el render del resumen + historial
   funcionan (no hay IBKR en CI local).
4. Revisar en navegador: tema, tipografía, métricas, tabs, resumen ejecutivo.
