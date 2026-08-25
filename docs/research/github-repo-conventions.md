# GitHub conventions in established Windows utilities and game tools

Research date: 2026-08-25. Sources are limited to the projects' own GitHub repositories and GitHub release pages. The examples below are naming observations, not claims that one convention is universally required.

## Compared projects

| Project | README/project naming | Release/tag example | Windows download evidence |
|---|---|---|---|
| [Microsoft PowerToys](https://github.com/microsoft/PowerToys) | The repository and README use **Microsoft PowerToys**. The opening description is functional: “a collection of utilities” for Windows customization and everyday tasks. | Release title: **Release v0.100.2**; tag: `v0.100.2`. | The release lists `PowerToysUserSetup-0.100.2-x64.exe`, ARM64, and machine-wide installer variants. [Releases](https://github.com/microsoft/PowerToys/releases) |
| [ShareX](https://github.com/ShareX/ShareX) | The product name is simply **ShareX**. The README immediately supplies the category: “Screen capture, file sharing and productivity tool.” | Release title: **ShareX 17.0.0** in the changelog/release history; the repository’s release list uses the branded form, e.g. **ShareX 20.2.0**. Tags use the numeric version form such as `v17.0.0`. [Changelog](https://github.com/ShareX/sharex.github.io/blob/master/changelog.md) | The README explicitly points users to GitHub releases and distinguishes regular setup, portable, and development builds. [Releases](https://github.com/ShareX/ShareX/releases) |
| [AutoHotkey](https://github.com/AutoHotkey/AutoHotkey) | The repository uses **AutoHotkey** as both project name and README heading, followed by a concise explanation of its Windows automation/scripting purpose. | Release/tag example: **v2.0.19**; the current release series continues the same `v2.x.y` form. | Release assets use the product name plus version and packaging role, for example `AutoHotkey_2.0.20_setup.exe` and `AutoHotkey_2.0.20.zip`. [Releases](https://github.com/AutoHotkey/AutoHotkey/releases) |
| [OBS Studio](https://github.com/obsproject/obs-studio) | The public product name is **OBS Studio**. The repository description states the category and purpose: free, open-source software for live streaming and screen recording. | Release title: **OBS Studio 32.2.2**; tag: `32.2.2` without a leading `v`. Preview releases are made explicit in the title, e.g. “Release Candidate” and “Beta”. | Assets use `OBS-Studio-<version>-Windows-<arch>` naming and include an installer and portable ZIP, e.g. `OBS-Studio-32.2.2-Windows-x64-Installer.exe`. [Releases](https://github.com/obsproject/obs-studio/releases) |
| [LosslessCut](https://github.com/mifi/lossless-cut) | The repository is hyphenated/lowercase, but the user-facing name is **LosslessCut**. The README uses a memorable category phrase: “The swiss army knife of lossless video/audio editing.” | Release list title: **3.69.0**; signed tag: `v3.69.0`. The title omits `v` even though the tag keeps it. | The README directs users to Windows 7-Zip downloads; the release includes `LosslessCut-win-x64.7z` and ARM64 variants. [Releases](https://github.com/mifi/lossless-cut/releases) |
| [Prism Launcher](https://github.com/PrismLauncher/PrismLauncher) | The repository display name and README use **Prism Launcher**. The README describes it in one sentence as a custom launcher for managing multiple Minecraft installations. | Release title: **Prism Launcher 11.0.2**; tag: `11.0.2` without `v`. A release title can add a short operational warning, as in the manually-required updater notice, without changing the version/tag. | Assets use product + platform/toolchain + version, e.g. `PrismLauncher-Windows-MinGW-arm64-11.0.2.zip`. [Releases](https://github.com/PrismLauncher/PrismLauncher/releases) |
| [OpenRCT2](https://github.com/OpenRCT2/OpenRCT2) | **OpenRCT2** is used consistently. The README combines a descriptive expansion (“open-source re-implementation of RollerCoaster Tycoon 2”) with a short Download section. | Release title/tag: **v0.5.3 - “Well, I didn't vote for you!”**. The project uses `v<SemVer>` and adds a themed subtitle to stable releases. | Release assets include explicit Windows installers such as `OpenRCT2-v0.5.3-windows-installer-win32.exe` and ARM64. [Releases](https://github.com/OpenRCT2/OpenRCT2/releases) |

## Naming patterns

### README and project name

1. Use one short product name as the README H1 and GitHub repository identity. Branding is usually title case (`ShareX`, `OBS Studio`, `Prism Launcher`, `LosslessCut`) even when the repository slug is lowercase or hyphenated.
2. Follow the name with one plain-language sentence describing the tool’s job and platform. The strongest examples make the category obvious immediately: Windows utilities, screen capture, automation, video editing, or game launcher.
3. Treat the repository name as a stable brand, not as a build or implementation label. None of these projects lead with words such as `source`, `app`, `tool`, or a framework name in the user-facing title.

### Version tags

- Semantic versioning is the dominant pattern: `major.minor.patch`.
- A leading `v` is common but not mandatory. PowerToys, AutoHotkey, LosslessCut, and OpenRCT2 use `v`; OBS Studio and Prism Launcher use a bare numeric tag.
- Do not mix styles within one project. The practical choice for a small Windows utility is `v0.1.0`, `v0.1.1`, etc., because it is recognizable in GitHub URLs and familiar to release tooling.
- Pre-release status is clearer when encoded explicitly, either in the tag (`v0.2.0-beta.1`) or in the release title/notes. OBS Studio’s release pages make “Beta” and “Release Candidate” visible in the title.

### GitHub release names

- Mature applications commonly use `<Product Name> <version>`: `ShareX 17.0.0`, `OBS Studio 32.2.2`, and `Prism Launcher 11.0.2`.
- Some projects use `v<version>` or `Release v<version>` as the title: AutoHotkey and PowerToys demonstrate this.
- Release titles may add human context after the stable version, but the version remains easy to scan. OpenRCT2’s themed subtitle is a good example; Prism Launcher’s updater warning is useful release context.
- Keep the tag and release title semantically identical even when their typography differs. For example, a tag `v3.69.0` can have a display title `3.69.0`, but it should not introduce a second or different version.

### Downloadable Windows assets

Asset names are more technical than release titles. The observed structure is generally:

`<product>-<version>-<platform/architecture/package>.<ext>`

Useful cues include `Windows`/`win`, `x64`, `arm64`, `Installer`/`Setup`, and `zip`/`7z`. This makes the GitHub Assets list self-explanatory without putting architecture details into the public product name or release title.

## Recommendation for SCP:SL AutoJoin

For this project, use the following compact, recognizable scheme:

- README H1: **SCP:SL AutoJoin**
- Opening sentence: **A Windows utility that automatically joins configured SCP: Secret Laboratory servers.** Adjust the behavior description if the implemented scope is narrower, but keep the first sentence concrete.
- Tags: `v0.1.0`, `v0.1.1`, then normal SemVer increments.
- Stable release title: **SCP:SL AutoJoin v0.1.0**. This combines the branded-title pattern used by ShareX/OBS/Prism Launcher with the `v` style used by PowerToys/OpenRCT2.
- Windows asset example: `SCP-SL-AutoJoin-v0.1.0-windows-x64.zip` or `SCP-SL-AutoJoin-v0.1.0-windows-x64-setup.exe`, depending on whether the release is portable or installable.
- If a build is not stable, make that visible: `SCP:SL AutoJoin v0.1.0-beta.1` rather than an ambiguous title such as “First release”.

This keeps the human-facing name stable while making versions, Windows architecture, and package type obvious in GitHub’s release list and Assets section.
