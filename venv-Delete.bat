@echo off
title w-AI-fu - Workaround for "Stuck on 'Creating Electron window'"

REM Set the base directory to the current directory where the batch file is located
set "baseDir=%~dp0"
REM Define the target folder relative to the base directory
set "targetFolder=%baseDir%source\app\vectordb\venv"

echo Detecting if %targetFolder% exists...

if exist "%targetFolder%" (
    echo Folder exists.
    choice /M "Do you want to delete the folder %targetFolder%? "
    if errorlevel 2 (
        echo Deletion canceled.
    ) else if errorlevel 1 (
        title w-AI-fu - Deleting...
		rmdir /s /q "%targetFolder%"
		title w-AI-fu - Finished
        echo Folder deleted.
    )
) else (
    title w-AI-fu - Folder not found
    echo Folder not found: %targetFolder%
    echo Please only run this, if the error occurs and the folder was created by w-AI-fu
)

pause
