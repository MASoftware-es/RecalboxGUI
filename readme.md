# RecalboxGUI

RecalboxGUI is a graphical Linux application for managing one or more Recalbox systems from another computer. It connects through SSH to perform maintenance tasks and uses Samba to open ROM folders in the file manager.

**Current version: 0.9.0**

The application can store multiple Recalbox environments, connect to each one independently, and provide repair, cleanup, and validation tools without requiring direct terminal access.

## Available features

- Management of multiple Recalbox systems.
- Remote connections through SSH.
- Anonymous access to shared folders through Samba.
- Language switching without restarting the application.
- Available languages: Español, English, Italiano, Français, and Deutsch.
- Themes that can be changed at runtime.
- Persistent language, theme, environments, window position, and window size.
- Repair of the NTFS disk mounting issue using `ntfs3`.
- Detection and cleanup of orphaned images, thumbnails, and videos.
- MAME ROM validation and correction.
- Neo Geo ROM validation and correction.
- Remote editing of `gamelist.xml` metadata and its images.
- EmulationStation restart.
- Safe restart or shutdown of the Recalbox system.

## Requirements

### Computer running RecalboxGUI

RecalboxGUI is designed to run on a Linux desktop. The installer recognizes the following distribution families:

- Debian and Ubuntu.
- Fedora and RHEL.
- Arch Linux.
- openSUSE and SUSE.

The following are required:

- Bash 4.2 or later.
- Python 3.10 or later.
- A Linux graphical desktop.
- Network access to the Recalbox system.
- OpenSSH client.
- GVfs Samba support.

The installation script checks and installs the appropriate system dependencies and creates a private virtual environment containing PySide6 and Paramiko.

### Recalbox system

The Recalbox system must:

- Be switched on and connected to the same network, or otherwise be reachable from the computer.
- Have the SSH service available.
- Allow connections using the configured user account.
- Share the `share` folder through Samba if ROM folders are to be opened in the file manager.

The default values used when creating an environment are:

- System: `recalbox.local`
- User: `root`
- Password: `recalboxroot`
- ROM folder: `/recalbox/share/roms`

These values can be changed separately for every environment.

## Installation

Extract or copy the project into a folder owned by your user account. Open a terminal in the project root and run:

```bash
bin/setup --install
```

The installer displays any missing system packages and asks for confirmation before installing them. Installation can be accepted automatically with:

```bash
bin/setup --install --yes
```

When system packages need to be installed, your `sudo` password will be requested. Python dependencies are stored only in `gui/.venv` and do not modify the global Python installation.

To check an existing installation without making changes, run:

```bash
bin/setup --check
```

Installer help is available with:

```bash
bin/setup --help
```

## Starting the application

From the project root, run:

```bash
bin/recalboxgui
```

On its first run, the window is centered on the screen. Its position and size are saved when the application closes and restored the next time it starts.

## Configuring a Recalbox environment

1. Open the **Application** menu.
2. Select **Recalbox environments…**.
3. Click **Add**.
4. Complete or review these fields:
   - Environment display name.
   - IP address or network name of the Recalbox system.
   - Connection user.
   - Connection password.
   - ROM folder path.
5. Click **Save**.

The display name identifies the system in the menu and on its connection tab. The eye-shaped button shows or hides the password while it is being edited.

Passwords are stored encrypted in the user's profile settings. This prevents them from appearing as readable text in the file, but it is not a replacement for a system credential store and does not protect against someone with full access to both the program and the user's profile.

## Connecting to Recalbox

1. Open **Application > Connect to environment**.
2. Select the environment name.
3. Wait for the SSH connection to be established.

If the connection succeeds, a tab bearing the environment name appears. An environment that is already connected cannot be opened a second time.

To disconnect it, click the **X** on its tab and confirm. All SSH sessions are closed and their registered remote temporary files are removed when the tab or the application is closed.

If the connection fails, check:

- That Recalbox is switched on.
- That `recalbox.local` responds on the network, or use its IP address.
- That SSH is available.
- That the user name and password are correct.
- That no firewall is blocking the SSH port.

Working Samba access does not guarantee that SSH is enabled or reachable.

## Utilities

After connecting, open the inner **Utilities** tab and select a tool from the list on the left.

### Fix the NTFS mounting BUG

Fixes an issue that prevents certain NTFS disks from being mounted correctly and used to play films in Kodi. The utility first checks whether the patch has already been applied and avoids changing the system when no action is required.

Click **Apply** to check its status and confirm the operation if the patch needs to be installed.

### Clean orphaned media files

Compares the images, thumbnails, and videos in the selected folders with the references contained in `gamelist.xml`.

1. Select the platforms to be checked.
2. Use **All** or **None** to quickly change the selection.
3. Click **Test** to obtain a result without deleting files.
4. Click **Clean** to remove orphaned media after confirming the operation.

Empty folders and folders without a `gamelist.xml` file are skipped. The progress bar displays the task's progress.

> **Warning:** **Clean** permanently deletes orphaned media files. Running **Test** and reviewing its result first is recommended.

### Validate MAME ROMs

Checks the MAME system ROMs using the cores actually available on the Recalbox system. Files are classified as valid, incompatible, unknown, or protected because they are required by other games.

1. Click **Analyze** to generate a report.
2. Review the final summary.
3. **Correct** becomes available after a successful analysis.
4. Click **Correct** to apply the most recently generated report.

ROMs are never deleted. Incompatible ROMs are moved to the `invalids` folder and unknown ROMs to `unknown`. The user can review and manually delete them if desired. Correction also updates `gamelist.xml`, system-specific configuration, and any media that is no longer referenced.

The **Open MAME folder** button opens the corresponding folder through Samba as an anonymous user.

### Validate Neo Geo ROMs

This utility follows the same analysis and correction process as the MAME validator but works only with the `neogeo` system. It does not analyze `neogeocd`.

The validator detects the cores and formats declared and installed in Recalbox. Incompatible and unknown ROMs are moved to their quarantine folders and are never deleted automatically.

The **Open NEOGEO folder** button opens the folder through Samba as an anonymous user.

### Restart services

This utility provides three separate actions:

- **Restart EmulationStation:** restarts only the Recalbox interface. This is useful for reloading systems, games, and `gamelist.xml` changes without restarting the entire system. The operation is blocked while a game, RetroArch, or Kodi is running.
- **Restart Recalbox:** restarts the complete remote system. The connection and its tab close automatically.
- **Shut down Recalbox:** safely shuts down the system. The connection closes, and the system must be physically switched on before it can be used again.

All three actions require confirmation.

## GameList editor

The **GameList** tab can inspect and edit game metadata directly in each system's `gamelist.xml` file.

1. Select a folder from the **Systems** list.
2. Select an entry from the **Games** list, initially sorted by name.
3. Edit its file, name, aliases, genre, genre identifier, publisher, developer, description, image, or thumbnail.
4. Click **Reload** to discard form changes and read the XML again.
5. Click **Save** to validate and update the remote file.

The games list contains **Name** and **Cover** columns. The latter displays **Yes** or **No** to show whether each game has an associated image, making incomplete entries easy to find. Click either column heading to change the sorting.

If a system folder does not contain `gamelist.xml`, the application offers to create an empty one. The following actions are available below the games list:

- **New:** prepares an empty form for adding an entry to the file.
- **Delete...:** can remove only the XML entry or also delete the ROM and its associated resources. Destructive operations require additional confirmation and cannot be undone.

The **File** field must contain a path relative to the system folder and point to an existing ROM. The **Select** button opens a remote file browser restricted to that folder so that the file can be chosen visually. Changing this field only updates the `gamelist.xml` reference; it does not rename or move the ROM.

All fields accept plain text only. Formatting is discarded when content is pasted, and values are validated to ensure that they can be written safely as XML. Attributes and metadata not shown in the form are preserved unchanged.

The **Image** and **Thumbnail** properties show a preview and provide three operations:

- **Select...:** chooses an existing remote file by browsing from the system's `media` folder.
- **Upload...:** accepts PNG, JPEG, WebP, BMP, and GIF images from the local computer. The file is copied to `media/images` or `media/thumbnails`; if its name already exists, another ending in `_2`, `_3`, and so on is generated without overwriting it.
- **Delete:** after confirmation, physically deletes the remote image, clears its field, and immediately updates the corresponding `gamelist.xml` entry.

Selecting or uploading an image refreshes its preview and path in the form. Click **Save** to persist the new reference in the XML.

Saving uses a temporary file and an atomic replacement. If `gamelist.xml` changes after it was loaded—for example, because another process updates it—RecalboxGUI prevents it from being overwritten and asks for the data to be reloaded.

## Language and visual theme

The language can be changed from **Preferences > Language**. The change takes effect immediately and is saved for the next run. Each language name is written in its own language.

The theme is selected from **Preferences > Theme** and is also applied and saved immediately.

## Location of user settings and files

RecalboxGUI does not store personal settings or temporary data inside the project folder, except for the virtual environment created during installation.

On a conventional Linux desktop, Qt normally uses these locations:

- Settings: `~/.config/RecalboxGUI/RecalboxGUI.conf`
- Local data: `~/.local/share/RecalboxGUI/`
- Cache and temporary files: `~/.cache/RecalboxGUI/`
- Known SSH keys: `~/.local/share/RecalboxGUI/ssh/known_hosts`

The exact locations respect `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, and `XDG_CACHE_HOME` when these variables are defined. They can also vary slightly depending on the Linux desktop and distribution.

## Closing the application

Select **Application > Exit...** and confirm. The window's close button can also be used.

The application cannot be closed while a connection attempt or remote utility is running. Before exiting, it closes all SSH connections, removes registered remote files, and saves the window geometry.

## Creating a distributable package

To generate a clean project ZIP, run:

```bash
bin/package
```

The package is created at:

```text
dist/RecalboxGUI.zip
```

The ZIP excludes virtual environments, caches, tests, temporary files, development data, and the old reference scripts folder. On the destination computer, extract it and run:

```bash
bin/setup --install
```

## Main project structure

```text
RecalboxGUI/
├── bin/
│   ├── package                 Creates the distributable package
│   ├── recalboxgui             Application launcher
│   ├── setup                   Installs and checks dependencies
│   └── recalboxscripts/        Scripts run temporarily on Recalbox
├── gui/
│   ├── assets/                 Icon and sounds
│   ├── components/             Reusable visual components
│   ├── connection/             SSH connections and remote execution
│   ├── dialogs/                Application dialogs
│   ├── i18n/                   Language catalogs
│   ├── themes/                 Visual themes
│   └── utilities/              Utility catalog
├── tests/                      Automated tests
├── pyproject.toml              Python metadata and dependencies
└── leeme.md                    Spanish documentation
```

Scripts in `bin/recalboxscripts` are copied temporarily to the Recalbox system when needed. They do not need to be installed manually on the remote system.

## Troubleshooting

### The launcher reports that the virtual environment does not exist

Run:

```bash
bin/setup --install
```

### The application does not start after an update

Update the private environment and check it again:

```bash
bin/setup --install
bin/setup --check
```

### Samba asks for credentials

RecalboxGUI explicitly attempts to mount the `share` resource as an anonymous user. Check that GVfs Samba support is installed by running `bin/setup --install` again and that the shared resource is reachable on the network.

### The SSH connection fails, but Samba works

They are separate services. Check SSH access from a terminal:

```bash
ssh root@recalbox.local
```

Use the system's IP address if `recalbox.local` cannot be resolved.

### The system's SSH identity has changed

Carefully check that you are connecting to the correct system. Known identities are stored in the user's profile, in the `ssh/known_hosts` file inside the RecalboxGUI data directory.

## Authors

Developed by **M.A Software**.

- Website: [https://masoftware.es](https://masoftware.es)
- Email: [info@masoftware.es](mailto:info@masoftware.es)
