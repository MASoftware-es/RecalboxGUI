# RecalboxGUI

RecalboxGUI es una aplicación gráfica para Linux destinada a administrar uno o varios equipos Recalbox desde otro ordenador. Se conecta mediante SSH para ejecutar tareas de mantenimiento y utiliza Samba para abrir las carpetas de ROM en el explorador de archivos.

La aplicación permite guardar distintos entornos Recalbox, conectarse a ellos de forma independiente y utilizar herramientas de reparación, limpieza y validación sin trabajar directamente desde una terminal.

## Funciones disponibles

- Gestión de varios equipos Recalbox.
- Conexiones remotas mediante SSH.
- Apertura anónima de carpetas compartidas mediante Samba.
- Cambio de idioma sin reiniciar la aplicación.
- Idiomas disponibles: Español, English, Italiano, Français y Deutsch.
- Temas visuales intercambiables en caliente.
- Conservación del idioma, tema, entornos, posición y tamaño de la ventana.
- Corrección del problema de montaje de discos NTFS mediante `ntfs3`.
- Búsqueda y limpieza de imágenes, miniaturas y vídeos huérfanos.
- Validación y corrección de ROM de MAME.
- Validación y corrección de ROM de Neo Geo.
- Edición remota de los metadatos `gamelist.xml` y sus imágenes.
- Reinicio de EmulationStation.
- Reinicio o apagado seguro del equipo Recalbox.

## Requisitos

### Ordenador donde se ejecutará RecalboxGUI

RecalboxGUI está preparado para ejecutarse en un escritorio Linux. El instalador reconoce las siguientes familias de distribuciones:

- Debian y Ubuntu.
- Fedora y RHEL.
- Arch Linux.
- openSUSE y SUSE.

Se necesita:

- Bash 4.2 o posterior.
- Python 3.10 o posterior.
- Un escritorio gráfico Linux.
- Acceso de red al equipo Recalbox.
- Cliente OpenSSH.
- Soporte GVfs para Samba.

El script de instalación comprueba e instala las dependencias del sistema correspondientes, además de crear un entorno virtual privado con PySide6 y Paramiko.

### Equipo Recalbox

El equipo Recalbox debe:

- Estar encendido y conectado a la misma red o ser accesible desde el ordenador.
- Tener disponible el servicio SSH.
- Permitir la conexión con el usuario configurado.
- Compartir por Samba la carpeta `share` si se desea abrir las carpetas de ROM desde el explorador.

Los valores predeterminados utilizados al crear un entorno son:

- Equipo: `recalbox.local`
- Usuario: `root`
- Contraseña: `recalboxroot`
- Carpeta de ROM: `/recalbox/share/roms`

Estos valores pueden cambiarse para cada entorno.

## Instalación

Descomprime o copia el proyecto en una carpeta perteneciente a tu usuario. Abre una terminal dentro de la raíz del proyecto y ejecuta:

```bash
bin/setup --install
```

El instalador mostrará los paquetes del sistema que falten y pedirá confirmación antes de instalarlos. Es posible aceptar automáticamente la instalación con:

```bash
bin/setup --install --yes
```

Cuando sea necesario instalar paquetes del sistema se solicitará la contraseña de `sudo`. Las dependencias Python se guardan únicamente en `gui/.venv`, sin alterar la instalación global de Python.

Para comprobar una instalación existente sin realizar cambios:

```bash
bin/setup --check
```

La ayuda del instalador se muestra mediante:

```bash
bin/setup --help
```

## Iniciar la aplicación

Desde la raíz del proyecto ejecuta:

```bash
bin/recalboxgui
```

En la primera ejecución la ventana se muestra centrada. Al cerrar la aplicación se guardan su posición y tamaño para el siguiente inicio.

## Configuración de un entorno Recalbox

1. Abre el menú **Aplicación**.
2. Selecciona **Entornos Recalbox…**.
3. Pulsa **Añadir**.
4. Completa o revisa los siguientes campos:
   - Nombre visual del entorno.
   - IP o nombre de red del equipo Recalbox.
   - Usuario de conexión.
   - Contraseña de conexión.
   - Ruta de la carpeta de ROM.
5. Pulsa **Guardar**.

El nombre visual identifica el equipo dentro del menú y en su pestaña de conexión. El botón con forma de ojo permite mostrar u ocultar la contraseña mientras se edita.

Las contraseñas se guardan cifradas en la configuración del perfil del usuario. Este mecanismo evita que aparezcan como texto legible en el archivo, pero no sustituye a un almacén de credenciales del sistema ni protege frente a alguien con acceso completo al programa y al perfil del usuario.

## Conectarse a Recalbox

1. Abre **Aplicación > Conectar con entorno**.
2. Selecciona el nombre del entorno.
3. Espera a que se establezca la conexión SSH.

Si la conexión se realiza correctamente, aparecerá una pestaña con el nombre del entorno. Un entorno conectado no puede abrirse una segunda vez.

Para desconectarlo, pulsa la **X** de su pestaña y confirma el cierre. Todas las sesiones SSH y los archivos temporales remotos asociados se cierran o eliminan al cerrar la pestaña o la aplicación.

Si no se puede conectar, comprueba:

- Que Recalbox esté encendido.
- Que `recalbox.local` responda en la red o utiliza su dirección IP.
- Que SSH esté disponible.
- Que el usuario y la contraseña sean correctos.
- Que un cortafuegos no esté bloqueando el puerto SSH.

El hecho de que Samba funcione no garantiza que SSH esté habilitado o accesible.

## Utilidades

Después de conectarte, abre la pestaña interna **Utilidades** y selecciona una herramienta de la lista situada a la izquierda.

### Corregir BUG de montaje NTFS

Corrige un problema que impide montar correctamente determinados discos NTFS y utilizarlos para reproducir películas desde Kodi. La utilidad comprueba primero si el parche ya está aplicado y evita modificar el sistema si no es necesario.

Pulsa **Aplicar** para comprobar el estado y confirma la operación si hace falta instalar el parche.

### Limpiar archivos multimedia huérfanos

Compara las imágenes, miniaturas y vídeos de las carpetas seleccionadas con las referencias incluidas en `gamelist.xml`.

1. Marca las plataformas que quieras revisar.
2. Utiliza **Todo** o **Nada** para cambiar rápidamente la selección.
3. Pulsa **Probar** para obtener un resultado sin eliminar archivos.
4. Pulsa **Limpiar** para eliminar los medios huérfanos después de confirmar la operación.

Las carpetas vacías o sin archivo `gamelist.xml` se omiten. La barra muestra el progreso de la tarea.

> **Advertencia:** la opción **Limpiar** elimina definitivamente los archivos multimedia huérfanos. Es recomendable ejecutar primero **Probar** y revisar el resultado.

### Validar ROM de MAME

Examina las ROM del sistema MAME utilizando los cores realmente disponibles en el equipo Recalbox. Clasifica los archivos como válidos, incompatibles, desconocidos o protegidos porque otros juegos los necesitan.

1. Pulsa **Analizar** para generar un informe.
2. Revisa el resumen final.
3. Después de un análisis correcto se habilitará **Corregir**.
4. Pulsa **Corregir** para aplicar el último informe generado.

Las ROM nunca se borran. Las incompatibles se mueven a la carpeta `invalids` y las desconocidas a `unknown`. El usuario puede revisarlas y eliminarlas manualmente si lo desea. La corrección también actualiza `gamelist.xml`, la configuración específica y los medios que hayan dejado de estar referenciados.

El botón **Abrir carpeta de MAME** abre la carpeta correspondiente mediante Samba como usuario anónimo.

### Validar ROM de Neo Geo

Tiene el mismo flujo de análisis y corrección que el validador de MAME, pero trabaja únicamente con el sistema `neogeo`. No analiza `neogeocd`.

El validador detecta los cores y formatos declarados e instalados en Recalbox. Las ROM incompatibles o desconocidas se mueven a sus carpetas de cuarentena y nunca se eliminan automáticamente.

El botón **Abrir carpeta de NEOGEO** abre la carpeta mediante Samba como usuario anónimo.

### Reinicio de servicios

Esta utilidad contiene tres acciones independientes:

- **Reiniciar EmulationStation:** reinicia solamente la interfaz de Recalbox. Resulta útil para recargar sistemas, juegos y cambios de `gamelist.xml` sin reiniciar el equipo completo. La operación se bloquea si hay un juego, RetroArch o Kodi en ejecución.
- **Reiniciar Recalbox:** reinicia por completo el sistema remoto. La conexión y su pestaña se cerrarán automáticamente.
- **Apagar Recalbox:** apaga el sistema de forma segura. La conexión se cerrará y será necesario encender físicamente el equipo para volver a utilizarlo.

Todas estas acciones solicitan confirmación previa.

## Editor GameList

La pestaña **GameList** permite consultar y editar los metadatos de los juegos directamente en el `gamelist.xml` de cada sistema.

1. Selecciona una carpeta en la lista **Sistemas**.
2. Selecciona una entrada de la lista **Juegos**.
3. Edita la ruta, nombre, alias, género, identificador de género, editor, desarrollador, descripción, imagen o miniatura.
4. Pulsa **Recargar** para descartar los cambios del formulario y leer nuevamente el XML.
5. Pulsa **Guardar** para validar y actualizar el archivo remoto.

La ruta debe ser relativa a la carpeta del sistema y apuntar a un archivo de ROM existente. Los campos de texto se validan para garantizar que puedan escribirse en XML. Los atributos y metadatos que no aparecen en el formulario se conservan sin cambios.

Los botones **Subir** aceptan imágenes PNG, JPEG, WebP, BMP y GIF. La imagen se copia a `media/images` o `media/thumbnails`, se previsualiza en el formulario y su ruta se introduce automáticamente. Si ya existe un archivo con el mismo nombre, se genera otro terminado en `_2`, `_3`, etc., sin sobrescribirlo.

El guardado utiliza un archivo temporal y una sustitución atómica. Si `gamelist.xml` cambia después de haberlo cargado —por ejemplo, porque otro proceso lo actualiza— RecalboxGUI impide sobrescribirlo y solicita que se recarguen los datos.

## Idioma y tema visual

El idioma se cambia desde **Aplicación > Idioma**. El cambio se aplica inmediatamente y se conserva para la siguiente ejecución. El nombre de cada idioma aparece escrito en su propio idioma.

El tema se selecciona desde **Aplicación > Tema** y también se aplica y guarda inmediatamente.

## Ubicación de la configuración y archivos del usuario

RecalboxGUI no guarda datos temporales ni configuración personal dentro de la carpeta del proyecto, salvo el entorno virtual creado durante la instalación.

En un escritorio Linux convencional, Qt suele utilizar estas ubicaciones:

- Configuración: `~/.config/RecalboxGUI/RecalboxGUI.conf`
- Datos locales: `~/.local/share/RecalboxGUI/`
- Caché y archivos temporales: `~/.cache/RecalboxGUI/`
- Claves SSH conocidas: `~/.local/share/RecalboxGUI/ssh/known_hosts`

Las rutas exactas respetan `XDG_CONFIG_HOME`, `XDG_DATA_HOME` y `XDG_CACHE_HOME` cuando estas variables están definidas. También pueden variar ligeramente según el escritorio y la distribución Linux.

## Cerrar la aplicación

Selecciona **Aplicación > Salir...** y confirma el cierre. También puedes utilizar el botón de cierre de la ventana.

La aplicación no permite cerrarse mientras haya una conexión en curso o una utilidad remota ejecutándose. Antes de salir cierra todas las conexiones SSH, limpia los archivos remotos registrados y guarda la geometría de la ventana.

## Crear un paquete distribuible

Para generar un ZIP limpio del proyecto ejecuta:

```bash
bin/package
```

El paquete se crea en:

```text
dist/RecalboxGUI.zip
```

El ZIP excluye entornos virtuales, cachés, pruebas, archivos temporales, datos de desarrollo y la carpeta de scripts antiguos usada como referencia. En el equipo de destino basta con descomprimirlo y ejecutar:

```bash
bin/setup --install
```

## Estructura principal del proyecto

```text
RecalboxGUI/
├── bin/
│   ├── package                 Generación del paquete distribuible
│   ├── recalboxgui             Lanzador de la aplicación
│   ├── setup                   Instalación y comprobación de dependencias
│   └── recalboxscripts/        Scripts ejecutados temporalmente en Recalbox
├── gui/
│   ├── assets/                 Icono y sonidos
│   ├── components/             Componentes visuales reutilizables
│   ├── connection/             Conexiones SSH y ejecución remota
│   ├── dialogs/                Diálogos de la aplicación
│   ├── i18n/                   Catálogos de idiomas
│   ├── themes/                 Temas visuales
│   └── utilities/              Catálogo de utilidades
├── tests/                      Pruebas automatizadas
├── pyproject.toml              Metadatos y dependencias Python
└── leeme.md                    Este documento
```

Los scripts de `bin/recalboxscripts` se copian temporalmente al equipo Recalbox cuando se necesitan. No es necesario instalarlos manualmente en el sistema remoto.

## Solución de problemas

### El lanzador indica que no existe el entorno virtual

Ejecuta:

```bash
bin/setup --install
```

### La aplicación no inicia después de una actualización

Actualiza el entorno privado y vuelve a comprobarlo:

```bash
bin/setup --install
bin/setup --check
```

### Samba solicita credenciales

RecalboxGUI intenta montar el recurso `share` explícitamente como usuario anónimo. Comprueba que el soporte GVfs para Samba esté instalado ejecutando de nuevo `bin/setup --install` y que el recurso compartido sea accesible desde la red.

### La conexión SSH falla pero Samba funciona

Son servicios distintos. Verifica el acceso SSH desde una terminal:

```bash
ssh root@recalbox.local
```

Utiliza la IP del equipo si el nombre `recalbox.local` no se resuelve.

### Ha cambiado la identidad SSH del equipo

Revisa cuidadosamente que te estás conectando al equipo correcto. Las identidades conocidas se almacenan dentro del perfil del usuario, en el archivo `ssh/known_hosts` del directorio de datos de RecalboxGUI.

## Autoría

Desarrollado por **M.A Software**.

- Web: [https://masoftware.es](https://masoftware.es)
- Correo: [info@masoftware.es](mailto:info@masoftware.es)
