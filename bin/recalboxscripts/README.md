# Scripts remotos de RecalboxGUI

Esta carpeta contiene exclusivamente los scripts administrados por RecalboxGUI
que deban copiarse temporalmente y ejecutarse dentro de un equipo Recalbox.

Los scripts deben:

- ejecutarse mediante su intérprete explícito (`python3`, `bash`, etc.);
- admitir operaciones de simulación antes de cualquier cambio destructivo;
- producir resultados estructurados cuando corresponda;
- escribir datos de trabajo únicamente en las rutas remotas asignadas;
- poder eliminarse del equipo Recalbox al finalizar el trabajo;
- mantener una versión identificable y una interfaz documentada.

## Progreso estructurado

Los scripts que soporten progreso deben emitirlo únicamente al solicitarlo de
forma explícita. `recalbox-clean-media.sh --progress` utiliza líneas con prefijo
`RCGUI|`, que la aplicación puede distinguir de la salida destinada al usuario:

```text
RCGUI|PLAN|sistemas|archivos|unidades_totales|dry_run
RCGUI|PROGRESS|unidades_completadas|unidades_totales|sistema_actual|sistemas
RCGUI|SYSTEM|DONE|indice|comprobados|referenciados|huerfanos|eliminados|errores
RCGUI|RESULT|comprobados|referenciados|huerfanos|eliminados|errores|omitidos
```
