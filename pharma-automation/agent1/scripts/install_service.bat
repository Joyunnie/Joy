@echo off
setlocal EnableDelayedExpansion

:: ============================================================
:: PharmaAgent1 Windows 서비스 설치 스크립트 (NSSM 사용)
:: 반드시 관리자 권한으로 실행하십시오.
:: ============================================================

set SERVICE_NAME=PharmaAgent1
set INSTALL_DIR=C:\pharma-agent
set CONFIG_PATH=%INSTALL_DIR%\agent1\config.yaml
set LOG_PATH=%INSTALL_DIR%\agent1\logs\service.log
set NSSM_URL=https://nssm.cc/release/nssm-2.24.zip
set NSSM_DIR=%INSTALL_DIR%\tools\nssm
set NSSM=%NSSM_DIR%\nssm.exe

echo.
echo ============================================================
echo  PharmaAgent1 서비스 설치
echo ============================================================
echo.

:: --- 관리자 권한 확인 ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [오류] 관리자 권한이 필요합니다.
    echo 이 스크립트를 마우스 오른쪽 클릭 후 "관리자로 실행"을 선택하십시오.
    pause
    exit /b 1
)
echo [OK] 관리자 권한 확인

:: --- Python 경로 감지 ---
for /f "delims=" %%i in ('where python 2^>nul') do (
    set PYTHON_PATH=%%i
    goto :python_found
)
echo [오류] Python을 찾을 수 없습니다.
echo PATH에 Python이 등록되어 있는지 확인하십시오.
pause
exit /b 1

:python_found
echo [OK] Python 경로: %PYTHON_PATH%

:: --- 설치 디렉토리 확인 ---
if not exist "%INSTALL_DIR%" (
    echo [오류] 설치 디렉토리가 없습니다: %INSTALL_DIR%
    echo 먼저 Agent1 파일을 %INSTALL_DIR% 에 배포하십시오.
    pause
    exit /b 1
)
echo [OK] 설치 디렉토리: %INSTALL_DIR%

:: --- config.yaml 확인 ---
if not exist "%CONFIG_PATH%" (
    echo [오류] config.yaml이 없습니다: %CONFIG_PATH%
    echo config.example.yaml을 복사하여 설정 후 다시 실행하십시오.
    pause
    exit /b 1
)
echo [OK] config.yaml: %CONFIG_PATH%

:: --- 로그 디렉토리 생성 ---
if not exist "%INSTALL_DIR%\agent1\logs" (
    mkdir "%INSTALL_DIR%\agent1\logs"
    echo [OK] 로그 디렉토리 생성: %INSTALL_DIR%\agent1\logs
)

:: --- NSSM 확인 및 설치 ---
if exist "%NSSM%" (
    echo [OK] NSSM 존재: %NSSM%
) else (
    echo [INFO] NSSM을 찾을 수 없습니다. 자동 다운로드를 시도합니다...
    echo.

    :: tools 디렉토리 생성
    if not exist "%NSSM_DIR%" mkdir "%NSSM_DIR%"

    :: PowerShell로 다운로드
    set NSSM_ZIP=%NSSM_DIR%\nssm.zip
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "try { Invoke-WebRequest -Uri '%NSSM_URL%' -OutFile '%NSSM_ZIP%' -UseBasicParsing; Write-Host 'Download OK' } catch { Write-Host 'Download FAILED: ' + $_.Exception.Message; exit 1 }"
    if %errorlevel% neq 0 (
        echo.
        echo [오류] NSSM 자동 다운로드 실패.
        echo 수동 설치 방법:
        echo   1. %NSSM_URL% 에서 nssm.zip 다운로드
        echo   2. 압축 해제 후 nssm.exe를 %NSSM% 에 복사
        echo   3. 이 스크립트를 다시 실행
        pause
        exit /b 1
    )

    :: 압축 해제 (win64)
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "Expand-Archive -Path '%NSSM_ZIP%' -DestinationPath '%NSSM_DIR%\extracted' -Force"
    copy /y "%NSSM_DIR%\extracted\nssm-2.24\win64\nssm.exe" "%NSSM%" >nul
    if %errorlevel% neq 0 (
        echo [오류] NSSM 압축 해제 실패.
        pause
        exit /b 1
    )
    del "%NSSM_ZIP%" >nul 2>&1
    echo [OK] NSSM 설치 완료: %NSSM%
)

:: --- 기존 서비스 정리 ---
sc query "%SERVICE_NAME%" >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] 기존 %SERVICE_NAME% 서비스를 제거합니다...
    sc stop "%SERVICE_NAME%" >nul 2>&1
    timeout /t 3 /nobreak >nul
    "%NSSM%" remove "%SERVICE_NAME%" confirm
    echo [OK] 기존 서비스 제거 완료
)

:: --- 서비스 등록 ---
echo.
echo [INFO] 서비스를 등록합니다...

"%NSSM%" install "%SERVICE_NAME%" "%PYTHON_PATH%"
"%NSSM%" set "%SERVICE_NAME%" AppParameters "-m agent1.agent.main --config %CONFIG_PATH%"
"%NSSM%" set "%SERVICE_NAME%" AppDirectory "%INSTALL_DIR%"

:: 로그 설정
"%NSSM%" set "%SERVICE_NAME%" AppStdout "%LOG_PATH%"
"%NSSM%" set "%SERVICE_NAME%" AppStderr "%LOG_PATH%"
"%NSSM%" set "%SERVICE_NAME%" AppRotateFiles 1
"%NSSM%" set "%SERVICE_NAME%" AppRotateBytes 10485760

:: 시작 유형: 자동
"%NSSM%" set "%SERVICE_NAME%" Start SERVICE_AUTO_START

:: 설명
"%NSSM%" set "%SERVICE_NAME%" Description "Pharma Automation Agent1 - PM+20 sync service"

:: --- 환경변수 설정 ---
:: PYTHONPATH는 setx로는 서비스에 반영되지 않으므로 NSSM AppEnvironmentExtra 사용
"%NSSM%" set "%SERVICE_NAME%" AppEnvironmentExtra ^
    "PYTHONPATH=%INSTALL_DIR%" ^
    "PM20_DB_PASSWORD=Ag3nt1!Read2024" ^
    "PM20_HASH_SALT=pharma-auto-salt-2024" ^
    "PHARMA_API_KEY=31b963d9f12985fa369d0e73d54c47581a08e737022dc25b5ba287f1ca7ba025"

:: --- 실패 시 재시작 설정 (30초 후) ---
sc failure "%SERVICE_NAME%" reset= 86400 actions= restart/30000/restart/30000/restart/30000

echo.
echo [OK] 서비스 등록 완료

:: --- 서비스 시작 ---
echo [INFO] 서비스를 시작합니다...
sc start "%SERVICE_NAME%"
if %errorlevel% equ 0 (
    echo [OK] %SERVICE_NAME% 서비스가 시작되었습니다.
) else (
    echo [경고] 서비스 시작에 실패했습니다. 수동으로 시작하거나 로그를 확인하십시오.
    echo   로그: %LOG_PATH%
)

echo.
echo ============================================================
echo  설치 완료
echo  서비스명  : %SERVICE_NAME%
echo  상태 확인 : sc query %SERVICE_NAME%
echo  로그      : %LOG_PATH%
echo  서비스 관리: services.msc
echo ============================================================
echo.
pause
endlocal
