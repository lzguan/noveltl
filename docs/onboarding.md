# Onboarding

**Last updated:** 2026-05-10

## Getting started

Clone the project from Github. After that, setup the project using one of the methods below.

## Devcontainer setup

Devcontainers are a useful feature in VSCode that allow you to develop in a Docker container. 

To get started with devcontainers, open the project in VSCode and install the [Dev Containers](vscode:extension/ms-vscode-remote.remote-containers) extension. A popup should come up in the bottom right corner asking to reopen the current folder in a container. Alternatively, open the [Command Palette](https://code.visualstudio.com/docs/getstarted/userinterface#_command-palette) and select "Open Folder in Container" (or something like that). Wait for the container to finish building and you are all set.

Devcontainer configurations are found in [`../devcontainer`](../.devcontainer/). The devcontainer is configured to save Github CLI configs and agent conversations as volumes and load them on devcontainer creation for convenience. Currently this is supported for Claude Code and Codex. All tools mentioned [here](project-structure.md#toolstechnologies) are configured in the devcontainer. Coding agents must be installed separately.

> Note for Windows users: make sure to clone this repository onto the WSL filesystem and not the mounted Windows filesystem. 

## Local

Local setup not yet documented, we recommend using devcontainers for now.