@echo off
set NEOFORGE_VERSION=26.1.2.109
:: To use a specific Java runtime, set an environment variable named ATM11_JAVA to the full path of java.exe.
:: To disable automatic restarts, set an environment variable named ATM11_RESTART to false.
:: To install the pack without starting the server, set an environment variable named ATM11_INSTALL_ONLY to true.

set INSTALLER="%~dp0neoforge-%NEOFORGE_VERSION%-installer.jar"
set NEOFORGE_URL="https://maven.neoforged.net/releases/net/neoforged/neoforge/%NEOFORGE_VERSION%/neoforge-%NEOFORGE_VERSION%-installer.jar"

:JAVA
if not defined ATM11_JAVA (
    set ATM11_JAVA=java
)

"%ATM11_JAVA%" -version 1>nul 2>nul || (
   echo Minecraft 26.1.2 requires Java 25 - Java not found
   pause
   exit /b 1
)

:NEOFORGE
setlocal
cd /D "%~dp0"
if not exist "libraries" (
    echo Neoforge not installed, installing now.
    if not exist %INSTALLER% (
        echo No Neoforge installer found, downloading from %NEOFORGE_URL%
        bitsadmin.exe /rawreturn /nowrap /transfer neoforge /download /priority FOREGROUND %NEOFORGE_URL% %INSTALLER%
    )
    
    echo Running Neoforge installer.
    "%ATM11_JAVA%" -jar %INSTALLER% -installServer
)

if not exist "server.properties" (
    (
        echo allow-flight=true
        echo motd=All the Mods 11
        echo max-tick-time=180000
		echo simulation-distance=5
		echo view-distance=8
    )> "server.properties"
)

if "%ATM11_INSTALL_ONLY%" == "true" (
    echo INSTALL_ONLY: complete
    goto:EOF
)

for /f tokens^=2-5^ delims^=.-_^" %%j in ('"%ATM11_JAVA%" -fullversion 2^>^&1') do set "jver=%%j"
if not %jver% geq 21  (
    echo Minecraft 1.21 requires Java 25 - found Java %jver%
    pause
    exit /b 1
) 

:START
"%ATM11_JAVA%" @user_jvm_args.txt @libraries\net\neoforged\neoforge\%NEOFORGE_VERSION%\win_args.txt nogui

if "%ATM11_RESTART%" == "false" ( 
    goto:EOF 
)

echo Restarting automatically in 10 seconds (press Ctrl + C to cancel)
timeout /t 10 /nobreak > NUL
goto:START
