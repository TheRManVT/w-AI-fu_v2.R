# w-AI-fu_v2.R
 Create your own AI Vtuber/Streamer ! (Openai or NovelAI)

## ⚠️THIS IS NOT THE ORIGINAL REPO!
This was created after version 2.0.7 and only is here for people, who have to reinstall the program.
The original repo is available [here](https://github.com/wAIfu-DEV/w-AI-fu_v2) (Currently private)

> [!NOTE]
> Please don't tell DEV about this. I only uploaded it for the people, who have to reinstall the program but deleted the original downloaded ZIP

## Knwon issuses
- You get a JavaScript error when starting w-AI-fu
  - **SHOULD** be fixed in this version
- You get stuck on "Creating Electron window" after restarting
  - Run venv-Delete.bat, which deletes the venv-folder inside source/app/vectordb
- I want to use NovelAI but they changed their API endpoint
  - First, move the original and the".dist-info"-folder to a different place, then activate the venv via opening the terminal in the root folder and put this command in:
```
venv/Scripts/activate
```
After you are in the venv, insert this command:
```
pip install novelai_api==0.31.0
```
this installs some depedenciese needed for this version to work. Then reinstall the other needed dependencies by inputting these commands:
```
cd install/
pip install -r requirements.txt
```
After that is done, just copy the novelai_api-folder from the base(or download the folder from [their repo]([https://github.com/Aedial/novelai-api](https://github.com/Aedial/novelai-api/archive/refs/tags/v0.31.0.zip))) into "venv\Lib\site-packages" and start w-AI-fu
- It shows me an error about ffmpeg
  - You have to download the [ffmpeg executable](https://www.ffmpeg.org/download.html) and put it into "bin/ffmpeg" before starting
- My AI is now back before I created them
  - If you have the original w-AI-fu, then just copy-paste the userdata folder from the original into this verison (Better to not overwrite things, though)
- My AI has forgotten everything
  - Copy the database.txt from source/app/vectordb in the original version of w-AI-fu and put it into the same folder again in this version

## Installation
1. Download the ZIP through the button on the top and extract it.
2. Install Python 3.10.X (preferably .11) and [NodeJS v19.8.1](https://nodejs.org/en/download/releases) (Install through the .msi-Installer)
3. Install the VC++ Build Tools (Guides, on how, are [here](https://www.pythondiscord.com/pages/tags/microsoft-build-tools/) and [here](https://hub.tcno.co/software/vs/buildtools/))
4. Reboot your PC, just in case
5. Install w-AI-fu through INSTALL.BAT
6. Wait till it's completed
7. Run it through the created shortcut

-----

### If you need help, don't be afraid to contact me

