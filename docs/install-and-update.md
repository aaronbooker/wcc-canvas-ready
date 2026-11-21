# Install or update WCC Canvas Ready, step by step

These steps cover a first install and every update. They use Claude in a web browser at [claude.ai](https://claude.ai). A free Claude account works. An update takes about a minute.

Claude changes its menus often. The pictures of Claude were taken on November 21, 2026, and your screen may look a little different.

## Get updates from here

The skill keeps improving, and updates may come often. Every update comes from this GitHub site. When there is a newer version, the skill tells you at the start of a chat, names the new version and gives you a link back here. Claude can't install the update for you, so you follow the steps below.

The notice looks like this. This one came from the update to version 1.1.0. Notices from later versions name the .skill file.

![Claude's update notice: v1.1.0 is out (you have v1.0.11), with three numbered steps and a link to steps with pictures.](images/10-update-notice.png)

Only download the skill from [github.com/aaronbooker/wcc-canvas-ready](https://github.com/aaronbooker/wcc-canvas-ready). If an email, a message or another website offers you a WCC Canvas Ready file, don't use it.

## Before you start (first install only)

1. Make a Claude account at [claude.ai](https://claude.ai) if you don't have one.
2. In Claude, select your name in the bottom-left corner, then **Settings**. Settings opens in a window over your chat. Choose **Capabilities** in the list on the left.
3. Make sure **Create and edit files** is switched on. Skills need it.

![Claude's Settings window with Capabilities selected. The Create and edit files switch is on, and its description says skills need this on.](images/02-create-and-edit-files.png)

## Step 1: Download the .skill file

1. Open the [latest release of WCC Canvas Ready](https://github.com/aaronbooker/wcc-canvas-ready/releases/latest). The version number is at the top, next to a green **Latest** label. A short list of what's new is below it.
2. Under **Assets**, select **wcc-canvas-ready.skill**. Don't choose either **Source code** download. Those won't work in Claude.
3. It goes into your Downloads folder. Leave it as it is. Don't open it.

![The GitHub release page for WCC Canvas Ready. At the top are the version number and a Latest label, then short notes on what's new. At the bottom, under Assets, wcc-canvas-ready.skill is outlined. A ZIP of the same skill and two Source code downloads are listed below it.](images/08-github-release.png)

The release may also list **wcc-canvas-ready.zip**. It's the same skill in the older file type. Use the .skill file: Claude's **Upload new version** button accepts only that.

## Step 2: Add it to Claude (first install)

1. In Claude's left sidebar, choose **Plugins**.

   ![Claude's left sidebar with New, Search, Projects, Artifacts, Code and Plugins. Plugins is selected.](images/03-plugins-in-sidebar.png)

2. At the top right of the Plugins page, choose **Add**, then **Upload plugin**. Claude treats a skill as one kind of plugin, so this is the right choice.

   ![The Plugins page. The Add menu is open and lists Upload plugin, Add custom connector, Create a plugin, Create with Claude and Add marketplace.](images/04-add-upload-plugin.png)

3. On the **Upload a plugin** page, drag **wcc-canvas-ready.skill** from your Downloads folder into the box under **Plugin file**, or select **browse** and choose it. A **Preview** shows the skill's name and description. Then select **Upload**.

   ![The Upload a plugin page with wcc-canvas-ready.skill (204 kB) chosen. A Preview box shows wcc-canvas-ready and its description. Upload and Cancel are below it.](images/05-upload-a-plugin.png)

4. Claude says **Wcc canvas ready is added and ready to use.** The skill is listed under **Your plugins** on the Plugins page. Open it and check that it says **Added** at the top right. A blue **New** label may show next to its name.

   ![The Wcc canvas ready page with a New label next to its name, an Added label at the top right, its description, and the skill listed under Skills.](images/06-skill-added.png)

## Step 2 instead: Update the copy you have

1. In Claude's left sidebar, choose **Plugins**. Under **Your plugins**, open **Wcc canvas ready**.
2. Select the three dots (**…**) at the top right, then **Upload new version**.

   ![The Wcc canvas ready page with the three-dot menu open. It lists Try in chat, Edit with Claude, Rename, Duplicate, Download, Upload new version, Disable and Delete.](images/09-upload-new-version-menu.png)

3. Drag **wcc-canvas-ready.skill** into the box, or select **Browse files** and choose it. Then select **Upload**. It replaces the old version. You don't need to delete anything first.

   ![The Upload a new version of Wcc canvas ready window. It says to pick a .skill file or a SKILL.md with this skill's name, and that earlier versions stay in the version history.](images/11-upload-new-version.png)

4. Claude says **Replaced Wcc canvas ready**.

   ![The bottom of the Wcc canvas ready page. Version shows v2, and a notice says Replaced Wcc canvas ready.](images/12-replaced.png)

The **Version** on that page (v1, v2 and so on) only counts how many times you've uploaded the skill. It isn't the skill's version number. Step 3 shows how to check that.

If you choose **Add**, then **Upload plugin** for an update by mistake, that works too. Claude asks **Replace existing plugin?** Select **Replace**.

![A window titled Replace existing plugin? It says a plugin named Wcc canvas ready is already installed and this replaces it with the new version. Cancel and Replace buttons.](images/13-replace-existing-plugin.png)

## Step 3: Start a new chat

The new version is sure to work in a new chat. To check, type: **Use the WCC Canvas Ready skill and tell me which version it is and whether there is an update.** The version should match the one on the GitHub page.

![Claude's answer in a new chat: You have WCC Canvas Ready v1.1.1. It says it couldn't confirm whether a newer version exists and gives the link to the latest release.](images/14-version-check.png)

On many accounts Claude can't reach GitHub to check for updates. Then it tells you which version you have and gives you the link, and you can compare the number yourself.

To use the skill, select the **+** button and choose **Upload or add files** (or drag your file into the chat box), then type **Get this file ready for Canvas.** Take out student names, grades and records first.

![The chat box with Get this file ready for Canvas typed in it. The + menu is open and lists Upload or add files first.](images/07-chat-box.png)

## Help improve the skill

Send your original file, the one from before you used the skill, to Aaron Booker at [abooker1@whatcom.edu](mailto:abooker1@whatcom.edu). That's all: no report and no second file. Aaron runs it through the skill himself, and the files faculty send are how the skill gets better. Take out student names, grades and records first. Files you send are used only for testing and are not shared or posted.

---

© 2026 Aaron Booker. This guide is licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/). Screenshots show Claude (Anthropic) and GitHub as they appeared on November 19, 20 and 21, 2026.
